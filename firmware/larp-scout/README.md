# LARP Scout ECHO controller firmware

This is the drive and status firmware for a LARP Scout's 3D Buffalo ECHO
board. It runs the existing differential-drive controls, sends the Pi a
heartbeat and CSI status, accepts `/drive` and `/stop`, and brakes after
500 ms without a fresh drive command. The Inland ESP32-CAM is a **separate**
Wi-Fi device: a camera problem must not stop this controller from joining the
Pi hotspot or accepting a stop command.

## Before you open Arduino IDE

1. Install Arduino IDE 2.x.
2. In **File > Preferences**, add this Additional Boards Manager URL if it is
   not already present:

   ```text
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```

3. In **Tools > Board > Boards Manager**, install **esp32 by Espressif
   Systems 3.0.7**. This is the version used to verify this project sketch.
4. Download and install **EchoLib 1.3.0** from the official
   [EchoLib 1.3.0 release](https://github.com/3DBuffalo/Echo_Lib/tree/V1.3.0):
   in Arduino IDE use **Sketch > Include Library > Add .ZIP Library**.
5. In **Library Manager**, install **Adafruit BusIO**. EchoLib includes the
   related headers even if this Scout is not using an add-on servo.

Do not select an ESP32-CAM board for the ECHO. Its target is the ESP32-S3.

## Flash one ECHO controller

1. In Arduino IDE choose **File > Open** and select
   `firmware/larp-scout/larp-scout.ino` directly. Its filename deliberately
   matches its `larp-scout` folder; Arduino treats a mismatch as a fatal
   sketch error before compiling the firmware.
2. Edit only the configuration near the top:

   ```cpp
   constexpr char ROBOT_ID = 'A';
   constexpr char WIFI_SSID[] = "your-Pi-hotspot-name";
   constexpr char WIFI_PASSWORD[] = "your-private-password";
   ```

   Use `ROBOT_ID = 'A'` for Scout A and `'B'` for Scout B. The SSID and
   password must exactly match the Pi's
   `/etc/stem-research-academy/config.env` values and the matching camera
   sketch.
3. Select **Tools > Board > ESP32 Arduino > ESP32S3 Dev Module**.
4. Select the ECHO's serial port. Set upload speed to **115200** for the most
   reliable first upload.
5. Click the checkmark (**Verify**) first. A successful verify only proves the
   source and installed libraries compile; it does not contact the board.
6. Put the wheels safely off the ground, then click **Upload**. Test `/stop`
   before any ground operation.

## Read errors in the right order

| Arduino message | Meaning | Fix |
| --- | --- | --- |
| `main file missing from sketch` or `Can't open sketch` | Arduino cannot find the primary `.ino` file because its name did not match the directory. | Open `larp-scout.ino` directly. Do not rename it independently of the `larp-scout` folder. |
| `EchoLib.h: No such file or directory` | EchoLib was not installed in Arduino's library folder. | Install the EchoLib **1.3.0** ZIP, restart Arduino IDE, and verify again. |
| `Adafruit_I2CDevice.h: No such file or directory` | EchoLib's required support library is missing. | Install **Adafruit BusIO** in Library Manager, then verify again. |
| An error names `TankDriveTrain` | The 3DBuffalo web examples and library releases have differed. This project is validated against EchoLib **1.3.0**, which provides `TankDrive`. | Remove an incompatible EchoLib copy, install the release above, and keep this sketch's `TankDrive drivetrain(...)` line unchanged. |
| `Failed to connect to ESP32-S3: No serial data received` | **Upload/bootloader**, not a source compile or Wi-Fi error. Arduino has already reached the upload stage. | Close Serial Monitor, use a direct data-capable USB cable, hold **PROG**, press and release **RESET**, wait for the port to reappear, then upload at 115200. |

For the last row, also disconnect other software using the serial port and
avoid an unpowered USB hub. The vendor's [basic ECHO setup](https://3dbuffalo.gitbook.io/echolib/getting-started/basic-setup-+-first-program)
and [Espressif's ESP32-S3 upload troubleshooting](https://docs.espressif.com/projects/esptool/en/latest/esp32s3/troubleshooting.html)
cover board-side recovery steps.

## Wi-Fi, WPA, and IPEX-1 antenna

The ECHO is configured as a 2.4 GHz Wi-Fi station. The Pi installer creates a
2.4 GHz channel-6 hotspot using WPA2-Personal/RSN. This sketch neither asks
for WPA1 nor has an option to select WPA1; do **not** enable WPA1 and do not
make the hotspot WPA3-only. Keep the Pi's `10.42.0.1` address unless the
firmware is changed and reflashed together.

The IPEX-1 antenna is physical hardware, not an Arduino setting. With robot
power off, press the antenna connector straight down onto the ECHO socket,
verify it is centered and flush, and route the cable away from motor/battery
wiring and metal chassis pieces. A loose antenna can cause weak or intermittent
Wi-Fi, but it cannot produce an Arduino compilation or bootloader error.

## Normal connection check

1. Start the Pi hotspot and wait until `3TSahur-Swarm` is visible.
2. Power **one** ECHO and watch Serial Monitor at 115200 baud. It should report
   an IP address and `Pi dashboard: http://10.42.0.1/`.
3. Check that Scout A or B appears online in the matching dashboard tab.
4. Repeat for the other Scout. Only then power and test the matching camera.

The controller reconnects without blocking motor safety: it retries Wi-Fi on a
per-Scout schedule, but the local 500 ms command watchdog remains active even
if the Pi or the camera is unavailable. See the root
[LARP connectivity guide](../../README.md#larp-connectivity-beginner-setup-and-troubleshooting)
for Pi-side commands and a complete field checklist.
