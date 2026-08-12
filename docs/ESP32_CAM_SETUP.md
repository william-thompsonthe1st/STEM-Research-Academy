# Inland ESP32-CAM setup for LARP Scouts

Each LARP Scout uses two independent boards: its ECHO drive controller and an
Inland ESP32-CAM video node. The camera does not connect to, or control, the
ECHO motors. It mounts on the scout, receives stable power, joins the
3TSahur-Swarm Wi-Fi network, and streams video directly to the operator's
browser.

## Before connecting power

- Confirm that the Inland board is compatible with the common AI Thinker
  ESP32-CAM layout. Do not use this sketch on a different pinout without
  changing the pin definitions.
- Use a stable, regulated 5 V supply capable of at least 1 A for the camera.
  Do not power it from a Raspberry Pi GPIO pin or the ECHO controller's logic
  rail.
- Keep the camera and ECHO drive-controller grounds common only if they share
  a power system. Motor power must remain separately fused and switched.

## Camera board pin map used by the firmware

The following assignments are already encoded in
`firmware/larp-esp32-cam/larp_esp32_cam.ino`.

| Camera signal | ESP32-CAM GPIO |
| --- | ---: |
| PWDN | 32 |
| RESET | -1 (not connected) |
| XCLK | 0 |
| SIOD (SCCB data) | 26 |
| SIOC (SCCB clock) | 27 |
| D0 through D7 | 5, 18, 19, 21, 36, 39, 34, 35 |
| VSYNC / HREF / PCLK | 25 / 23 / 22 |

These are camera-module signals, not extra wires to the Pi. The Pi receives
the resulting MJPEG stream over Wi-Fi.

## Flash each camera

1. Install Arduino IDE and the **esp32 by Espressif Systems** board package.
2. Connect a USB-to-serial adapter for flashing:

   | USB-to-serial adapter | ESP32-CAM |
   | --- | --- |
   | 5 V | 5 V |
   | GND | GND |
   | TX | U0R / GPIO 3 |
   | RX | U0T / GPIO 1 |
   | GND, only while uploading | GPIO 0 |

3. Select the board profile that matches the printed module. For an
   AI Thinker-compatible camera, select **AI Thinker ESP32-CAM** and the
   correct serial port. Use a low upload speed if uploads are unreliable.
4. Open `firmware/larp-esp32-cam/larp_esp32_cam.ino`.
5. For Scout A, set `CAMERA_ID` to `'A'`; for Scout B, set it to `'B'`.
   Set `WIFI_SSID` and `WIFI_PASSWORD` to exactly match the Pi hotspot.
6. Upload. If the adapter cannot begin upload, hold the board's reset button
   briefly while the IDE starts connecting.
7. Remove the GPIO 0-to-ground upload jumper, reset the board, and reconnect
   only normal operating power. Leaving GPIO 0 grounded prevents normal boot.

### Flash through an Arduino UNO R4

This is a fallback for either UNO R4 Minima or UNO R4 WiFi. A dedicated 3.3 V
USB-to-UART adapter remains simpler because it may provide automatic reset and
does not need a relay sketch.

> **Voltage safety:** UNO R4 digital pins use 5 V logic. The ESP32 ROM loader
> uses a 3.3 V UART, and Espressif says not to connect it to 5 V TTL serial.
> Never wire UNO R4 D1/TX directly to ESP32-CAM U0R/GPIO 3.

Use a two-channel, UART-capable 5 V-to-3.3 V level shifter. A resistor divider
on UNO TX would protect the ESP input, but it only translates one direction.
The RA4M1 datasheet specifies a guaranteed HIGH input of up to `0.8 x VCC`
(4.0 V at 5 V), so the ESP's 3.3 V TX is not guaranteed to be recognized by
the UNO R4 without translation in the other direction too.

1. Select the exact UNO R4 model and its USB port in Arduino IDE. With D0/D1
   disconnected, upload:

   ```cpp
   void setup() {
     Serial.begin(115200);
     Serial1.begin(115200);  // UNO R4 D0/RX, D1/TX
   }

   void loop() {
     while (Serial.available()) Serial1.write(Serial.read());
     while (Serial1.available()) Serial.write(Serial1.read());
   }
   ```

2. Unplug USB and camera power before wiring. Use a separate regulated 5 V,
   at least 1 A camera supply. Join grounds, but do not join that supply's 5 V
   output to the UNO 5 V pin.
3. Power the shifter high side from UNO 5V and low side from UNO 3.3V. Connect:

   | Signal path | Connection |
   | --- | --- |
   | Host to camera | UNO D1/TX -> shifter 5 V side -> shifter 3.3 V side -> ESP U0R/GPIO 3 |
   | Camera to host | ESP U0T/GPIO 1 -> shifter 3.3 V side -> shifter 5 V side -> UNO D0/RX |
   | Reference | UNO GND, shifter GND, ESP GND, and camera-supply GND together |
   | Upload strap | ESP GPIO 0 -> GND only while flashing |

4. Hold GPIO 0 low and reset or power-cycle the ESP32-CAM. This selects the ROM
   serial bootloader; the UNO R4 has no DTR/RTS connection to do it for you.
5. Change the IDE board to **AI Thinker ESP32-CAM**, keep the **UNO R4 USB
   port** selected, set upload speed to **115200**, close Serial Monitor, and
   upload. The UNO R4 must run the bridge sketch; do not hold it in reset.
6. After upload, remove camera power, remove GPIO 0 from GND, and restore power.
   Reset the camera if necessary. Reopen Serial Monitor at 115200 for boot logs.

If the IDE cannot synchronize, recheck crossed TX/RX paths and the level
shifter directions, repeat the GPIO 0/reset sequence, try shorter wires, or use
a dedicated adapter. This technique relays UART only; it does not provide
automatic boot/reset control or a dependable camera power supply.

Primary references: [Arduino UNO R4 Minima](https://docs.arduino.cc/hardware/uno-r4-minima),
[Arduino UNO R4 WiFi](https://docs.arduino.cc/hardware/uno-r4-wifi/), [RA4M1
electrical characteristics](https://docs.arduino.cc/resources/datasheets/ra4m1-datasheet.pdf),
[Espressif 3.3 V serial connection](https://docs.espressif.com/projects/esptool/en/latest/esp32/esptool/serial-connection.html),
and [ESP32 boot-mode selection](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html).

The firmware waits for Wi-Fi without blocking, retries every five seconds, and
starts its HTTP stream after it joins the hotspot. It serves at most 10 frames
per second so drive commands keep priority on the shared network.

## Verify the feed

1. Power 3TSahur and wait for the `3TSahur-Swarm` hotspot.
2. Power the matching camera and open its serial monitor at 115200 baud. A
   successful connection prints the camera hostname and stream address.
3. From a device on the hotspot, open:

   ```text
   http://larp-a-cam.local/status
   http://larp-a-cam.local/stream
   ```

   Replace `a` with `b` for Scout B.
4. Open the matching LARP tab in the 3TSahur dashboard. The selected tab opens
   that feed automatically; inactive tabs intentionally close their streams to
   preserve Wi-Fi bandwidth for robot controls.

If `.local` names do not resolve, use the IP address printed by the serial
monitor. On the Pi, set that stream URL in
`/etc/stem-research-academy/config.env`, then restart the dashboard:

```bash
sudoedit /etc/stem-research-academy/config.env
# LARP_A_CAMERA_URL=http://10.42.0.31/stream
# LARP_B_CAMERA_URL=http://10.42.0.32/stream
sudo systemctl restart stem-robot-dashboard
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No serial boot or repeated brownout | Use a regulated 5 V supply and short power leads; camera startup can draw more current than a USB adapter provides. |
| `Camera initialization failed` | Confirm the Inland board uses the AI Thinker-compatible pin map and that the ribbon cable is seated. |
| Camera joins Wi-Fi but no dashboard image | Open `/status` and `/stream` directly, then verify `LARP_A_CAMERA_URL` or `LARP_B_CAMERA_URL`. |
| Camera cannot join the hotspot | Use the 2.4 GHz `3TSahur-Swarm` network, verify the password, and keep it at least eight characters. |
| Controls become slow while video runs | Verify only one dashboard tab is active, keep the 10 FPS firmware setting, and move the cameras closer to the Pi hotspot. |

## CSI presence display

The camera is the verification tool. The separate ECHO controller measures
Wi-Fi Channel State Information (CSI) and reports a disturbance level through
its `/status` endpoint. The dashboard presents that as a **possible presence**
indicator and a 0-100% signal-variance meter. It cannot identify a person,
measure distance, or be used as the sole safety sensor. Confirm any indication
with the LARP camera before acting.
