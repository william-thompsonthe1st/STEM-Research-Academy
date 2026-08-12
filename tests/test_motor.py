import unittest
from unittest.mock import patch

from robot_server.motor import MecanumDrive


class FakePWM:
    def __init__(self):
        self.duty = None
        self.running = False

    def start(self, duty):
        self.duty = duty
        self.running = True

    def ChangeDutyCycle(self, duty):
        self.duty = duty

    def stop(self):
        self.running = False


class FakeGPIO:
    BCM = "BCM"
    OUT = "OUT"
    LOW = 0

    def __init__(self):
        self.pwms = {}

    def setwarnings(self, _enabled):
        pass

    def setmode(self, _mode):
        pass

    def setup(self, _pin, _mode, initial=0):
        pass

    def PWM(self, pin, _frequency):
        self.pwms[pin] = FakePWM()
        return self.pwms[pin]

    def output(self, _pins, _value):
        pass

    def cleanup(self):
        pass


class MecanumMixTests(unittest.TestCase):
    def test_forward_moves_every_wheel_forward(self):
        self.assertEqual(
            MecanumDrive.mix(1, 0, 0),
            {"front_left": 1, "front_right": 1, "rear_left": 1, "rear_right": 1},
        )

    def test_strafe_uses_opposite_diagonals(self):
        self.assertEqual(
            MecanumDrive.mix(0, 1, 0),
            {"front_left": 1, "front_right": -1, "rear_left": -1, "rear_right": 1},
        )

    def test_combined_commands_are_normalized(self):
        result = MecanumDrive.mix(1, 1, 1)
        self.assertLessEqual(max(abs(value) for value in result.values()), 1)
        self.assertEqual(result["front_left"], 1)

    def test_supplied_forward_pin_directions(self):
        gpio = FakeGPIO()
        drive = MecanumDrive(gpio_module=gpio)
        drive.drive(1, 0, 0, 0.75)
        for forward_pin in (5, 16, 20, 26):
            self.assertEqual(gpio.pwms[forward_pin].duty, 75)
        for reverse_pin in (6, 19, 21, 13):
            self.assertFalse(gpio.pwms[reverse_pin].running)
        self.assertEqual(sum(pwm.running for pwm in gpio.pwms.values()), 4)
        drive.close()

    def test_full_reversal_uses_one_shared_deadtime(self):
        gpio = FakeGPIO()
        drive = MecanumDrive(gpio_module=gpio)
        drive.drive(1, 0, 0, 0.75)
        with patch("robot_server.motor.time.sleep") as sleep:
            drive.drive(-1, 0, 0, 0.75)
        sleep.assert_called_once_with(0.015)
        self.assertEqual(sum(pwm.running for pwm in gpio.pwms.values()), 4)
        drive.close()


if __name__ == "__main__":
    unittest.main()
