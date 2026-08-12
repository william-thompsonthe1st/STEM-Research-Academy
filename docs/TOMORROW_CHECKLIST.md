# Tomorrow field checklist

Use this list in order. Keep the wheels raised and motor power disconnected
until each relevant software check has passed.

## 1. Bring the current system online

- [ ] Pull the latest `agent/integrate-3tsahur-larp` branch and run the normal installer/update procedure on the Pi.
- [ ] Confirm the dashboard opens at `http://10.42.0.1` and the health panel reports the expected Pi/camera state.
- [ ] Confirm C270 video in **Control Priority**, then **Balanced**. Do not choose Detail until the first two profiles are stable.
- [ ] Confirm LARP A and B heartbeat, drive status, CSI display, and their ESP32-CAM streams one at a time.
- [ ] Test `Space`, `Esc`, browser disconnect, and dead-man release with all wheels raised. Each must stop motion promptly.

## 2. Record the data needed for the new servo work

- [ ] BCM GPIO pin for gimbal pan, gimbal tilt, ramp servo 1, and ramp servo 2.
- [ ] Exact servo make/model for all four servos, including standard versus micro servo and any supplied pulse-width range.
- [ ] Mechanically safe minimum, center, and maximum angles for pan and tilt.
- [ ] Ramp **closed** and **open** angles for both servos, and whether the ramp servos move in the same or opposite directions.
- [ ] A photo or simple labeled wiring diagram of the servo signal, power, and ground connections.
- [ ] Servo power-source voltage/current rating and confirmation that it is external—not Pi 5 V—with a common logic ground to the Pi.
- [ ] Desired UI/keyboard controls, movement speed, and whether the ramp needs an intermediate position.

## 3. Capture deployment facts

- [ ] Actual C270 device path from `v4l2-ctl --list-devices`.
- [ ] LARP A/B IP addresses and, if mDNS fails, working camera stream URLs.
- [ ] CSI calibration results with the area clear: baseline and suggested threshold for each LARP.
- [ ] YOLO result at 320px on one feed: whether controls remain responsive.
- [ ] Gamepad browser/model and its observed stick/button mapping.

## 4. Capture performance evidence

| Condition | Target observation |
| --- | --- |
| Control Priority, no YOLO | Immediate response; no recurring delay. |
| Balanced, one stream | Immediate response; stable camera. |
| YOLO enabled on selected tab | Controls remain responsive; lower vision FPS if not. |
| LARP A then LARP B | Each responds independently; inactive feed stays closed. |
| Dead-man/gamepad | Motion stops immediately when the hold control is released. |

## 5. Send back to continue development

Send the pin/servo details above, photos of physical servo wiring, safety/performance results, any dashboard screenshot/error text, and your preferred gimbal/ramp controls. That is sufficient to add the servo module without guessing wiring or mechanical limits.
