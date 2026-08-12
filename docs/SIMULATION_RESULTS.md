# Simulation results

Date: 2026-08-11

The integration base and the 3TSahur/LARP updates were compiled with Python.
All 39 hardware-independent tests passed in an isolated desktop virtual
environment with the repository's Flask dependency installed.

| Group | Checks | Result |
| --- | ---: | --- |
| `test_dashboard_ui.py` | per-robot tabs, lazy MJPEG stream loading, keyboard tab controls, and non-overlap layout | pass |
| `test_motor.py` | mecanum mixing, normalization, reversal dead-time, and confirmed GPIO/PWM mapping | pass |
| `test_camera.py` | C270 V4L2 discovery ordering | pass |
| `test_firmware.py` | LARP reconnect behavior, capped camera stream rate, firmware settings, and installer invariants | pass |
| `test_scouts.py` | heartbeat registry handling | pass |
| `test_server.py` | hub API, expiry/sequence safety, dashboard, and scout proxy behavior | pass |

The test harness uses fake GPIO/PWM implementations and mocked network/camera
interfaces. It verifies the partner-base forward pins `5, 16, 20, 13` and
reverse pins `6, 19, 21, 26` for the four mecanum wheels.

Not simulated: physical motor direction/current, C270 USB capture, real Wi-Fi
radio behavior, ECHO motor IDs, Inland ESP32-CAM pin map, and Arduino upload.
Those require the actual hardware and must be performed using the raised-wheel
procedure in the setup guide.
