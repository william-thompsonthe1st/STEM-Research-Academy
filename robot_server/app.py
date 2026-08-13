"""3TSahur hotspot dashboard for its two LARP reconnaissance scouts."""

from __future__ import annotations

import atexit
import json
import logging
import math
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path
from uuid import uuid4

from flask import Flask, Response, jsonify, render_template, request, send_from_directory, url_for

from .actuators import ActuatorController
from .camera import CameraStream
from .motor import MecanumDrive
from .scouts import CameraRegistry, ScoutRegistry
from .vision import VisionManager


# Drive heartbeats are intentionally frequent and must not flood journald.
# Warnings, tracebacks, and explicit application errors remain visible.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

WATCHDOG_SECONDS = float(os.environ.get("DRIVE_WATCHDOG_SECONDS", "0.20"))
# A drive route must return well before the browser's latest-command timeout.
# This bounds a missing/offline scout without extending a stale command queue.
SCOUT_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("SCOUT_REQUEST_TIMEOUT_SECONDS", "0.12"))
drive = MecanumDrive()
camera = CameraStream(
    device=os.environ.get("CAMERA_DEVICE", "auto"),
    width=int(os.environ.get("CAMERA_WIDTH", "640")),
    height=int(os.environ.get("CAMERA_HEIGHT", "480")),
    fps=int(os.environ.get("CAMERA_FPS", "10")),
)
last_drive_at = 0.0
last_scout_motion_at = {"a": 0.0, "b": 0.0}
state_lock = threading.Lock()
shutdown_event = threading.Event()
drive_sequences: dict[str, int] = {}
scout_sequences: dict[tuple[str, str], int] = {}
scout_command_locks = {"a": threading.Lock(), "b": threading.Lock()}
scout_registry = ScoutRegistry()
camera_registry = CameraRegistry()


def _env_first(*names: str, default: str = "") -> str:
    """Accept current settings and the aliases used in the partner project."""
    return next((value for name in names if (value := os.environ.get(name))), default)


SCOUTS = {
    "a": {
        "name": "LARP Scout A",
        "host": _env_first("LARP_A_HOST", "SCOUT_A_HOST", default="larp-a.local"),
        "camera": _env_first("LARP_A_CAMERA_URL", "ESP32_ONE_STREAM_URL", default="http://larp-a-cam.local/stream"),
    },
    "b": {
        "name": "LARP Scout B",
        "host": _env_first("LARP_B_HOST", "SCOUT_B_HOST", default="larp-b.local"),
        "camera": _env_first("LARP_B_CAMERA_URL", "ESP32_TWO_STREAM_URL", default="http://larp-b-cam.local/stream"),
    },
}


CAMERA_URL_SETTINGS = {
    "a": ("LARP_A_CAMERA_URL", "ESP32_ONE_STREAM_URL"),
    "b": ("LARP_B_CAMERA_URL", "ESP32_TWO_STREAM_URL"),
}


def _control_is_active() -> bool:
    """Report recent hub or Scout motion for optional-work bandwidth gating."""
    now = time.monotonic()
    return bool(
        (last_drive_at and now - last_drive_at < WATCHDOG_SECONDS * 1.5)
        or any(stamp and now - stamp < 0.35 for stamp in last_scout_motion_at.values())
    )


def _scout_camera_url(scout_id: str) -> str:
    configured_url = _env_first(*CAMERA_URL_SETTINGS[scout_id])
    if configured_url:
        return configured_url
    return camera_registry.stream_url(scout_id, SCOUTS[scout_id]["camera"])


def _fetch_scout_jpeg(scout_id: str, timeout: float) -> bytes | None:
    """Read one complete JPEG from the ESP32-CAM's MJPEG response."""
    raw = bytearray()
    with urllib.request.urlopen(_scout_camera_url(scout_id), timeout=timeout) as response:
        while len(raw) < 128_000:
            chunk = response.read(min(4096, 128_000 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
            start = raw.find(b"\xff\xd8")
            end = raw.find(b"\xff\xd9", max(0, start + 2))
            if start >= 0 and end > start:
                return bytes(raw[start:end + 2])
    return None


def _relay_scout_camera(scout_id: str):
    """Keep a browser stream open while an ESP32-CAM reconnects or gets DHCP."""
    while True:
        try:
            with urllib.request.urlopen(_scout_camera_url(scout_id), timeout=1.5) as response:
                while chunk := response.read(4096):
                    yield chunk
        except (OSError, ValueError, urllib.error.URLError):
            time.sleep(0.5)


def _scout_frame(scout_id: str):
    """Read one bounded scout frame in the optional worker."""
    return _fetch_scout_jpeg(scout_id, timeout=0.4)


vision = VisionManager({
    "3tsahur": camera.latest_jpeg,
    "larp-a": lambda: _scout_frame("a"),
    "larp-b": lambda: _scout_frame("b"),
}, should_pause=_control_is_active)
events: deque[dict] = deque(maxlen=120)
event_lock = threading.Lock()
snapshot_dir = Path(os.environ.get("SNAPSHOT_DIR", "/tmp/3tsahur-snapshots"))
CAMERA_PROFILES = {"control": (320, 240, 6), "balanced": (640, 480, 10), "detail": (1280, 720, 12)}
camera_profile = "balanced"
actuators = ActuatorController()


def record_event(kind: str, source: str, message: str) -> dict:
    event = {"id": uuid4().hex[:10], "at_ms": round(time.time() * 1000), "kind": kind[:32], "source": source[:16], "message": message[:160]}
    with event_lock:
        events.appendleft(event)
    return event


def _snapshot_bytes(source: str) -> bytes | None:
    if source == "3tsahur":
        return camera.latest_jpeg()
    scout_id = {"larp-a": "a", "larp-b": "b"}.get(source)
    if not scout_id:
        return None
    return _fetch_scout_jpeg(scout_id, timeout=0.75)


def _scout_request(scout_id: str, path: str, query: dict | None = None) -> dict:
    scout = SCOUTS.get(scout_id)
    if scout is None:
        raise KeyError(scout_id)
    suffix = f"?{urllib.parse.urlencode(query)}" if query else ""
    host = scout_registry.host_for(scout_id, scout["host"])
    url = f"http://{host}{path}{suffix}"
    with urllib.request.urlopen(url, timeout=SCOUT_REQUEST_TIMEOUT_SECONDS) as response:
        body = response.read(8192).decode("utf-8")
    return json.loads(body) if body else {"ok": True}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.after_request
    def prevent_stale_dashboard(response):
        if request.endpoint not in {"camera_feed", "scout_camera_feed"}:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            larp_a_stream=url_for("scout_camera_feed", scout_id="a"),
            larp_b_stream=url_for("scout_camera_feed", scout_id="b"),
            server_time_ms=round(time.time() * 1000),
        )

    @app.get("/camera.mjpg")
    def camera_feed():
        return Response(camera.frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/scouts/<scout_id>/camera.mjpg")
    def scout_camera_feed(scout_id: str):
        if scout_id not in SCOUTS:
            return jsonify(error="Unknown scout"), 404
        return Response(
            _relay_scout_camera(scout_id),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/api/status")
    def status():
        return jsonify(
            online=True,
            name="3TSahur",
            hostname=socket.gethostname(),
            gpio="hardware" if drive.is_hardware else "simulation",
            camera_available=camera.available,
            camera_error=camera.error,
            camera_device=camera.selected_device,
            camera_profile=camera_profile,
            camera_width=camera.width,
            camera_height=camera.height,
            camera_fps=camera.fps,
            uptime_seconds=round(time.monotonic(), 1),
            command=drive.last_command,
            actuators=actuators.snapshot(),
            camera_heartbeats={camera_id: camera_registry.snapshot(camera_id) for camera_id in ("a", "b")},
            vision={source: vision.snapshot(source) for source in ("3tsahur", "larp-a", "larp-b")},
            server_time_ms=round(time.time() * 1000),
        )

    @app.post("/api/camera/profile")
    def set_camera_profile():
        global camera_profile
        if _control_is_active():
            return jsonify(error="Stop all robots before changing the camera profile", control_active=True), 409
        profile = str((request.get_json(silent=True) or {}).get("profile", ""))
        if profile not in CAMERA_PROFILES:
            return jsonify(error="Unknown camera profile"), 400
        width, height, fps = CAMERA_PROFILES[profile]
        try:
            camera.configure(width, height, fps)
            camera_profile = profile
            return jsonify(ok=True, profile=profile, width=width, height=height, fps=fps)
        except ValueError as error:
            return jsonify(error=str(error)), 400

    @app.post("/api/actuators/gimbal")
    def set_gimbal():
        payload = request.get_json(silent=True) or {}
        try:
            result = actuators.set_gimbal(payload.get("pan"), payload.get("tilt"))
            record_event("gimbal", "3tsahur", f"Gimbal target pan {result['gimbal']['pan']}°, tilt {result['gimbal']['tilt']}°")
            return jsonify(ok=True, **result)
        except ValueError as error:
            return jsonify(error=str(error)), 400

    @app.post("/api/actuators/ramp")
    def set_ramp():
        payload = request.get_json(silent=True) or {}
        try:
            result = actuators.set_ramp(payload.get("state"))
            record_event("ramp", "3tsahur", f"Ramp target {result['ramp']['state']}")
            return jsonify(ok=True, **result)
        except ValueError as error:
            return jsonify(error=str(error)), 400
    @app.route("/api/vision/<source>", methods=["GET", "POST"])
    def vision_status(source: str):
        try:
            if request.method == "POST":
                enabled = bool((request.get_json(silent=True) or {}).get("enabled", False))
                return jsonify(vision.set_enabled(source, enabled))
            return jsonify(vision.snapshot(source))
        except KeyError:
            return jsonify(error="Unknown vision source"), 404

    @app.get("/api/events")
    def event_list():
        with event_lock:
            return jsonify(events=list(events))

    @app.post("/api/events")
    def add_event():
        payload = request.get_json(silent=True) or {}
        return jsonify(record_event(str(payload.get("kind", "note")), str(payload.get("source", "dashboard")), str(payload.get("message", "Operator event"))))

    @app.post("/api/snapshots/<source>")
    def snapshot(source: str):
        if source not in ("3tsahur", "larp-a", "larp-b"):
            return jsonify(error="Unknown snapshot source"), 404
        if _control_is_active():
            return jsonify(error="Stop all robots before taking a snapshot", control_active=True), 409
        try:
            image = _snapshot_bytes(source)
            if not image:
                raise RuntimeError("No JPEG frame received")
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            name = f"{round(time.time() * 1000)}-{source}.jpg"
            (snapshot_dir / name).write_bytes(image)
            event = record_event("snapshot", source, f"Saved {source} camera snapshot")
            return jsonify(ok=True, url=f"/snapshots/{name}", event=event)
        except Exception as error:
            return jsonify(error=f"Snapshot unavailable: {error}"), 503

    @app.get("/snapshots/<path:name>")
    def serve_snapshot(name: str):
        return send_from_directory(snapshot_dir, name)

    @app.post("/api/drive")
    def command_drive():
        global last_drive_at
        payload = request.get_json(silent=True) or {}
        try:
            forward = float(payload.get("forward", 0))
            strafe = float(payload.get("strafe", 0))
            rotate = float(payload.get("rotate", 0))
            speed = float(payload.get("speed", 0.75))
            sequence = int(payload.get("sequence", 0))
            session = str(payload.get("session", "legacy"))[:64]
            expires_at_ms = int(payload["expires_at_ms"])
        except (TypeError, ValueError):
            return jsonify(error="Drive values must be numbers"), 400
        except KeyError:
            return jsonify(error="Current control protocol required", expired=True), 409
        server_now_ms = round(time.time() * 1000)
        if expires_at_ms < server_now_ms or expires_at_ms > server_now_ms + 1000:
            with state_lock:
                drive.stop()
                last_drive_at = 0
            return jsonify(ok=True, expired=True, sequence=sequence), 409
        with state_lock:
            if sequence and sequence <= drive_sequences.get(session, -1):
                return jsonify(ok=True, stale=True, sequence=sequence)
            if sequence:
                drive_sequences[session] = sequence
                if len(drive_sequences) > 64:
                    drive_sequences.pop(next(iter(drive_sequences)))
            try:
                drive.drive(forward, strafe, rotate, speed)
            except ValueError as error:
                return jsonify(error=str(error)), 400
            last_drive_at = time.monotonic()
        return jsonify(ok=True, sequence=sequence)

    @app.post("/api/stop")
    def command_stop():
        global last_drive_at
        with state_lock:
            drive.stop()
            last_drive_at = 0
        return jsonify(ok=True)

    @app.get("/api/scouts/<scout_id>/status")
    def scout_status(scout_id: str):
        if scout_id not in SCOUTS:
            return jsonify(error="Unknown scout"), 404
        heartbeat = scout_registry.snapshot(scout_id)
        camera_heartbeat = camera_registry.snapshot(scout_id)
        if heartbeat is None:
            return jsonify(
                online=False,
                connected=False,
                name=SCOUTS[scout_id]["name"],
                host=SCOUTS[scout_id]["host"],
                heartbeat=None,
                camera=camera_heartbeat,
            )
        try:
            status_data = _scout_request(scout_id, "/status")
            status_data["online"] = True
            status_data["connected"] = True
            status_data["host"] = scout_registry.host_for(scout_id, SCOUTS[scout_id]["host"])
            status_data["heartbeat"] = heartbeat
            status_data["camera"] = camera_heartbeat
            return jsonify(status_data)
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as error:
            return jsonify(
                online=False,
                connected=heartbeat is not None,
                name=SCOUTS[scout_id]["name"],
                host=heartbeat["ip"] if heartbeat else SCOUTS[scout_id]["host"],
                heartbeat=heartbeat,
                camera=camera_heartbeat,
                error=str(error),
            )

    @app.route("/api/scouts/register", methods=["GET", "POST"])
    def register_scout():
        payload = request.get_json(silent=True) or request.args
        scout_id = str(payload.get("id", "")).lower()
        if scout_id not in SCOUTS:
            return jsonify(error="Scout id must be A or B"), 400
        try:
            rssi = int(payload["rssi"]) if payload.get("rssi") not in (None, "") else None
            uptime_ms = int(payload["uptime_ms"]) if payload.get("uptime_ms") not in (None, "") else None
        except (TypeError, ValueError):
            return jsonify(error="Invalid Scout telemetry"), 400
        remote_ip = request.remote_addr or ""
        heartbeat = scout_registry.record(scout_id, remote_ip, rssi, uptime_ms, "http")
        heartbeat.pop("last_seen", None)
        return jsonify(
            ok=True,
            registered=True,
            id=scout_id.upper(),
            dashboard="http://10.42.0.1",
            heartbeat=heartbeat,
        )

    @app.route("/api/cameras/register", methods=["GET", "POST"])
    def register_camera():
        """Record an ESP32-CAM by the DHCP address that actually reached the Pi."""
        payload = request.get_json(silent=True) or request.args
        camera_id = str(payload.get("id", "")).lower()
        if camera_id not in SCOUTS:
            return jsonify(error="Camera id must be A or B"), 400
        try:
            rssi = int(payload["rssi"]) if payload.get("rssi") not in (None, "") else None
            uptime_ms = int(payload["uptime_ms"]) if payload.get("uptime_ms") not in (None, "") else None
        except (TypeError, ValueError):
            return jsonify(error="Invalid camera telemetry"), 400
        remote_ip = request.remote_addr or ""
        heartbeat = camera_registry.record(camera_id, remote_ip, rssi, uptime_ms)
        heartbeat.pop("last_seen", None)
        return jsonify(
            ok=True,
            registered=True,
            id=camera_id.upper(),
            dashboard="http://10.42.0.1",
            stream=url_for("scout_camera_feed", scout_id=camera_id),
            heartbeat=heartbeat,
        )

    @app.post("/api/scouts/<scout_id>/drive")
    def scout_drive(scout_id: str):
        if scout_id not in SCOUTS:
            return jsonify(error="Unknown scout"), 404
        payload = request.get_json(silent=True) or {}
        heartbeat = scout_registry.snapshot(scout_id)
        if heartbeat is None:
            return jsonify(error=f"{SCOUTS[scout_id]['name']} has no current heartbeat"), 409
        try:
            x = float(payload.get("x", 0))
            y = float(payload.get("y", 0))
            speed = float(payload.get("speed", 35))
            sequence = int(payload.get("sequence", 0))
            session = str(payload.get("session", "legacy"))[:64]
            expires_at_ms = int(payload["expires_at_ms"])
            if not all(math.isfinite(value) for value in (x, y, speed)):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return jsonify(error="Scout drive values must be finite numbers"), 400
        server_now_ms = round(time.time() * 1000)
        if expires_at_ms < server_now_ms or expires_at_ms > server_now_ms + 1000:
            return jsonify(ok=True, expired=True, sequence=sequence), 409
        query = {
            "x": round(max(-100, min(100, x))),
            "y": round(max(-100, min(100, y))),
            "speed": round(max(0, min(100, speed))),
        }
        last_scout_motion_at[scout_id] = (
            time.monotonic() if query["speed"] > 0 and (query["x"] or query["y"]) else 0.0
        )
        with scout_command_locks[scout_id]:
            sequence_key = (scout_id, session)
            if sequence and sequence <= scout_sequences.get(sequence_key, -1):
                return jsonify(ok=True, stale=True, sequence=sequence)
            if sequence:
                scout_sequences[sequence_key] = sequence
                if len(scout_sequences) > 128:
                    scout_sequences.pop(next(iter(scout_sequences)))
            try:
                result = _scout_request(scout_id, "/drive", query)
                result.update(sequence=sequence)
                return jsonify(result)
            except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as error:
                return jsonify(error=f"{SCOUTS[scout_id]['name']} is unreachable: {error}"), 502

    @app.post("/api/scouts/<scout_id>/stop")
    def scout_stop(scout_id: str):
        if scout_id not in SCOUTS:
            return jsonify(error="Unknown scout"), 404
        last_scout_motion_at[scout_id] = 0.0
        if scout_registry.snapshot(scout_id) is None:
            return jsonify(ok=True, connected=False)
        try:
            result = _scout_request(scout_id, "/stop")
            return jsonify(result)
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as error:
            return jsonify(error=f"{SCOUTS[scout_id]['name']} is unreachable: {error}"), 502

    @app.get("/healthz")
    def health():
        return jsonify(ok=True)

    return app


def _watchdog() -> None:
    global last_drive_at
    while not shutdown_event.wait(0.05):
        with state_lock:
            expired = last_drive_at and time.monotonic() - last_drive_at > WATCHDOG_SECONDS
            if expired:
                last_drive_at = 0
                drive.stop()


def cleanup() -> None:
    shutdown_event.set()
    drive.close()
    camera.close()
    vision.close()
    scout_registry.close()


threading.Thread(target=_watchdog, name="motor-watchdog", daemon=True).start()
atexit.register(cleanup)
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), threaded=True)
