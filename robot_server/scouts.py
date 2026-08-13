"""UDP heartbeat discovery for LARP scouts on the 3TSahur hotspot."""

from __future__ import annotations

import json
import socket
import threading
import time


class ScoutRegistry:
    def __init__(self, port: int = 5006, max_age: float = 12.0) -> None:
        self.port = port
        self.max_age = max_age
        self._records: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.error: str | None = None
        self._thread = threading.Thread(target=self._listen, name="scout-heartbeats", daemon=True)
        self._thread.start()

    def _listen(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.settimeout(0.5)
        try:
            listener.bind(("0.0.0.0", self.port))
            while not self._stop.is_set():
                try:
                    payload, address = listener.recvfrom(1024)
                    data = json.loads(payload.decode("utf-8"))
                    scout_id = str(data.get("id", "")).lower()
                    if scout_id not in ("a", "b"):
                        continue
                    self.record(scout_id, address[0], data.get("rssi"), data.get("uptime_ms"), "udp")
                except socket.timeout:
                    continue
                except (UnicodeDecodeError, ValueError, OSError):
                    continue
        except OSError as error:
            self.error = str(error)
        finally:
            listener.close()

    def record(
        self,
        scout_id: str,
        ip: str,
        rssi: int | None = None,
        uptime_ms: int | None = None,
        transport: str = "http",
    ) -> dict:
        """Record a verified heartbeat received from a Scout."""
        normalized_id = str(scout_id).lower()
        if normalized_id not in ("a", "b"):
            raise ValueError("Scout id must be A or B")
        record = {
            "id": normalized_id,
            "ip": ip,
            "last_seen": time.monotonic(),
            "rssi": rssi,
            "uptime_ms": uptime_ms,
            "transport": transport,
        }
        with self._lock:
            self._records[normalized_id] = record
        return dict(record)

    def snapshot(self, scout_id: str) -> dict | None:
        with self._lock:
            record = self._records.get(scout_id)
            if not record:
                return None
            result = dict(record)
        age = time.monotonic() - result["last_seen"]
        if age > self.max_age:
            return None
        result["age_ms"] = round(age * 1000)
        return result

    def host_for(self, scout_id: str, fallback: str) -> str:
        record = self.snapshot(scout_id)
        return record["ip"] if record else fallback

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)


class CameraRegistry:
    """Recent HTTP registrations from the independently-addressed ESP32-CAMs."""

    def __init__(self, max_age: float = 15.0) -> None:
        self.max_age = max_age
        self._records: dict[str, dict] = {}
        self._lock = threading.Lock()

    def record(
        self,
        camera_id: str,
        ip: str,
        rssi: int | None = None,
        uptime_ms: int | None = None,
    ) -> dict:
        normalized_id = str(camera_id).lower()
        if normalized_id not in ("a", "b"):
            raise ValueError("Camera id must be A or B")
        record = {
            "id": normalized_id,
            "ip": ip,
            "last_seen": time.monotonic(),
            "rssi": rssi,
            "uptime_ms": uptime_ms,
            "transport": "http",
        }
        with self._lock:
            self._records[normalized_id] = record
        return dict(record)

    def snapshot(self, camera_id: str) -> dict | None:
        with self._lock:
            record = self._records.get(camera_id)
            if not record:
                return None
            result = dict(record)
        age = time.monotonic() - result["last_seen"]
        if age > self.max_age:
            return None
        result["age_ms"] = round(age * 1000)
        return result

    def stream_url(self, camera_id: str, fallback: str) -> str:
        """Prefer a camera's current DHCP address over mDNS or a static override."""
        record = self.snapshot(camera_id)
        return f"http://{record['ip']}/stream" if record else fallback
