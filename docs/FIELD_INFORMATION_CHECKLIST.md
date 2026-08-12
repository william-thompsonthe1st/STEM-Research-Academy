# Field information checklist

Bring or send this information before the next hardware-specific change. Clear
photos are useful when they include the connector labels and board markings.

## 3TSahur Raspberry Pi and mecanum

- [ ] Raspberry Pi OS version and whether the dashboard installer completed.
- [ ] Output from `ip addr`, `nmcli device status`, and the dashboard service
  status after boot.
- [ ] C270 device path from `v4l2-ctl --list-devices` and a photo of the USB
  connection if it is not detected.
- [ ] A photo of both motor drivers and every Pi-to-driver signal connection.
- [ ] Raised-wheel test results for forward, reverse, strafe, and rotation.
- [ ] The real command delay observation: which robot, camera profile, number
  of active streams, approximate delay, and whether it repeats after reboot.

## LARP Scout A and B connectivity

- [ ] The exact 3D Buffalo/ECHO controller model and a photo of both sides.
- [ ] The final `ROBOT_ID` (`A` or `B`) for each physical controller.
- [ ] Serial-monitor output from each controller while joining
  `3TSahur-Swarm`.
- [ ] The IP address, RSSI, and `/status` response for each scout after it
  joins the hotspot.
- [ ] The dashboard symptom if a scout does not connect: waiting heartbeat,
  connected/no drive, or drive timeout.
- [ ] Confirmation that the retained ECHO motor connections have not changed.

## Inland ESP32-CAM A and B

- [ ] A readable photo of both sides of each camera board and the camera-ribbon
  connector.
- [ ] Whether the board has a built-in USB uploader or requires a serial bridge.
- [ ] The selected Arduino board profile and upload log for each camera.
- [ ] `CAMERA_ID` and the stream URL/IP for each camera.
- [ ] A direct browser test of each camera's `/status` and `/stream` endpoint.
- [ ] The regulated 5 V camera-power source, current rating, and wiring photo.

## Planned gimbal and ramp

- [ ] Exact servo-driver board model, board photo, and data sheet/product link.
- [ ] Driver bus/address details and its four intended channels: pan, tilt,
  ramp-left, ramp-right.
- [ ] Servo make/model, operating voltage, travel range, and horn orientation.
- [ ] Servo supply voltage/current rating, fuse/switch plan, and common-ground
  arrangement with the Pi.
- [ ] Safe mechanical end limits for pan, tilt, and both ramp servos.
- [ ] Whether ramp-left and ramp-right must move in the same or mirrored
  direction, plus the preferred boot/fail-safe ramp position.

## Recommended first-session evidence

- [ ] A short video of raised-wheel drive tests.
- [ ] One screenshot per dashboard tab showing 3TSahur, LARP A, and LARP B.
- [ ] A timestamped note of latency with camera/YOLO/dead-man settings.
- [ ] Any terminal or Arduino error text copied exactly, not paraphrased.
