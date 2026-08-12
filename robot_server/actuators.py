"""Safe staged auxiliary-actuator state for 3TSahur.

This module intentionally has no GPIO, I2C, PWM, or servo-driver dependency.
It lets the dashboard and API be exercised before a servo driver model, power
plan, channel assignments, and mechanical limits are supplied. No physical
servo signal can be emitted by this implementation.
"""

from __future__ import annotations

import math
import threading


class ActuatorController:
    """Maintain desired gimbal/ramp state without addressing hardware."""

    PAN_MIN, PAN_MAX = -90, 90
    TILT_MIN, TILT_MAX = -45, 45
    RAMP_STATES = {"up", "down"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pan = 0
        self._tilt = 0
        self._ramp = "down"

    @staticmethod
    def _position(value: object, minimum: int, maximum: int, label: str) -> int:
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label} must be a finite number") from error
        if not math.isfinite(number):
            raise ValueError(f"{label} must be a finite number")
        return max(minimum, min(maximum, round(number)))

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "configured": False,
                "hardware": False,
                "reason": (
                    "Servo driver model, power plan, channels, and calibrated limits "
                    "are not configured. No servo output is active."
                ),
                "gimbal": {
                    "pan": self._pan,
                    "tilt": self._tilt,
                    "pan_limits": [self.PAN_MIN, self.PAN_MAX],
                    "tilt_limits": [self.TILT_MIN, self.TILT_MAX],
                },
                "ramp": {"state": self._ramp},
            }

    def set_gimbal(self, pan: object, tilt: object) -> dict:
        pan_value = self._position(pan, self.PAN_MIN, self.PAN_MAX, "Pan")
        tilt_value = self._position(tilt, self.TILT_MIN, self.TILT_MAX, "Tilt")
        with self._lock:
            self._pan, self._tilt = pan_value, tilt_value
        return self.snapshot()

    def set_ramp(self, state: object) -> dict:
        state_value = str(state).lower()
        if state_value not in self.RAMP_STATES:
            raise ValueError("Ramp state must be 'up' or 'down'")
        with self._lock:
            self._ramp = state_value
        return self.snapshot()
