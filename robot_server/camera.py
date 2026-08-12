"""Background capture and MJPEG encoding for a USB webcam."""

from __future__ import annotations

import glob
import os
import threading
import time


class CameraStream:
    def __init__(self, device: str = "auto", width: int = 640, height: int = 480, fps: int = 10) -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self._condition = threading.Condition()
        self._frame: bytes | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self.error: str | None = None
        self.selected_device: str | None = None

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
        with self._condition:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._capture, name="usb-camera", daemon=True)
            self._thread.start()

    def _capture(self) -> None:
        camera = None
        try:
            import cv2  # type: ignore

            first_frame = None
            attempted: list[str] = []
            for device in self._candidate_devices():
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
                    ok, image = candidate.read()
                    if ok and image is not None:
                        camera = candidate
                        first_frame = image
                        self.selected_device = os.path.realpath(device)
                        break
                    time.sleep(0.1)
                if camera is not None:
                    break
                candidate.release()

            if camera is None:
                tried = ", ".join(attempted) if attempted else "no /dev/video devices found"
                raise RuntimeError(f"Could not capture from Logitech webcam ({tried})")

            frame_interval = 1 / max(1, self.fps)
            next_frame_at = time.monotonic()
            failed_reads = 0
            while self._running:
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
                ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 65])
                if ok:
                    with self._condition:
                        self._frame = encoded.tobytes()
                        self.error = None
                        self._condition.notify_all()
                next_frame_at += frame_interval
                delay = next_frame_at - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_frame_at = time.monotonic()
        except Exception as error:  # Camera errors must not take down motor control.
            self.error = str(error)
        finally:
            if camera is not None:
                camera.release()
            self._running = False

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
        return self._frame is not None and self.error is None

    def close(self) -> None:
        self._running = False
        with self._condition:
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
