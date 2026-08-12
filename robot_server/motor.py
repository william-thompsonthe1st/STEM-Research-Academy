"""Fail-safe four-wheel mecanum drive control for Raspberry Pi GPIO."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class MotorPins:
    forward: int
    reverse: int


# BCM numbering. Driver 1 controls the front axle and Driver 2 controls the
# rear axle. Do not share a GPIO input between driver boards.
DEFAULT_MOTOR_PINS = {
    "front_left": MotorPins(5, 6),       # Driver 1, Motor A
    "front_right": MotorPins(16, 19),    # Driver 1, Motor B
    "rear_left": MotorPins(20, 21),      # Driver 2, Motor A
    "rear_right": MotorPins(26, 13),     # Driver 2, Motor B
}


class _Motor:
    def __init__(self, gpio, pins: MotorPins, frequency: int) -> None:
        self.gpio = gpio
        self.pins = pins
        for pin in (pins.forward, pins.reverse):
            gpio.setup(pin, gpio.OUT, initial=gpio.LOW)
        self.forward_pwm = gpio.PWM(pins.forward, frequency)
        self.reverse_pwm = gpio.PWM(pins.reverse, frequency)
        self._active_pwm = None
        self._direction = 0

    def set(self, value: float) -> None:
        duty = min(100.0, abs(value) * 100.0)
        direction = 1 if value > 0 else -1 if value < 0 else 0
        target_pwm = self.forward_pwm if value > 0 else self.reverse_pwm if value < 0 else None
        inactive_pin = self.pins.reverse if value > 0 else self.pins.forward

        if target_pwm is not self._active_pwm:
            if self._active_pwm is not None:
                self._active_pwm.ChangeDutyCycle(0)
                self._active_pwm.stop()
            self._active_pwm = target_pwm
            if target_pwm is not None:
                self.gpio.output(inactive_pin, self.gpio.LOW)
                target_pwm.start(duty)
        elif target_pwm is not None:
            target_pwm.ChangeDutyCycle(duty)

        if target_pwm is None:
            self.gpio.output((self.pins.forward, self.pins.reverse), self.gpio.LOW)
        self._direction = direction

    def would_reverse(self, value: float) -> bool:
        direction = 1 if value > 0 else -1 if value < 0 else 0
        return bool(direction and self._direction and direction != self._direction)

    def close(self) -> None:
        self.set(0)


class MecanumDrive:
    """Mix forward, strafe, and rotation commands into four wheel speeds."""

    def __init__(self, frequency: int = 1000, gpio_module=None) -> None:
        self._lock = threading.RLock()
        self._closed = False
        self.last_command = {"forward": 0.0, "strafe": 0.0, "rotate": 0.0, "speed": 0.75}
        self.is_hardware = False
        self._gpio = gpio_module
        self._motors: dict[str, _Motor] = {}

        if self._gpio is None:
            try:
                import RPi.GPIO as GPIO  # type: ignore

                self._gpio = GPIO
            except (ImportError, RuntimeError):
                self._gpio = None

        if self._gpio is not None:
            self._gpio.setwarnings(False)
            self._gpio.setmode(self._gpio.BCM)
            self._motors = {
                name: _Motor(self._gpio, pins, frequency)
                for name, pins in DEFAULT_MOTOR_PINS.items()
            }
            self.is_hardware = True

    @staticmethod
    def mix(forward: float, strafe: float, rotate: float) -> dict[str, float]:
        wheels = {
            "front_left": forward + strafe + rotate,
            "front_right": forward - strafe - rotate,
            "rear_left": forward - strafe + rotate,
            "rear_right": forward + strafe - rotate,
        }
        scale = max(1.0, *(abs(value) for value in wheels.values()))
        return {name: value / scale for name, value in wheels.items()}

    def drive(self, forward: float, strafe: float, rotate: float, speed: float = 0.75) -> None:
        with self._lock:
            if self._closed:
                return
            values = [forward, strafe, rotate, speed]
            if any(not isinstance(value, (int, float)) for value in values):
                raise ValueError("Drive values must be numbers")
            if any(not math.isfinite(float(value)) for value in values):
                raise ValueError("Drive values must be finite")
            forward, strafe, rotate = (
                max(-1.0, min(1.0, float(value)))
                for value in (forward, strafe, rotate)
            )
            speed = max(0.0, min(1.0, float(speed)))
            mixed = self.mix(forward, strafe, rotate)
            outputs = {name: value * speed for name, value in mixed.items()}
            if any(
                self._motors[name].would_reverse(value)
                for name, value in outputs.items()
                if name in self._motors
            ):
                # Remove power from every channel once, then apply the new
                # direction. A single shared deadtime avoids four sequential
                # 15 ms sleeps during a full chassis reversal.
                for motor in self._motors.values():
                    motor.set(0)
                time.sleep(0.015)
            for name, value in outputs.items():
                if name in self._motors:
                    self._motors[name].set(value)
            self.last_command = {
                "forward": forward,
                "strafe": strafe,
                "rotate": rotate,
                "speed": speed,
            }

    def stop(self) -> None:
        self.drive(0, 0, 0, self.last_command["speed"])

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            for motor in self._motors.values():
                motor.close()
            if self._gpio is not None:
                for pins in DEFAULT_MOTOR_PINS.values():
                    self._gpio.output((pins.forward, pins.reverse), self._gpio.LOW)
                self._gpio.cleanup()
            self._closed = True
