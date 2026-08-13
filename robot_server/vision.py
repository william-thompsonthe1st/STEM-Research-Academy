"""Optional, failure-isolated YOLO inference for the dashboard.

This module deliberately imports neither OpenCV nor Ultralytics until a user
enables vision. All inference happens on one daemon thread and never in a
Flask route or a motor-control path.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable


class VisionManager:
    """Run pretrained person detection without making control depend on it."""

    def __init__(
        self,
        sources: dict[str, Callable[[], object | None]],
        should_pause: Callable[[], bool] | None = None,
    ) -> None:
        self._sources = sources
        # A source can be an MJPEG request to an ESP32-CAM.  While an operator
        # is driving, that traffic is optional and must not compete with the
        # short control-heartbeat path.
        self._should_pause = should_pause or (lambda: False)
        self._enabled = {source: False for source in sources}
        self._states = {source: self._new_state() for source in sources}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._model = None
        self._model_error: str | None = None
        self.interval = max(0.2, float(os.environ.get("VISION_INTERVAL_SECONDS", "0.5")))
        self.confidence = float(os.environ.get("VISION_CONFIDENCE", "0.45"))
        self.image_size = int(os.environ.get("VISION_IMAGE_SIZE", "320"))
        self.model_path = os.environ.get("VISION_MODEL", "yolo11n_ncnn_model")

    @staticmethod
    def _new_state() -> dict:
        return {"enabled": False, "available": None, "error": None, "detections": [], "updated_at_ms": None, "frame_width": 0, "frame_height": 0}

    def snapshot(self, source: str) -> dict:
        with self._lock:
            if source not in self._states:
                raise KeyError(source)
            return dict(self._states[source], detections=list(self._states[source]["detections"]))

    def set_enabled(self, source: str, enabled: bool) -> dict:
        with self._lock:
            if source not in self._states:
                raise KeyError(source)
            self._enabled[source] = enabled
            state = self._states[source]
            state["enabled"] = enabled
            if not enabled:
                state.update(available=None, error=None, detections=[])
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="optional-yolo", daemon=True)
                self._thread.start()
        self._wake.set()
        return self.snapshot(source)

    def _load_model(self):
        if self._model is not None:
            return self._model
        if self._model_error:
            raise RuntimeError(self._model_error)
        try:
            from ultralytics import YOLO  # type: ignore
            self._model = YOLO(self.model_path)
            return self._model
        except Exception as error:
            self._model_error = f"YOLO unavailable: {error}"
            raise RuntimeError(self._model_error) from error

    def _run_one(self, source: str) -> None:
        try:
            import cv2  # type: ignore
            frame = self._sources[source]()
            if frame is None:
                raise RuntimeError("No camera frame available")
            if isinstance(frame, bytes):
                frame = cv2.imdecode(__import__("numpy").frombuffer(frame, dtype="uint8"), cv2.IMREAD_COLOR)
            if frame is None:
                raise RuntimeError("Camera frame could not be decoded")
            model = self._load_model()
            result = model(frame, classes=[0], conf=self.confidence, imgsz=self.image_size, verbose=False)[0]
            height, width = frame.shape[:2]
            detections = []
            for box in result.boxes:
                x1, y1, x2, y2 = (round(float(value), 1) for value in box.xyxy[0].tolist())
                detections.append({"label": "person", "confidence": round(float(box.conf[0]), 3), "x1": x1, "y1": y1, "x2": x2, "y2": y2})
            with self._lock:
                self._states[source].update(available=True, error=None, detections=detections, updated_at_ms=round(time.time() * 1000), frame_width=width, frame_height=height)
        except Exception as error:
            with self._lock:
                self._states[source].update(available=False, error=str(error), detections=[], updated_at_ms=round(time.time() * 1000))

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                active = [source for source, enabled in self._enabled.items() if enabled]
            if not active:
                self._wake.wait(timeout=1)
                self._wake.clear()
                continue
            if self._should_pause():
                self._wake.wait(timeout=0.1)
                self._wake.clear()
                continue
            for source in active:
                if self._stop.is_set() or self._should_pause():
                    break
                self._run_one(source)
            self._wake.wait(timeout=self.interval)
            self._wake.clear()

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=1)
