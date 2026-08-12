# Simulation results

Date: 2026-08-11

The integration base was compiled with Python and the following
hardware-independent test groups were executed successfully (18 tests total):

| Group | Checks | Result |
| --- | ---: | --- |
| `test_motor.py` | mecanum mixing, normalization, reversal dead-time, confirmed GPIO/PWM mapping | pass |
| `test_camera.py` | C270 V4L2 discovery ordering | pass |
| `test_firmware.py` | LARP drive/camera firmware and installer invariants | pass |
| `test_scouts.py` | heartbeat registry handling | pass |
| `test_server.py` | hub API, expiry/sequence safety, dashboard, scout proxy behavior | not run locally — Flask unavailable in desktop runtime |

The test harness uses fake GPIO/PWM implementations and mocked network/camera
interfaces. It verifies the partner-base forward pins `5, 16, 20, 13` and reverse
pins `6, 19, 21, 26` for the four wheels.

The unexecuted Flask route tests are included in the repository and can be run
on the Pi after the installer installs Flask. This desktop sandbox does not bundle
Flask and blocks temporary package installation; that is an environment limit,
not a test failure in the project code.

Not simulated: physical motor direction/current, C270 USB capture, real Wi-Fi
radio behavior, ECHO motor IDs, Inland ESP32-CAM pin map, and Arduino upload.
Those require the actual hardware and must be performed using the raised-wheel
procedure in the setup guide.
