# 3TSahur and LARP Swarm

This project controls a three-robot reconnaissance system from a Raspberry Pi
4 Model B (4 GB). **3TSahur** is the Pi-powered mecanum hub with a Logitech
C270 camera. **LARP Scout A** and **LARP Scout B** are ECHO differential-drive
scouts, each paired with a separate Inland ESP32-CAM video node.

The project is based on the hardened deployment, dashboard, and test structure
from `AloeVeraZ/CityTechClubProjects/stem-research-academy`, integrated with
the 3TSahur/LARP naming, confirmed motor wiring, and ESP32-CAM support.

## Capabilities

- 3TSahur mecanum forward/backward, strafe, and rotation control.
- Logitech C270 MJPEG stream and two LARP ESP32-CAM MJPEG streams.
- Keyboard and touch controls, latest-command delivery, expiration, sequence
  checks, and independent hub/scout watchdogs.
- Self-hosted `3TSahur-Swarm` Wi-Fi hotspot, mDNS, systemd dashboard service,
  and a Pi-attached Chromium control window.
- Atomic installer update/rollback behavior and a simulation test suite.

## Start here

Read [the setup guide](docs/SETUP.md) before flashing boards or powering
motors. The exact Pi motor wiring is in [WIRING.md](docs/WIRING.md), the
integration history is in [CHANGES_FROM_ORIGINAL.md](docs/CHANGES_FROM_ORIGINAL.md),
and the executed simulation evidence is in [SIMULATION_RESULTS.md](docs/SIMULATION_RESULTS.md).

## Packages

- [robot_server](robot_server/README.md) — 3TSahur web server, dashboard, C270,
  mecanum GPIO, and LARP command proxy.
- [firmware/larp-scout](firmware/larp-scout/README.md) — LARP ECHO-board drive
  controller.
- [firmware/larp-esp32-cam](firmware/larp-esp32-cam/README.md) — Inland
  ESP32-CAM MJPEG stream.
- [installer](installer/README.md) — Raspberry Pi hotspot, service, kiosk, and
  upgrade installer.

## Local simulation

On a Python 3.11+ development machine:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The tests simulate GPIO/PWM motor selection, web routes, scout proxy behavior,
camera discovery, firmware contents, and installer invariants. They do not
replace wheels-up direction testing, electrical current testing, or compilation
against the actual Arduino board packages.
