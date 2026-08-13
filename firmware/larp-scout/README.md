# LARP scout drive firmware

This package runs the differential-drive controller on each LARP scout's ECHO
board. Flash `larp_scout_controller.ino` with `ROBOT_ID = 'A'` or `ROBOT_ID =
'B'`. It joins `3TSahur-Swarm`, reports a heartbeat to the 3TSahur hub, serves
`/drive`, `/stop`, and `/status`, and stops motors after 500 ms without a valid
command.

The LARP drive controller and its separate Inland ESP32-CAM must use the same
`A` or `B` identity. Confirm the ECHO motor IDs and direction with wheels
raised before ground operation.

## Upload one board at a time

Use **ESP32S3 Dev Module** in Arduino IDE with the `esp32 by Espressif
Systems` package and the EchoLib dependencies documented by 3DBuffalo. Match
the board-package version, serial port, USB data cable, and upload speed
(`115200`) of the working ECHO board. The LARP sketch targets the ECHO's
ESP32-S3; do not select an ESP32-CAM profile for this controller.

If Arduino says `Failed to connect to ESP32-S3: No serial data received` or
links to Espressif troubleshooting, compilation has already finished. This is
the ECHO bootloader/upload path. Close Serial Monitor, disconnect any external
serial connection, then hold **PROG** for about five seconds, press and release
**RESET** while still holding **PROG**, wait for the newly enumerated serial
port, and upload again. Use a direct data-capable USB cable and stable board
power. See [ECHO basic setup](https://3dbuffalo.gitbook.io/echolib/getting-started/basic-setup-+-first-program) and [Espressif's ESP32-S3 troubleshooting](https://docs.espressif.com/projects/esptool/en/latest/esp32s3/troubleshooting.html).

## Wi-Fi and IPEX-1 antenna check

`WIFI_SSID` and `WIFI_PASSWORD` in `larp_scout_controller.ino` must match the
Pi's `/etc/stem-research-academy/config.env` values exactly. The project
hotspot is 2.4 GHz `bg` mode, channel 6, with WPA2-Personal/RSN; keep it on
2.4 GHz and do not make it WPA3-only. Change a credential only as a
coordinated update:
change the Pi configuration, both ECHO sketches, and both ESP32-CAM sketches,
then reflash all Wi-Fi boards.

The IPEX-1 antenna is hardware, not a sketch option. With the ECHO powered
off, press a known-good 2.4 GHz IPEX-1 antenna connector straight onto the
socket until fully seated. Route the antenna away from motor/battery wiring
and metal chassis parts, and do not operate the ECHO without its required
antenna. The Zippy/ECHO product information identifies the external IPEX-1
antenna connection: [Zippy](https://www.3dbuffalo.co/product-page/zippy) and
[ECHO](https://www.3dbuffalo.co/echo).
