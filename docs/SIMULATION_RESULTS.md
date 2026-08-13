# Simulation results

Date: 2026-08-12

The integration base and the 3TSahur/LARP updates were checked with the
repository's hardware-independent Python test suite. Firmware source was also
verified in Arduino against the actual ECHO and Inland board profiles; see
**Arduino firmware verification** below.

The current suite completed with **77 passing tests**.

| Group | Checks | Result |
| --- | ---: | --- |
| `test_dashboard_ui.py` | per-robot tabs, lazy MJPEG streams, CSI, vision controls, mission tools, profiles, health panel, non-overlap layout, and static lightweight UI-refresh guard | pass |
| `test_motor.py` | mecanum mixing, normalization, reversal dead-time, and confirmed GPIO/PWM mapping | pass |
| `test_camera.py` | C270 V4L2 discovery ordering | pass |
| `test_firmware.py` | LARP reconnect behavior, CSI status fields, capped camera stream rate, firmware settings, and installer invariants | pass |
| `test_scouts.py` | heartbeat registry handling | pass |
| `test_server.py` | hub API, expiry/sequence safety, profile/control isolation, timeline, snapshot failure handling, dashboard, and scout proxy behavior | pass |
| `test_swarm_compatibility.py` | simultaneous 3TSahur, LARP A, and LARP B route compatibility plus local control-path queue check | pass |

The test harness uses fake GPIO/PWM implementations and mocked network/camera
interfaces. It verifies the partner-base forward pins `5, 16, 20, 13` and
reverse pins `6, 19, 21, 26` for the four mecanum wheels.

## Arduino firmware verification

On 2026-08-12, the two LARP sketches were verified with `esp32 by Espressif
Systems 3.0.7`:

| Firmware | Arduino board profile | Result |
| --- | --- | --- |
| `firmware/larp-scout/larp-scout.ino` | `ESP32S3 Dev Module` | verified; 985,601 bytes flash (75%), 45,704 bytes RAM (13%) |
| `firmware/larp-esp32-cam/larp-esp32-cam.ino` | `AI Thinker ESP32-CAM` | verified; 1,057,281 bytes flash (33%), 51,580 bytes RAM (15%) |

The ECHO verification used EchoLib 1.3.0 and Adafruit BusIO. The primary
`.ino` names now match their sketch directories, eliminating Arduino's
pre-compile `main file missing from sketch` fatal error. This validation checks
the code and board definitions; a physical upload still requires the correct
USB/bootloader procedure on each actual board.

The merged performance path also avoids rewriting unchanged Pi or LARP motor
outputs for held dashboard commands while continuing to refresh each watchdog.
This keeps the HTTP, Wi-Fi, CSI, and dashboard control loop available without
changing the control API or timeout behavior.

## Control-path timing simulation

Using the Flask test client and simulated GPIO/network interfaces, 100 current
3TSahur drive commands averaged **0.131 ms** per request (95th percentile
**0.171 ms**, maximum **1.562 ms**). One hundred immediate LARP proxy commands
averaged **0.125 ms** (95th percentile **0.166 ms**, maximum **0.273 ms**).

This confirms the dashboard/API control path does not contain a multi-second
software queue. It does not measure physical motor response or real radio
latency. The dashboard's one-active-camera policy and the ESP32-CAM 10 FPS cap
are intended to prevent the prior hotspot video congestion from delaying those
small command packets.

The latest feature pass also ran a camera-profile update immediately followed
by a current drive command. The profile response and subsequent drive command
both passed in the simulated environment. This verifies route separation, not
the physical C270's reopen time; changing a profile should therefore be done
while stationary.

## Three-robot compatibility and timing check

The current compatibility pass registered both LARPs with distinct simulated
hotspot addresses, then sent one current 3TSahur mecanum command, one LARP A
drive command, and one LARP B drive command. Both LARP status routes returned
successfully and the 3TSahur motor state remained current. This exercises the
same dashboard API routes that the three tabs use, with scout HTTP calls mocked
to remove physical radio variation.

After the UI refresh, 100 repeated composite cycles, each containing one
current 3TSahur command and one command for each LARP, averaged **0.406 ms**
per cycle, with a **0.571 ms** 95th percentile and **2.490 ms** maximum. The
compatibility test also asserts a 50 ms local ceiling across repeated Pi/LARP
requests, so a new local request queue cannot silently reintroduce multi-second
delays.

The UI refresh changes only HTML/CSS presentation and one regression test. It
does not alter the dashboard JavaScript, HTTP endpoints, control timer rates,
camera-stream behavior, motor mixer, watchdog, firmware, or network settings.
It adds no dependencies or background tasks and removes the previous CSS camera
filter and `backdrop-filter` panel effect.

This confirms software compatibility and the absence of a local API backlog;
it does **not** measure the Pi's hotspot airtime, 2.4 GHz interference, ESP32
processing, servo behavior, battery voltage drop, or actual motor response.
Use [the field information checklist](FIELD_INFORMATION_CHECKLIST.md) and the
raised-wheel connection test before declaring the system field-ready.

Not simulated: physical motor direction/current, C270 USB capture, real Wi-Fi
radio behavior, ECHO motor IDs, Inland ESP32-CAM pin map, and Arduino upload.
Those require the actual hardware and must be performed using the raised-wheel
procedure in the setup guide.
