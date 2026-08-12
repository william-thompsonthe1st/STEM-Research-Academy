# LARP ESP32-CAM firmware

This package provides the video node for each LARP reconnaissance scout. Flash
`larp-esp32-cam.ino` to an Inland ESP32-CAM-compatible board, setting
`CAMERA_ID` to `A` or `B` before each upload. It joins `3TSahur-Swarm` and
serves an MJPEG stream at `http://larp-a-cam.local/stream` or
`http://larp-b-cam.local/stream`.

The default pins target the common AI Thinker-compatible Inland ESP32-CAM.
Verify the module's printed pinout and power it from a stable supply before
flashing or using it. The camera board does not drive the scout motors.
