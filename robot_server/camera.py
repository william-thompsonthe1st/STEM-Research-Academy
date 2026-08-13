"""Background capture and MJPEG encoding for a USB webcam."""

from __future__ import annotations

import glob
import os
import threading
import time
from pathlib import Path


class CameraStream:
    def __init__(self, device: str = "auto", width: int = 640, height: int = 480, fps: int = 10) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self._condition = threading.Condition()
        self._lifecycle_lock = threading.RLock()
        self._frame: bytes | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._generation = 0
        self.error: str | None = None
        self.selected_device: str | None = None
        self.camera_name = "USB camera"
        self.capture_width: int | None = None
        self.capture_height: int | None = None
        self.capture_fps: int | None = None
        self.last_frame_at: float | None = None
        self.restart_count = 0

    @staticmethod
    def _camera_name(device: str) -> str:
        """Return the V4L2 model name without assuming one Logitech model."""
        persistent_name = device.replace("\\", "/").rsplit("/", 1)[-1]
        if persistent_name.startswith("usb-"):
            persistent_name = persistent_name[4:].split("-video-index", 1)[0]
            parts = persistent_name.split("_", 1)
            if len(parts) == 2 and all(character in "0123456789abcdefABCDEF" for character in parts[0]):
                persistent_name = parts[1]
            return persistent_name.replace("_", " ").strip() or "USB camera"

        video_node = os.path.realpath(device).replace("\\", "/").rsplit("/", 1)[-1]
        try:
            name = (Path("/sys/class/video4linux") / video_node / "name").read_text(encoding="utf-8").strip()
            if name:
                return name
        except OSError:
            pass
        return "USB camera"

    def _candidate_devices(self) -> list[str]:
        """Return capture candidates with Logitech/by-id devices first."""
        candidates: list[str] = []
        if self.device and self.device.lower() != "auto":
            candidates.append(self.device)

        persistent = glob.glob("/dev/v4l/by-id/*-video-index0")
        persistent.sort(key=lambda path: ("c270" not in path.lower() and "logitech" not in path.lower(), path))
        candidates.extend(persistent)
        candidates.extend(sorted(glob.glob("/dev/video*")))

        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            resolved = os.path.realpath(candidate)
            if resolved not in seen:
                seen.add(resolved)
                unique.append(candidate)
        return unique

    def start(self) -> None:
        with self._lifecycle_lock:
            with self._condition:
                if self._running:
                    return
                self._running = True
                self._generation += 1
                generation = self._generation
                self._thread = threading.Thread(
                    target=self._capture, args=(generation,), name="usb-camera", daemon=True
                )
                self._thread.start()

    def _active(self, generation: int) -> bool:
        return self._running and generation == self._generation

    def _capture(self, generation: int | None = None) -> None:
        """Supervise capture so a USB disconnect recovers without a restart."""
        generation = self._generation if generation is None else generation
        retry_delay = 1.0
        while self._active(generation):
            try:
                self._capture_once(generation)
                retry_delay = 1.0
            except Exception as error:  # Camera errors must not take down motor control.
                if not self._active(generation):
                    break
                with self._condition:
                    self.error = str(error)
                    self.restart_count += 1
                    self._condition.notify_all()
                if not self._active(generation):
                    break
                # An interruptible wait keeps shutdown and profile changes quick.
                with self._condition:
                    self._condition.wait(timeout=retry_delay)
                retry_delay = min(5.0, retry_delay * 2)

    def _capture_once(self, generation: int) -> None:
        """Open a usable V4L2 node and capture until it fails or is stopped."""
        camera = None
        try:
            import cv2  # type: ignore

            first_frame = None
            attempted: list[str] = []
            for device in self._candidate_devices():
                if not self._active(generation):
                    return
                attempted.append(device)
                source = int(device) if device.isdigit() else device
                candidate = cv2.VideoCapture(source, cv2.CAP_V4L2)
                if not candidate.isOpened():
                    candidate.release()
                    continue
                candidate.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                candidate.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                candidate.set(cv2.CAP_PROP_FPS, self.fps)
                # The C270 may need a short USB exposure warm-up. A metadata
                # V4L2 node can open successfully but will never return a frame,
                # so prove capture before selecting the node.
                for _ in range(15):
                    if not self._active(generation):
                        break
                    ok, image = candidate.read()
                    if ok and image is not None:
                        if not self._active(generation):
                            break
                        camera = candidate
                        first_frame = image
                        self.selected_device = os.path.realpath(device)
                        self.camera_name = self._camera_name(device)
                        self.capture_width = int(image.shape[1])
                        self.capture_height = int(image.shape[0])
                        reported_fps = round(float(candidate.get(cv2.CAP_PROP_FPS)))
                        self.capture_fps = reported_fps if reported_fps > 0 else self.fps
                        break
                    time.sleep(0.1)
                if camera is not None:
                    break
                candidate.release()

            if camera is None:
                if not self._active(generation):
                    return
                tried = ", ".join(attempted) if attempted else "no /dev/video devices found"
                raise RuntimeError(f"Could not capture from Logitech webcam ({tried})")

            frame_interval = 1 / max(1, self.fps)
            next_frame_at = time.monotonic()
            failed_reads = 0
            while self._active(generation):
                if first_frame is not None:
                    ok, image = True, first_frame
                    first_frame = None
                else:
                    ok, image = camera.read()
                if not ok:
                    self.error = "Camera stopped returning frames"
                    failed_reads += 1
                    if failed_reads >= 10:
                        raise RuntimeError("Camera stopped returning frames; reconnecting")
                    time.sleep(0.2)
                    continue
                failed_reads = 0
                if not self._active(generation):
                    break
                ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 65])
                if ok:
                    with self._condition:
                        if not self._active(generation):
                            break
                        self._frame = encoded.tobytes()
                        self.error = None
                        self.last_frame_at = time.monotonic()
                        self._condition.notify_all()
                next_frame_at += frame_interval
                delay = next_frame_at - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_frame_at = time.monotonic()
        finally:
            if camera is not None:
                camera.release()

    def frames(self):
        self.start()
        last_frame = None
        while self._running:
            with self._condition:
                self._condition.wait_for(lambda: self._frame is not None and self._frame is not last_frame, timeout=2)
                frame = self._frame
            if frame is None:
                continue
            last_frame = frame
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"

    @property
    def available(self) -> bool:
        return self._frame is not None and self.error is None and self.frame_age_seconds < 3.0

    @property
    def frame_age_seconds(self) -> float:
        if self.last_frame_at is None:
            return float("inf")
        return max(0.0, time.monotonic() - self.last_frame_at)

    def latest_jpeg(self) -> bytes | None:
        """Return the newest captured frame without opening a second webcam."""
        with self._condition:
            return self._frame

    def configure(self, width: int, height: int, fps: int) -> None:
        """Apply a profile by restarting only the camera capture worker."""
        if not (160 <= width <= 1920 and 120 <= height <= 1080 and 1 <= fps <= 30):
            raise ValueError("Unsupported camera profile")
        with self._lifecycle_lock:
            was_running = self._running
            self.close()
            with self._condition:
                self.width, self.height, self.fps = width, height, fps
                self._frame = None
                self.last_frame_at = None
                self.error = None
                self.selected_device = None
                self.camera_name = "USB camera"
                self.capture_width = None
                self.capture_height = None
                self.capture_fps = None
            if was_running:
                self.start()

    def close(self) -> None:
        with self._lifecycle_lock:
            with self._condition:
                self._running = False
                self._generation += 1
                self._condition.notify_all()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2)
