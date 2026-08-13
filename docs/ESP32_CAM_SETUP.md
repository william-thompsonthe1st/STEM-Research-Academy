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

The firmware waits for Wi-Fi without blocking and retries every 2.0 seconds on
Camera A or 2.4 seconds on Camera B. The different retry intervals prevent the
two cameras from retrying in lockstep after the Pi hotspot restarts. It retries
its HTTP server while Wi-Fi remains connected, reuses that server after a
temporary Wi-Fi drop, and registers its current DHCP address directly with the
Pi dashboard every four seconds. It serves at most 10 frames per second so
drive commands keep priority on the shared network.

## Verify the feed

1. Power 3TSahur and wait for the `3TSahur-Swarm` hotspot.
2. Power the matching camera and open its serial monitor at 115200 baud. A
   successful connection prints the camera hostname and stream address, then
   `Camera registered with Pi dashboard.`
3. From a device on the hotspot, open:

   ```text
   http://larp-a-cam.local/status
   http://larp-a-cam.local/stream
   ```

   Replace `a` with `b` for Scout B.
4. Open the matching LARP tab in the 3TSahur dashboard. The selected tab opens
   the Pi-relayed feed automatically; it does not depend on `.local` name
   resolution. Inactive tabs intentionally close their streams to preserve
   Wi-Fi bandwidth for robot controls.

The Pi learns each newly flashed camera's DHCP address automatically. If you
must operate an older, unflashed camera firmware, use the IP address printed by
its serial monitor and set that stream URL in
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
| Camera joins Wi-Fi but no dashboard image | Confirm the serial log says `Camera registered with Pi dashboard.` Then open `/status` and `/stream` directly. `LARP_A_CAMERA_URL` or `LARP_B_CAMERA_URL` is the legacy fallback. |
| Camera cannot join the hotspot | Use the 2.4 GHz `3TSahur-Swarm` network, verify the password, and keep it at least eight characters. |
| Controls become slow while video runs | Verify only one dashboard tab is active, keep the 10 FPS firmware setting, and move the cameras closer to the Pi hotspot. |

## CSI presence display

The camera is the verification tool. The separate ECHO controller measures
Wi-Fi Channel State Information (CSI) and reports a disturbance level through
its `/status` endpoint. The dashboard presents that as a **possible presence**
indicator and a 0-100% signal-variance meter. It cannot identify a person,
measure distance, or be used as the sole safety sensor. Confirm any indication
with the LARP camera before acting.
