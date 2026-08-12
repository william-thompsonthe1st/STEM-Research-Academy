# 3TSahur auxiliary actuator setup requirements

The 3TSahur dashboard includes a staged control surface for the Logitech C270
pan/tilt gimbal and the two-servo ramp. It is safe to deploy before the servo
hardware details are known: the current implementation has **no GPIO, I2C,
PWM, or servo-driver dependency**, so it cannot emit a servo signal.

## Current controls

| Feature | Dashboard control | Keyboard control | Current behavior |
| --- | --- | --- | --- |
| Camera gimbal mode | **Gimbal mode** button | `G`, then arrow keys | Records requested pan/tilt in 10° planning steps. |
| Camera gimbal buttons | Pan left/right and tilt up/down | — | Records requested direction/position. |
| Ramp door | **Raise/Lower ramp** button | `R` | Records requested `up` or `down` state. |

These controls appear only on the **3TSahur** tab. They do not affect LARP
controls, mecanum drive commands, the motor watchdog, or the emergency stop.

## Information required before hardware output is enabled

Provide all of the following before adding a driver adapter or pin/channel
mapping:

1. **Exact servo driver model and board photo.** Identify whether it is an I2C
   PWM board, a direct Pi PWM solution, or another controller.
2. **Driver communication details.** I2C address/bus or other required
   interface details. Do not assume a PCA9685-compatible board from appearance.
3. **Servo channel plan.** The four driver channels for pan, tilt, ramp-left,
   and ramp-right. The current code deliberately does not assign any.
4. **Power plan.** Servo supply voltage, current rating, fuse/switch approach,
   and where the Pi, driver, and servo-supply grounds meet. Never power these
   servos from a Pi GPIO pin.
5. **Servo details.** Make/model, operating voltage, travel range, and horn
   orientation for the standard pan servo, micro tilt servo, and two ramp
   servos.
6. **Mechanical calibration.** Safe minimum/maximum pulse or angle for each
   servo with no binding. For the ramp, state whether the two servos must move
   in the same or mirrored direction.
7. **Fail-safe behavior.** Confirm whether ramp movement should stop/hold when
   Wi-Fi disconnects and whether its default after boot should be fully raised
   or lowered.

## Safe commissioning order

1. Keep the mecanum motor supply disconnected and support the robot so neither
   the wheels nor ramp can contact people or objects.
2. Test one servo at a time from the driver with an unloaded linkage.
3. Calibrate and record safe end limits before installing horns/linkages.
4. Connect the gimbal, verify pan and tilt directions at low travel, then test
   the ramp without load.
5. Confirm the ramp-left and ramp-right servos remain mechanically synchronized.
6. Only then enable dashboard output and perform a low-speed integrated test.

## Software boundary

The staged API endpoints are:

- `GET /api/status` → `actuators`
- `POST /api/actuators/gimbal` with `{ "pan": number, "tilt": number }`
- `POST /api/actuators/ramp` with `{ "state": "up" | "down" }`

They validate and retain desired state only. Until a hardware-specific adapter
is intentionally added, status reports `configured: false` and **no servo
output is active**.
