# Simulation results

Date: 2026-08-11

The integration base and the 3TSahur/LARP updates were compiled with Python.
All 41 hardware-independent tests passed in an isolated desktop virtual
environment with the repository's Flask dependency installed.

| Group | Checks | Result |
| --- | ---: | --- |
| `test_dashboard_ui.py` | per-robot tabs, lazy MJPEG stream loading, CSI presence display, keyboard tab controls, and non-overlap layout | pass |
| `test_motor.py` | mecanum mixing, normalization, reversal dead-time, and confirmed GPIO/PWM mapping | pass |
| `test_camera.py` | C270 V4L2 discovery ordering | pass |
| `test_firmware.py` | LARP reconnect behavior, CSI status fields, capped camera stream rate, firmware settings, and installer invariants | pass |
| `test_scouts.py` | heartbeat registry handling | pass |
| `test_server.py` | hub API, expiry/sequence safety, dashboard, and scout proxy behavior | pass |

The test harness uses fake GPIO/PWM implementations and mocked network/camera
interfaces. It verifies the partner-base forward pins `5, 16, 20, 13` and
reverse pins `6, 19, 21, 26` for the four mecanum wheels.

## Control-path timing simulation

Using the Flask test client and simulated GPIO/network interfaces, 100 current
3TSahur drive commands averaged **0.135 ms** per request (95th percentile
**0.161 ms**, maximum **1.711 ms**). One hundred immediate LARP proxy commands
averaged **0.125 ms** (95th percentile **0.166 ms**, maximum **0.273 ms**).

This confirms the dashboard/API control path does not contain a multi-second
software queue. It does not measure physical motor response or real radio
latency. The dashboard's one-active-camera policy and the ESP32-CAM 10 FPS cap
are intended to prevent the prior hotspot video congestion from delaying those
small command packets.

Not simulated: physical motor direction/current, C270 USB capture, real Wi-Fi
radio behavior, ECHO motor IDs, Inland ESP32-CAM pin map, and Arduino upload.
Those require the actual hardware and must be performed using the raised-wheel
procedure in the setup guide.
