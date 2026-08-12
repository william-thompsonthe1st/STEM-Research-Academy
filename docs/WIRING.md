# 3TSahur motor wiring

The 3TSahur mecanum chassis uses two DC 3–18 V, 10 A dual H-bridge motor
drivers. This table intentionally matches the partner repository's original
mecanum assignment. All numbers below are Raspberry Pi **BCM GPIO** numbers.

| Wheel | Driver input pair | Forward | Reverse |
| --- | --- | ---: | ---: |
| Front left | Driver 1 IN1 / IN2 | GPIO 5 | GPIO 6 |
| Rear left | Driver 1 IN3 / IN4 | GPIO 16 | GPIO 19 |
| Front right | Driver 2 IN1 / IN2 | GPIO 20 | GPIO 21 |
| Rear right | Driver 2 IN3 / IN4 | GPIO 13 | GPIO 26 |

This is encoded in `robot_server/motor.py` and tested in
`tests/test_motor.py`. Do not connect one GPIO to more than one driver input:
independent channels are required for mecanum strafe and rotation.

Before the first ground test, connect all logic and motor grounds, power motors
from their rated external supply, add a suitable fuse/power switch, and test
each direction with all wheels raised. If one wheel is physically reversed,
reverse only that motor's leads or swap only its `MotorPins` pair in code.
