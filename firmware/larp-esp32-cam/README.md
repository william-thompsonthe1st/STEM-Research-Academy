# LARP Inland ESP32-CAM firmware

This sketch is the LARP Scout's video node. It is deliberately independent of
the ECHO motor controller: it joins the Pi hotspot, serves a capped MJPEG feed,
and registers its current DHCP address with the Pi dashboard. If it cannot
connect or its camera fails, Scout drive and stop commands still remain on the
ECHO controller.

## Flash a camera, one at a time

1. Install Arduino IDE 2.x and **esp32 by Espressif Systems 3.0.7** through
   Boards Manager. This is the version used to verify this sketch.
2. Choose **File > Open** and open
   `firmware/larp-esp32-cam/larp-esp32-cam.ino` directly. Its name matches its
   folder, which Arduino requires before it can compile a sketch.
3. Set the top-of-file configuration for the camera you are flashing:

   ```cpp
   constexpr char CAMERA_ID = 'A';
   constexpr char WIFI_SSID[] = "your-Pi-hotspot-name";
   constexpr char WIFI_PASSWORD[] = "your-private-password";
   ```

   Use `A` with Scout A and `B` with Scout B. Copy the exact same hotspot
   credentials into both camera sketches and both ECHO sketches.
4. For the Inland board used by this project, select **Tools > Board > ESP32
   Arduino > AI Thinker ESP32-CAM**. Select the correct serial port.
5. Connect GPIO0 to GND only for upload, reset/power-cycle the camera, and
   upload at **115200** if the default speed is unreliable. Remove the GPIO0
   jumper and reset again for normal boot.

The AI Thinker pin map is built into this sketch. Do not select this board
profile for an unknown ESP32-CAM layout without first matching its printed
pinout. `NodeMCU-32S` may upload a generic ESP32 binary but is not a supported
camera profile. Use the detailed [ESP32-CAM setup guide](../../docs/ESP32_CAM_SETUP.md) for
USB-to-UART wiring and power requirements.

## Verify connection and video

1. Start the Pi and wait for the 2.4 GHz `3TSahur-Swarm` hotspot.
2. Power the camera from a stable regulated 5 V source. Open Serial Monitor at
   115200 baud.
3. A working board prints its hostname and stream URL, followed by
   `Camera registered with Pi dashboard.`
4. Test `http://larp-a-cam.local/status` and `/stream` from a device on the
   hotspot (replace `a` with `b` for the other Scout). Then select the matching
   LARP tab in the Pi dashboard; it uses the registered DHCP address and does
   not rely on browser `.local` lookup.

The firmware retries Wi-Fi without blocking, uses different retry intervals
for A and B to avoid lockstep reconnects, and caps video at 10 FPS. The
dashboard keeps only the selected camera feed open; optional vision, snapshots,
and profile changes pause or are deferred during robot movement so control
traffic stays available.

## Troubleshooting

| Symptom | What it means | What to do |
| --- | --- | --- |
| `main file missing from sketch` | The primary `.ino` name and its folder do not match. | Open `larp-esp32-cam.ino` directly and do not rename it alone. |
| `esp_camera.h: No such file or directory` | The ESP32 board package or board selection is wrong. | Install `esp32 by Espressif Systems 3.0.7` and select AI Thinker ESP32-CAM. |
| Upload cannot connect | The camera is not in flashing mode. | Connect GPIO0 to GND, reset, upload at 115200, then remove GPIO0-to-GND and reset for normal boot. |
| `Camera initialization failed` | Camera pin map, ribbon seating, or power is wrong. | Read the printed `esp_err`, select AI Thinker ESP32-CAM, confirm the pinout, reseat the ribbon, and use regulated 5 V with enough current. |
| Camera joins Wi-Fi but no dashboard image | The Pi has not received a current registration or cannot fetch the stream. | Confirm the serial message `Camera registered with Pi dashboard.`, then open `/status` and `/stream` directly. |
| Controls feel slow while video runs | Wi-Fi airtime is overloaded. | Keep one LARP tab/feed active, retain the 10 FPS cap, move closer to the Pi, and stop the robot before optional snapshots or vision use. |

The camera must use the Pi's 2.4 GHz WPA2-Personal/RSN hotspot. It does not
need WPA1 and will not join 5 GHz-only or WPA3-only service. Its camera ribbon
is unrelated to the ECHO's IPEX-1 Wi-Fi antenna; see the root
[LARP connectivity guide](../../README.md#larp-connectivity-beginner-setup-and-troubleshooting)
for ECHO antenna checks.
