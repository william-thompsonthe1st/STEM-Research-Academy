# 3TSahur + LARP Reconnaissance Swarm

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/control-Python_3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Raspberry Pi" src="https://img.shields.io/badge/hub-Raspberry_Pi_4-C51A4A?logo=raspberrypi&logoColor=white">
  <img alt="ESP32" src="https://img.shields.io/badge/scouts-ECHO_%2B_ESP32--CAM-111111?logo=espressif&logoColor=white">
  <img alt="License" src="https://img.shields.io/github/license/william-thompsonthe1st/STEM-Research-Academy">
</p>

> One rugged Raspberry Pi mecanum hub, two mobile camera scouts, and one browser dashboard for safe local reconnaissance experiments.

**3TSahur** is a Raspberry Pi 4 Model B (4 GB) mecanum-drive control hub with a Logitech C270 USB camera. It coordinates two ECHO differential-drive scout robots—**LARP Scout A** and **LARP Scout B**—each paired with an Inland ESP32-CAM video node. The project creates a self-contained local Wi-Fi control network: no internet connection is required during normal operation.

## What it can do

| System | Capability |
| --- | --- |
| 3TSahur hub | Drive forward, reverse, strafe, and rotate with four independently controlled mecanum wheels. |
| Live vision | Show the Logitech C270 feed plus two LARP ESP32-CAM MJPEG streams in one dashboard. |
| Scout control | Send direction commands to LARP Scout A and B independently over Wi-Fi. |
| Safety | Stop stale commands automatically; includes sequence checks, watchdogs, and a kill-all control. |
| Deployment | Configure a Pi hotspot, dashboard service, local touchscreen/display kiosk, and mDNS address. |
| Optional AI vision | Prepare pretrained YOLO11 Nano person detection for the selected C270 or LARP camera feed. |
| Mission tools | Keep a bounded event timeline, save per-camera snapshots, calibrate LARP CSI baselines, and use browser gamepads/dead-man control. |

## System overview

```mermaid
flowchart LR
    O["Operator<br/>phone, tablet, or Pi display"] <-->|"Browser controls / video"| D["3TSahur dashboard<br/>Raspberry Pi 4"]
    D -->|"USB"| C270["Logitech C270<br/>hub camera"]
    D -->|"GPIO"| H1["Front H-bridge<br/>motor driver"]
    D -->|"GPIO"| H2["Rear H-bridge<br/>motor driver"]
    H1 --> W["4 mecanum wheels"]
    H2 --> W
    D <-. "3TSahur-Swarm Wi-Fi" .-> LA["LARP Scout A<br/>ECHO controller"]
    D <-. "3TSahur-Swarm Wi-Fi" .-> LB["LARP Scout B<br/>ECHO controller"]
    CA["Inland ESP32-CAM A"] -->|"MJPEG stream"| D
    CB["Inland ESP32-CAM B"] -->|"MJPEG stream"| D
    LA --- CA
    LB --- CB
```

## Setup roadmap

Follow this order from an empty workbench to a safe first drive. Each stage
has a clear stop point, so a problem stays isolated to one subsystem.

```mermaid
flowchart TB
    S1["1. Gather and inspect<br/>Pi · motor hardware · two ECHOs · two Inland ESP32-CAMs"] --> S2["2. Build the Pi hub<br/>Raspberry Pi OS → installer → 3TSahur-Swarm hotspot"]
    S2 --> S3["3. Flash Scout A<br/>ECHO controller A + ESP32-CAM A"]
    S3 --> S4["4. Flash Scout B<br/>ECHO controller B + ESP32-CAM B"]
    S4 --> S5["5. Verify without motion<br/>dashboard · C270 · camera feeds · heartbeats"]
    S5 --> S6["6. Safety test raised wheels<br/>direction · Space · Esc · disconnect stop"]
    S6 --> S7["7. Low-speed ground test<br/>one active camera stream"]
    S7 --> S8["Optional last<br/>CSI calibration · YOLO · gamepad"]
```

| Stage | You need | Success looks like | Detailed instructions |
| --- | --- | --- | --- |
| 1. Hub | Pi 4, microSD, C270, motor drivers, safe external motor power | Everything is wired with motor power disconnected | [Wiring reference](docs/WIRING.md) |
| 2. Pi software | Internet for initial Pi setup | Pi creates `3TSahur-Swarm`; dashboard opens at `http://10.42.0.1` | [Pi installation](#install-on-the-raspberry-pi) |
| 3–4. Scouts | Each ECHO, each Inland ESP32-CAM, and a serial adapter | A and B use matching IDs and join the hotspot | [Flash firmware](#flash-the-larp-firmware) |
| 5. Network + video | Phone, tablet, or Pi display on the hotspot | C270 and the selected LARP stream display | [ESP32-CAM verification](docs/ESP32_CAM_SETUP.md#verify-the-feed) |
| 6–7. Motion | Wheels off the floor first | Controls, emergency stop, and watchdog stop work | [Safety checklist](#safety-checklist) |

> **Safety gate:** Do not connect motor power or attempt a floor drive until
> the dashboard, cameras, emergency stop, and raised-wheel direction tests all pass.

## Reproduction methodology

This project is designed as a local-first system: the Pi hosts the Wi-Fi
network, dashboard, motor control, C270 camera feed, and optional vision
worker. The two LARPs join that same network, register a heartbeat, receive
short-lived drive commands, and expose their own camera feeds. Nothing in
normal operation requires cloud access.

1. **Build safely.** Assemble and wire the parts in the rebuild checklist,
   leaving motor power disconnected until software checks pass.
2. **Install the Pi hub.** Flash Raspberry Pi OS, clone this repository, run
   the installer, and join the resulting `3TSahur-Swarm` hotspot.
3. **Flash the four scout boards.** Configure A/B identifiers and matching
   hotspot credentials in both LARP drive boards and both ESP32-CAM boards.
4. **Validate one subsystem at a time.** Confirm the Pi dashboard, C270, each
   camera stream, each LARP heartbeat, then raised-wheel drive directions.
5. **Operate with control priority.** Keep one dashboard camera stream open,
   start in the Control Priority camera profile if radio capacity is limited,
   and test `Space`/`Esc` before floor operation.
6. **Enable optional analysis last.** Use CSI calibration with the scene clear,
   then enable YOLO only for the selected camera when its performance is
   acceptable.

### What happens when the system runs

- The browser sends only current, expiring commands; stale/reordered input is
  rejected and the Pi watchdog stops 3TSahur if refreshes cease.
- Switching robot tabs stops all robots and closes inactive MJPEG streams to
  protect control bandwidth.
- LARP drive status, CSI, timeline, health, vision, snapshots, and camera
  profiles are auxiliary features. Their failure must display a status only;
  it cannot disable the core stop/watchdog/control paths.
- The mission timeline is capped at 120 in-memory events. Snapshots are saved
  locally by the Pi; copy any images you need before rebooting or updating.

### Quick field-validation flow

```mermaid
flowchart LR
    A["Boot Pi hub"] --> B["Join local hotspot"] --> C["Verify C270 and one LARP stream"]
    C --> D["Raised-wheel stop and direction test"] --> E["Calibrate CSI"]
    E --> F["Enable optional YOLO / gamepad"] --> G["Ground test at low speed"]
```

For the next field session, use the step-by-step
[tomorrow checklist](docs/TOMORROW_CHECKLIST.md). It includes the precise
gimbal/ramp servo information needed before new actuator code is written.

## What changed from the partner integration base

The partner repository remains the software foundation. We retained the Python
server/package structure, motor-control pattern, hotspot installer, systemd
deployment, and original Pi mecanum GPIO mapping; the work here adapts and
extends that base for the 3TSahur/LARP swarm.

| Area | Partner-base behavior retained | 3TSahur/LARP changes |
| --- | --- | --- |
| Drivetrain | Python mecanum drive and GPIO architecture | Names changed only; exact BCM mapping remains `5/6`, `16/19`, `20/21`, `13/26`. |
| Deployment | Hotspot, service, kiosk, installer/update rollback | 3TSahur names, local operator workflow, beginner setup/checklists. |
| Dashboard | Responsive browser controls | Three robot tabs, single active stream, health panel, profiles, timeline, gamepad/dead-man controls. |
| Scouts | ECHO drive/control foundations | LARP A/B identities, Wi-Fi recovery, heartbeats, CSI display/calibration, separate camera feeds. |
| Vision | No optional hub inference workflow | Per-feed YOLO11 Nano toggles, overlays, snapshots, and failure isolation. |
| Validation | Original functional test foundation | Expanded simulation coverage, API expiry/sequence checks, feature-isolation checks, and timing results. |

```mermaid
flowchart TB
    Base["Partner integration base\nserver · GPIO architecture · hotspot · installer"] --> Retained["Retained without drivetrain-pin changes"]
    Retained --> Hub["3TSahur hub\nC270 · mecanum · camera profiles"]
    Retained --> Scouts["LARP Scout A / B\nECHO · ESP32-CAM · CSI"]
    Hub --> Dashboard["Tabbed operator dashboard\ncontrols · health · timeline"]
    Scouts --> Dashboard
    Dashboard --> Optional["Optional YOLO · snapshots · gamepad · dead-man"]
```

Read [docs/CHANGES_FROM_ORIGINAL.md](docs/CHANGES_FROM_ORIGINAL.md) for the
full file-level integration record.

### Verified compatibility with the partner baseline

The current project retains the partner team's tested mecanum GPIO mapping,
mixer, shared 15 ms reversal dead-time, latest-command-only control channel,
300 ms command expiry, 200 ms Pi watchdog, ECHO motor IDs (`1`/`6`), and
ESP32 Wi-Fi sleep-disable behavior. The 3TSahur/LARP work adds tabs, camera
isolation, optional mission tools, and control-priority tuning around that
foundation; it does not replace the motor architecture. See the detailed
[partner baseline comparison](docs/PARTNER_BASELINE_COMPARISON.md) for every
retained behavior, added feature, latency difference, and test limitation.

## Dashboard

Open `http://10.42.0.1` after connecting to the 3TSahur hotspot. On a device that supports mDNS, `http://3tsahur.local` also works. The Pi's attached display opens the same dashboard automatically after installation.

```text
┌─────────────────────────────────────────────────────────────────────┐
│  [ 3TSahur ]  [ LARP Scout A ]  [ LARP Scout B ]     ● Online       │
├───────────────────────────────────┬─────────────────────────────────┤
│  Selected robot's live camera     │  Selected robot's controls      │
│  (one stream active at a time)    │  status, speed, and stop        │
├───────────────────────────────────┴─────────────────────────────────┤
│  Emergency STOP ALL · responsive phone/tablet/desktop layout         │
└─────────────────────────────────────────────────────────────────────┘
```

Only the selected tab keeps its MJPEG feed open. This preserves hotspot
bandwidth for low-latency robot commands instead of competing with three video
streams at once.

### Current dashboard visual system

The UI uses a static control-room visual system: an editorial status header,
compact safety pills, a three-robot navigation dock, and layered control cards.
It is a presentation-only refresh: the tabs, controls, keyboard bindings,
single-stream policy, safety stops, optional vision, CSI, mission tools, and
actuator staging all retain their existing behavior.

```text
+-----------------------------------------------------------------------+
|  3TSAHUR-SWARM LOCAL COMMAND CENTER              [ LOCAL CONTROL ]   |
|  Reconnaissance dashboard     [ one camera ] [ watchdog protected ]  |
+-----------------------------------------------------------------------+
| [01 3TSahur]       [02 LARP Scout A]       [03 LARP Scout B]         |
+--------------------------------------+--------------------------------+
| Selected live camera                 | Selected robot controls        |
| vision + snapshot overlay            | status, speed, drive, stop     |
|                                      | CSI / gimbal / ramp as needed  |
+--------------------------------------+--------------------------------+
| STOP ALL (Esc)       Mission timeline, health, dead-man controls      |
+-----------------------------------------------------------------------+
```

The visual layer adds no JavaScript, packages, API calls, polling, video
streams, model work, or motor-control code. It also removes the former
camera CSS filter and mission-panel backdrop filter to avoid extra compositor
work on the Raspberry Pi.

The dashboard works with mouse/touch controls and the following keyboard shortcuts when the page is focused:

| Robot | Keys | Action |
| --- | --- | --- |
| 3TSahur | `W` / `S` | Forward / reverse |
| 3TSahur | `A` / `D` | Strafe left / right |
| 3TSahur | `Q` / `E` | Rotate left / right |
| 3TSahur | `Space` | Stop the hub drivetrain |
| LARP Scout A | Arrow keys | Forward, reverse, left, right |
| LARP Scout B | `I` / `K` / `J` / `L` | Forward, reverse, left, right |
| All robots | `Esc` | Emergency kill-all |

Commands are deliberately short-lived. Releasing a key, losing the client connection, or letting the watchdog expire stops the affected robot.

## Hardware and wiring

### Rebuild checklist

**Required parts**

- [ ] Raspberry Pi 4 Model B (4 GB), microSD card, official-grade 5 V / 3 A supply, case/cooling, and a local display or operator phone/tablet.
- [ ] Logitech C270 USB webcam and four mecanum DC motors with compatible wheels/chassis.
- [ ] Two dual-channel H-bridge drivers, correctly rated fused motor battery/supply, wiring, common ground, and an accessible physical motor-power switch.
- [ ] For the planned C270 gimbal and ramp: a verified servo-driver board, a separate servo-rated regulated supply, four servo channels, compatible pan/tilt and ramp servos, and mechanical end-stop testing before the driver is enabled.
- [ ] Two ECHO robots, two Inland ESP32-CAM boards, matching camera modules, two stable regulated 5 V camera supplies, and either built-in camera USB or 3.3 V-safe USB-to-serial flashing hardware.
- [ ] A 2.4 GHz Wi-Fi-capable operator device. A browser gamepad is optional; no Pi-side gamepad hardware is required.

**Raspberry Pi software checklist**

- [ ] Current 64-bit Raspberry Pi OS with internet available for initial installation.
- [ ] Run `bash installer/install.sh` as the normal Pi user. It installs Python, Flask, OpenCV, V4L2 tools, NetworkManager, Avahi, and required GPIO support.
- [ ] Flash and configure the two LARP controller sketches and two ESP32-CAM sketches with the same hotspot credentials.
- [ ] Optional YOLO: follow [docs/VISION_SETUP.md](docs/VISION_SETUP.md) to install `ultralytics` and `ncnn` inside `.vision-venv` and export `yolo11n_ncnn_model`.

**Arduino IDE checklist**

- [ ] Install Arduino IDE and the **esp32 by Espressif Systems** board package for the Inland ESP32-CAM; select the AI Thinker-compatible profile described in [docs/ESP32_CAM_SETUP.md](docs/ESP32_CAM_SETUP.md).
- [ ] Install the ECHO/EchoLib dependencies specified in [firmware/larp-scout/README.md](firmware/larp-scout/README.md) before flashing the LARP drive controllers.
- [ ] Upload with GPIO0 grounded only during ESP32-CAM flashing, then remove the jumper before normal boot.
- [ ] Read [the LARP camera/controller integration guide](docs/LARP_CAMERA_CONTROLLER_INTEGRATION.md) before connecting the camera to power or using an Arduino as a serial bridge.

### 3TSahur hub

| Part | Role |
| --- | --- |
| Raspberry Pi 4 Model B (4 GB) | Runs the hotspot, web dashboard, control service, and USB camera feed. |
| Logitech C270 | USB hub camera. Use a powered USB hub if the Pi cannot supply enough current. |
| Two dual-channel H-bridge motor drivers | Drive the four mecanum motors. Motor power must come from a suitable external supply. |
| Four mecanum DC motors | Front-left, rear-left, front-right, rear-right wheel positions. |

The Pi GPIO layout below is intentionally the same layout as the integration base repository. GPIO numbers are **BCM numbers**, not physical header pin numbers.

| Wheel | Driver channel | GPIO direction pins |
| --- | --- | --- |
| Front left | Front driver IN1 / IN2 | GPIO 5 / GPIO 6 |
| Rear left | Front driver IN3 / IN4 | GPIO 16 / GPIO 19 |
| Front right | Rear driver IN1 / IN2 | GPIO 20 / GPIO 21 |
| Rear right | Rear driver IN3 / IN4 | GPIO 13 / GPIO 26 |

Do not power motors from the Pi's 5 V rail. Share a common ground between the Pi and motor-driver logic, verify each motor direction with wheels raised, and keep an accessible physical power switch. Full connection notes are in [docs/WIRING.md](docs/WIRING.md).

### Planned C270 gimbal and ramp

The dashboard now includes **Gimbal mode** (`G`, then arrow keys) and a **ramp toggle** (`R`) on the 3TSahur tab. This release is intentionally a no-output staging layer: it records bounded requested pan/tilt and ramp positions but contains no servo-driver library, GPIO mapping, I2C address, PWM channel, or physical output. It cannot move servos until the team supplies the driver model, power plan, channels, and calibrated mechanical limits. See [auxiliary-actuator setup requirements](docs/3TSAHUR_AUXILIARY_ACTUATORS.md).

### LARP scouts and cameras

Each scout contains:

- An ECHO robot controller running the LARP drive firmware. The retained motor IDs are left = `1`, right = `6`.
- An Inland ESP32-CAM flashing the LARP camera firmware, configured as an AI Thinker-compatible pin layout.
- The same Wi-Fi SSID/password as the Pi hotspot.

The ESP32-CAM board variations can differ. Check the board silk screen and camera connector before powering it. The camera is a separate Wi-Fi video node: retain the ECHO controller's existing motor wiring, power the camera from a regulated 5 V branch, and pair `ROBOT_ID` with `CAMERA_ID` (`A`/`A`, `B`/`B`). See the [LARP camera/controller integration guide](docs/LARP_CAMERA_CONTROLLER_INTEGRATION.md) for the complete safe-power, flashing, Wi-Fi, and field-test procedure.

## Install on the Raspberry Pi

### Fast install (recommended after review)

On a current Raspberry Pi OS image with internet access, run this as the
normal Pi user—not `root`. It downloads the repository's installer, which
then performs package installation, preflight validation, atomic app
replacement, hotspot/service setup, and reboot.

```bash
curl -fsSL https://raw.githubusercontent.com/william-thompsonthe1st/STEM-Research-Academy/main/installer/curl-install.sh | bash
```

To install a reviewed non-default branch, send the branch name to **bash**:

```bash
curl -fsSL https://raw.githubusercontent.com/william-thompsonthe1st/STEM-Research-Academy/agent/integrate-3tsahur-larp/installer/curl-install.sh | STEM_REPO_BRANCH=agent/integrate-3tsahur-larp bash
```

The installer intentionally reboots. Read the script or use the clone method
below first if your team prefers to inspect every install step locally.

### Copy/paste Pi upgrade from the partner installation

If the Pi already runs the partner project or another dashboard build, **do
not reflash Raspberry Pi OS**. The 3TSahur installer replaces the installed
application and restarts the existing `stem-robot-dashboard` service. It uses
the same application path (`~/STEMResearchAcademy`) and configuration location
(`/etc/stem-research-academy/config.env`), so do not attempt to run both
dashboard versions at the same time.

Run this entire block as the normal Pi user. It creates timestamped backups
when the application or config exists, then installs the current integration
branch without performing a full Pi OS package upgrade:

```bash
set -Eeuo pipefail

upgrade_stamp="$(date +%Y%m%d-%H%M%S)"
app_backup="$HOME/STEMResearchAcademy.partner-backup-$upgrade_stamp"
config_backup="$HOME/stem-config.partner-backup-$upgrade_stamp.env"

if [ -d "$HOME/STEMResearchAcademy" ]; then
    cp -a -- "$HOME/STEMResearchAcademy" "$app_backup"
    echo "Application backup: $app_backup"
else
    echo "No existing ~/STEMResearchAcademy directory; skipping app backup."
fi

if sudo test -f /etc/stem-research-academy/config.env; then
    sudo cp -- /etc/stem-research-academy/config.env "$config_backup"
    sudo chown "$(id -u):$(id -g)" "$config_backup"
    echo "Configuration backup: $config_backup"
else
    echo "No existing config.env; skipping config backup."
fi

curl -fsSL https://raw.githubusercontent.com/william-thompsonthe1st/STEM-Research-Academy/agent/integrate-3tsahur-larp/installer/curl-install.sh | STEM_REPO_BRANCH=agent/integrate-3tsahur-larp STEM_SKIP_OS_UPGRADE=1 bash
```

No Raspberry Pi OS reflash is needed; the installer validates the replacement
and intentionally reboots the Pi when it finishes.

After the Pi reboots, expect these intentional changes:

- The hotspot is `3TSahur-Swarm` and the Pi hostname is `3tsahur`.
- The dashboard is at `http://10.42.0.1` after joining that hotspot.
- The retained mecanum GPIO layout and motor wiring stay the same.
- Reflash each LARP controller with the LARP firmware and matching Wi-Fi
  credentials before expecting it to reconnect. Reflash the ESP32-CAM boards
  only when their new dashboard feeds are needed.

Verify the service, then test 3TSahur with its wheels raised before connecting
or driving the LARPs:

```bash
sudo systemctl status stem-robot-dashboard --no-pager
sudo systemctl status stem-robot-hotspot --no-pager
```

If you need to return to the partner build after a successful upgrade, use the
backup above or rerun the partner repository's installer. See the [partner
baseline comparison](docs/PARTNER_BASELINE_COMPARISON.md) for the retained
motor architecture and the exact configuration differences.

### Optional one-command YOLO install

Install the base hub first. Then, if you want pretrained person detection,
run this separate command as the normal Pi user. It creates `.vision-venv`,
installs Ultralytics/NCNN, downloads the pretrained `yolo11n` weights, and
exports the 320px NCNN model used by the dashboard.

```bash
curl -fsSL https://raw.githubusercontent.com/william-thompsonthe1st/STEM-Research-Academy/main/installer/install-vision.sh | bash
```

YOLO remains optional: do not install it until the base dashboard, cameras,
and controls have passed their physical checks. It is never required for motor
control or LARP operation.

### Manual vision install

Use this alternative only if you prefer to inspect each command rather than using
the one-command installer above.

- Current 64-bit Raspberry Pi OS; complete the base installation first.
- Stable power, at least 3 GB free storage, and temporary internet for the
  one-time package/model download and conversion.
- A connected C270 or a verified LARP ESP32-CAM MJPEG stream.
- Install as the normal Pi user in a separate environment—never as `root` and
  never into the dashboard's system Python packages.

```bash
cd ~/STEMResearchAcademy
python3 -m venv --system-site-packages .vision-venv
source .vision-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ultralytics>=8.3,<9" ncnn

# Downloads pretrained COCO weights once, then exports the Pi-friendly runtime.
python - <<'PY'
from ultralytics import YOLO
YOLO("yolo11n.pt").export(format="ncnn", imgsz=320)
PY
```

The complete [pretrained vision setup guide](docs/VISION_SETUP.md) includes
the C270 visual test, LARP feed prerequisites, safe performance settings,
offline-use notes, and a hardware validation checklist. Upstream references:
[YOLO11 models](https://docs.ultralytics.com/models/yolo11/),
[NCNN export](https://docs.ultralytics.com/integrations/ncnn/), and
[Raspberry Pi deployment](https://docs.ultralytics.com/guides/raspberry-pi/).

## Flash the LARP firmware

| Target | Sketch | Set before upload |
| --- | --- | --- |
| LARP Scout A/B ECHO board | [firmware/larp-scout/larp_scout_controller.ino](firmware/larp-scout/larp_scout_controller.ino) | `ROBOT_ID`, Wi-Fi credentials, and any board-specific library setup. |
| Inland ESP32-CAM A/B | [firmware/larp-esp32-cam/larp-esp32-cam.ino](firmware/larp-esp32-cam/larp-esp32-cam.ino) | `CAMERA_ID`, Wi-Fi credentials, and the camera board profile. |

Upload one copy configured as `A` and one as `B` for each firmware type. The [LARP controller README](firmware/larp-scout/README.md) and [camera README](firmware/larp-esp32-cam/README.md) cover dependencies and upload notes.

### ESP32-CAM quick start

The Inland ESP32-CAM is a separate Wi-Fi video node, not a motor-controller
accessory. Flash it as `A` or `B`, connect it to stable 5 V power, and use the
matching `larp-a-cam.local/stream` or `larp-b-cam.local/stream` address. The
dashboard opens only the selected LARP feed to protect control responsiveness.
See the complete [Inland ESP32-CAM setup guide](docs/ESP32_CAM_SETUP.md) for
the flash wiring, pin map, network fallback, and troubleshooting steps.
For the complete LARP-level procedure—including power separation, when an
Arduino can safely act as a serial bridge, controller/camera pairing, and a
field-test checklist—read the [LARP camera/controller integration guide](docs/LARP_CAMERA_CONTROLLER_INTEGRATION.md).

### Flash an Inland ESP32-CAM

Use these steps once for **Scout A** and again for **Scout B**. The ESP32-CAM
is the scout's Wi-Fi video node; it does not connect to or control the ECHO
motor controller.

1. Install Arduino IDE and the **esp32 by Espressif Systems** board package.
2. Before applying power, verify that the Inland module uses the
   AI Thinker-compatible camera layout. Use a stable regulated 5 V supply
   capable of at least 1 A—never a Raspberry Pi GPIO pin or the ECHO logic
   rail.
3. Connect a 3.3 V-safe USB-to-serial adapter: adapter **5 V** to camera
   **5 V**, **GND** to **GND**, adapter **TX** to **U0R / GPIO 3**, and adapter
   **RX** to **U0T / GPIO 1**. For uploading only, connect **GPIO 0** to
   **GND**.
4. In Arduino IDE, select **AI Thinker ESP32-CAM**, choose the adapter's serial
   port, and open
   [`firmware/larp-esp32-cam/larp-esp32-cam.ino`](firmware/larp-esp32-cam/larp-esp32-cam.ino).
   If the upload is unreliable, lower the upload speed.
5. Set `CAMERA_ID` to `'A'` for Scout A or `'B'` for Scout B. Set
   `WIFI_SSID` and `WIFI_PASSWORD` to the exact credentials for the
   `3TSahur-Swarm` Pi hotspot.
6. Upload the sketch. If it stays at “Connecting,” briefly press **Reset**
   while Arduino IDE is connecting.
7. Remove the GPIO 0-to-GND jumper, press **Reset**, and power the board
   normally. It will not boot the camera firmware while GPIO 0 remains grounded.
8. Join a phone, tablet, or computer to the Pi hotspot and check
   `http://larp-a-cam.local/status` and
   `http://larp-a-cam.local/stream` (replace `a` with `b` for Scout B).
   The matching LARP dashboard tab should then open the feed automatically.

#### If the available bridge is an Arduino UNO R4

The UNO R4 can pass upload data between the computer and camera, but it cannot
connect directly because its serial pins use 5 V logic and the ESP32 uses
3.3 V logic. A resistor divider alone is not enough. You need:

- an UNO R4 Minima or UNO R4 WiFi and its USB cable;
- a **two-channel, UART-capable 5 V-to-3.3 V logic-level shifter**;
- a separate regulated **5 V, 1 A or greater** camera supply;
- jumper wires, including a removable GPIO 0-to-GND jumper.

> **Do not connect UNO D1/TX directly to camera U0R/GPIO 3. Do not power the
> camera from the UNO 3.3 V pin. Disconnect USB and camera power before
> changing wires.**

```mermaid
flowchart LR
    PC["Computer / Arduino IDE"] -->|"USB data + UNO power"| UNO["UNO R4<br/>5 V UART"]
    UNO -->|"D1 / TX"| CH1["Level shifter channel 1<br/>5 V to 3.3 V"]
    CH1 -->|"safe 3.3 V"| RX["ESP32-CAM<br/>U0R / GPIO 3 / RX"]
    TX["ESP32-CAM<br/>U0T / GPIO 1 / TX"] -->|"3.3 V"| CH2["Level shifter channel 2<br/>3.3 V to 5 V"]
    CH2 -->|"safe 5 V"| UNO
    PSU["Separate regulated supply<br/>5 V, at least 1 A"] -->|"positive only"| CAM5["ESP32-CAM 5V"]
    GND["Common ground"] ---|"UNO GND"| UNO
    GND --- SHG["Shifter GND"]
    GND --- ESPG["ESP32-CAM GND"]
    GND --- PSUG["Supply GND"]
    BOOT["GPIO 0 to GND<br/>upload only"] --- GND
    BAD1["NEVER: UNO TX directly to ESP RX"] -. "unsafe 5 V" .-> RX
    BAD2["NEVER: separate supply + to UNO 5V"] -. "do not join positive rails" .-> UNO
    classDef danger fill:#7f1d1d,color:#fff,stroke:#ef4444,stroke-width:2px;
    class BAD1,BAD2 danger;
```

```mermaid
flowchart LR
    A["1. D0/D1 disconnected<br/>upload bridge to UNO"] --> B["2. Power off<br/>wire shifter, supply, ground"]
    B --> C["3. GPIO 0 low<br/>reset camera into bootloader"]
    C --> D["4. Select AI Thinker<br/>keep UNO port, upload at 115200"]
    D --> E["5. Power off<br/>remove GPIO 0 jumper"]
    E --> F["Normal boot<br/>verify at 115200"]
```

1. **Prepare the UNO.** Leave D0 and D1 disconnected. Connect only the UNO USB
   cable. In Arduino IDE, select your exact UNO R4 model and its serial port,
   then upload this bridge sketch:

   ```cpp
   void setup() {
     Serial.begin(115200);   // UNO R4 USB serial
     Serial1.begin(115200);  // D0/RX and D1/TX
   }

   void loop() {
     while (Serial.available()) Serial1.write(Serial.read());
     while (Serial1.available()) Serial.write(Serial1.read());
   }
   ```

   **Checkpoint:** Arduino IDE reports a successful UNO upload. Leave this
   sketch running; do not hold the UNO in reset.
2. **Wire everything with all power disconnected.** `HV`/`LV` names vary by
   shifter, so follow its labels and direction markings.

   ```text
   COMPUTER --USB--> UNO R4

   UNO 5V  ------> shifter HV power       UNO GND ---------+
   UNO 3.3V -----> shifter LV power       shifter GND -----+-- common ground
   UNO D1/TX ----> [5V -> 3.3V channel] --> ESP U0R/GPIO 3  |
   UNO D0/RX <---- [5V <- 3.3V channel] <-- ESP U0T/GPIO 1  |
                                                            |
   separate 5V >=1A supply + ----------------> ESP 5V      |
   separate supply GND ------------------------------------+
   ESP GPIO 0 ---------------------------------> GND  (upload only)
   ```

   Do not connect the separate supply's positive 5 V output to UNO 5V.
   **Checkpoint:** TX and RX are crossed through two shifter channels, every
   device shares ground, and GPIO 0 is connected to ground.
3. **Enter camera upload mode.** Reconnect UNO USB and camera power while GPIO 0
   remains grounded. Press the camera **Reset** button once; if it has no Reset
   button, briefly remove and restore camera power.
4. **Upload the camera sketch.** In Arduino IDE, open
   `firmware/larp-esp32-cam/larp-esp32-cam.ino`. Change the selected board to
   **AI Thinker ESP32-CAM**, but keep the **same UNO R4 USB serial port**
   selected. Set upload speed to **115200** and close Serial Monitor. Confirm
   `CAMERA_ID`, `WIFI_SSID`, and `WIFI_PASSWORD`, then select **Upload**.

   **Checkpoint:** the output ends with a successful flash/reset message. If it
   stays on `Connecting...`, press camera Reset once, check GPIO 0 is grounded,
   and verify the crossed TX/RX paths.
5. **Return the camera to normal boot.** Disconnect camera power. Remove only
   the GPIO 0-to-GND jumper, then restore camera power. Press camera Reset if
   needed. Open Serial Monitor at **115200** to see its network address.

The UNO bridge cannot automatically control the camera's Reset or GPIO 0 pins.
If it still cannot synchronize after checking the wiring and using short
jumpers, use a dedicated 3.3 V USB-to-UART adapter. Electrical rationale:
[Arduino UNO R4
Minima documentation](https://docs.arduino.cc/hardware/uno-r4-minima), [Arduino
UNO R4 WiFi documentation](https://docs.arduino.cc/hardware/uno-r4-wifi/),
[Renesas RA4M1 input thresholds](https://docs.arduino.cc/resources/datasheets/ra4m1-datasheet.pdf),
[Espressif serial-connection guidance](https://docs.espressif.com/projects/esptool/en/latest/esp32/esptool/serial-connection.html),
and [Espressif boot-mode guidance](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html).

For the full connection table, pin map, network fallback, and troubleshooting,
see [the Inland ESP32-CAM setup guide](docs/ESP32_CAM_SETUP.md).

## Tests and simulation evidence

The hardware-independent test suite exercises simulated GPIO/PWM motor decisions, camera discovery, scout command proxy behavior, firmware settings, and installer invariants.

```bash
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The recorded desktop simulation ran **60 tests successfully**: dashboard/UI,
mecanum mixing, camera discovery/profile isolation, firmware invariants,
scout registry, Flask control APIs, mission events, snapshots, and optional
vision failure handling. Repeated held-command heartbeats are also verified to
refresh the watchdog without rewriting unchanged Pi or LARP motor outputs.
Hardware validation is still required for motor
polarity/current, Wi-Fi range, camera focus, CSI calibration, gamepad mapping,
and physical emergency-stop behavior. Read
[docs/SIMULATION_RESULTS.md](docs/SIMULATION_RESULTS.md) for the exact
results and limitations.

## Project structure

```text
STEM-Research-Academy/
├── robot_server/                 # Python dashboard, GPIO drive, camera, scout proxy
│   ├── static/                   # Browser UI assets
│   ├── templates/                # Dashboard page
│   └── tests/                    # Software simulation tests
├── firmware/
│   ├── larp-scout/               # ECHO drive firmware for Scouts A and B
│   └── larp-esp32-cam/           # Inland ESP32-CAM streaming firmware
├── installer/                    # Pi installer, hotspot, systemd, kiosk setup
├── docs/                         # Wiring, setup, test report, integration changes
├── run.py                        # Dashboard entry point
└── requirements.txt              # Local development dependencies
```

## Local development

Run the dashboard without GPIO hardware for UI work and code review:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Then browse to `http://127.0.0.1:8080`. On a non-Pi machine, GPIO behavior is simulated/fails safely; it does not move hardware. Keep real motor testing on the Pi, with wheels off the ground for the first run.

## Documentation

- [Setup guide](docs/SETUP.md) — end-to-end Pi, network, firmware, and first-drive procedure.
- [Tomorrow field checklist](docs/TOMORROW_CHECKLIST.md) — physical validation and the servo/gimbal data required for the next development step.
- [Field information checklist](docs/FIELD_INFORMATION_CHECKLIST.md) — exact photos, serial logs, network evidence, and hardware data needed for the next integration step.
- [Latency and connection tuning](docs/LATENCY_TUNING.md) — control-priority safeguards, reconnection behavior, and field-test sequence.
- [Wiring reference](docs/WIRING.md) — exact 3TSahur motor GPIO mapping and ESP32-CAM notes.
- [Inland ESP32-CAM setup](docs/ESP32_CAM_SETUP.md) — upload wiring, pin map, stream verification, and troubleshooting.
- [LARP camera/controller integration](docs/LARP_CAMERA_CONTROLLER_INTEGRATION.md) — safe power, Arduino-bridge decision guide, pairing, setup, and field tests.
- [Simulation results](docs/SIMULATION_RESULTS.md) — commands run, passed tests, and test limitations.
- [Changes from original](docs/CHANGES_FROM_ORIGINAL.md) — what came from the integration base and what changed.
- [Installer guide](installer/README.md) and [server guide](robot_server/README.md) — package-specific operation details.

## Safety checklist

- Test each motion direction with the wheels clear of the floor.
- Use a fused motor supply sized for motor stall current; never run motor power through the Pi.
- Keep the motor battery disconnected while wiring or flashing boards.
- Make sure every controller shares the intended common logic ground.
- Test `Space`/`Esc` and a network-disconnect stop before operating near people or property.

---

Built from the partner project's deployment/dashboard foundation and adapted for the 3TSahur hub and LARP Scout system. See [docs/CHANGES_FROM_ORIGINAL.md](docs/CHANGES_FROM_ORIGINAL.md) for the complete integration record.
