# Pretrained vision setup (Raspberry Pi 4)

This guide prepares the 3TSahur Raspberry Pi for **pretrained person detection**. It uses Ultralytics YOLO11 Nano (`yolo11n`), whose standard weights are trained on the COCO dataset. No dataset collection, labeling, or training is required.

> Current repository status: vision is optional and starts only after an operator enables it for a camera. It runs in an isolated background worker; it does not change the motor GPIO mapping, LARP firmware, or control service.

## What the model does

The included COCO weights recognize 80 common object categories. For this project, begin with COCO class `0` (`person`) only. The model returns confidence-scored bounding boxes that can be drawn onto a camera frame. Treat the output as an operator aid, not a safety decision or proof of identity.

Relevant upstream documentation:

- [YOLO11 pretrained models](https://docs.ultralytics.com/models/yolo11/)
- [Ultralytics NCNN export](https://docs.ultralytics.com/integrations/ncnn/)
- [Ultralytics Raspberry Pi deployment guidance](https://docs.ultralytics.com/guides/raspberry-pi/)

## Prerequisites

- Raspberry Pi 4 Model B (4 GB) running a current **64-bit Raspberry Pi OS**.
- The normal 3TSahur installation completed first. It provides Python 3, OpenCV, the Logitech C270 setup, and the dashboard service.
- A stable internet connection for the one-time Python package, model-weight, and NCNN export downloads. Normal driving and existing camera streaming do not need internet after setup.
- At least 3 GB of free storage and a stable Pi power supply. ML packages and model conversion use more space and CPU than the base dashboard.
- The C270 connected and visible as `/dev/video0` (or the configured camera device). Use `v4l2-ctl --list-devices` to check.

Do not run model installation as `root`, and do not install the ML packages into `/usr/lib/python3`. The separate environment below keeps the established dashboard dependencies unchanged. The project installer records this environment for the dashboard automatically; the dashboard loads it only when an operator enables Vision.

## Install YOLO11 Nano and NCNN

The recommended path is the one-command installer from the root README. It
installs the model, verifies the dashboard can import it, updates the protected
vision setting, and restarts the dashboard. If you instead install manually,
run these commands as the Pi's normal user after the base project is installed:

```bash
cd ~/STEMResearchAcademy
python3 -m venv --system-site-packages .vision-venv
source .vision-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ultralytics>=8.3,<9" ncnn
```

The first package install can take several minutes on a Pi. If it fails due to storage pressure, stop, free space, and retry—do not delete the robot project or its `/etc/stem-research-academy/config.env` file.

## Download and export the pretrained model

Run this once while the vision environment is active:

```bash
python - <<'PY'
from ultralytics import YOLO

# Downloads pretrained COCO weights; this is not a training step.
model = YOLO("yolo11n.pt")

# NCNN is the embedded-friendly runtime used for Pi inference.
model.export(format="ncnn", imgsz=320)
print("Created yolo11n_ncnn_model/ in the current directory.")
PY
```

Keep the resulting `yolo11n_ncnn_model/` directory with the application. If the Pi must be offline later, create the export once on a connected Pi and retain that directory; neither weights nor a dataset need to be downloaded again for inference.

For a manual installation, make the separate vision environment visible to the
dashboard once, then restart the service:

```bash
VISION_SITE_PACKAGES="$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
sudo sed -i -E '/^VISION_SITE_PACKAGES=/d' /etc/stem-research-academy/config.env
printf 'VISION_SITE_PACKAGES=%s\n' "$VISION_SITE_PACKAGES" | sudo tee -a /etc/stem-research-academy/config.env
sudo systemctl restart stem-robot-dashboard
```

## Enable or disable vision in the dashboard

After the installer reports that its dashboard import/model check passed,
reload the dashboard. Select one robot tab and use its Vision button or press
`C` to toggle that camera's inference on and off. No further code changes are
required after the successful installer run. Vision is per camera and pauses
while a Pi or LARP drive command is active; it resumes after the robot stops.

Open a robot tab and press `C`, or select its **Vision off · C** button. The control is per camera: 3TSahur's C270, LARP Scout A, and LARP Scout B each keep their own state. When enabled, the dashboard overlays current `person` boxes and confidence scores; press `C` again to immediately stop future inference for that selected feed.

Vision is deliberately disabled after a dashboard restart. A missing model, missing `ultralytics`/`ncnn` package, unavailable camera, or unreachable LARP stream reports as **Vision unavailable** in the video pane. Those conditions do not disable driving, emergency stop, the motor watchdog, camera streaming, or CSI status.

## Verify the Logitech C270 and create a visual preview

This one-frame check writes a labelled image to `/tmp` without touching the dashboard service or motor controls:

```bash
cd ~/STEMResearchAcademy
source .vision-venv/bin/activate
python - <<'PY'
import cv2
from ultralytics import YOLO

camera = cv2.VideoCapture(0)
if not camera.isOpened():
    raise RuntimeError("C270 could not be opened. Check CAMERA_DEVICE and USB power.")

ok, frame = camera.read()
camera.release()
if not ok:
    raise RuntimeError("C270 opened but did not return a frame.")

model = YOLO("yolo11n_ncnn_model")
results = model(frame, classes=[0], conf=0.45, imgsz=320, verbose=False)
cv2.imwrite("/tmp/3tsahur-yolo-preview.jpg", results[0].plot())
print("Saved /tmp/3tsahur-yolo-preview.jpg")
PY
```

Open `/tmp/3tsahur-yolo-preview.jpg` on the Pi display. A person in view should have a labelled bounding box. An image with no box is valid when no person meets the confidence threshold.

## LARP ESP32-CAM feed prerequisites

Before using a LARP feed for vision:

1. Complete [ESP32_CAM_SETUP.md](ESP32_CAM_SETUP.md) for the appropriate camera.
2. Confirm the selected LARP tab plays the Pi-relayed camera feed after the
   ESP32-CAM log prints `Camera registered with Pi dashboard.` The direct
   `http://larp-a-cam.local/stream` or `http://larp-b-cam.local/stream` address
   (or a configured static-IP fallback) is only a diagnostic fallback.
3. Keep only the selected dashboard stream open. The existing dashboard does this automatically to preserve Wi-Fi capacity for robot control.
4. Start with **one** vision source at a time. Do not run inference on both ESP32-CAM streams and the C270 simultaneously on a Pi 4.

The ESP32-CAM must run the current firmware so it can register its changing
DHCP address with the Pi and produce a valid MJPEG stream.

## Performance and safe operating settings

Use these initial settings for the Pi 4:

| Setting | Start with | Why |
| --- | --- | --- |
| Model | `yolo11n_ncnn_model` | Smallest YOLO11 detection model. |
| Input size | `320` | Reduces CPU load compared with 640px inference. |
| Classes | `[0]` | Limits detection to people. |
| Confidence | `0.45` | Reasonable initial balance; tune only after observing your own space. |
| Inference rate | 2–5 FPS | Video can remain smooth while the Pi has time for controls. |
| Vision sources | One active tab/feed | Avoids competing inference, video, and Wi-Fi workloads. |

The included implementation runs inference in a separate worker and never waits in a motor-command request path. If you enable more than one feed, the worker samples them in turn; for the best Pi 4 responsiveness, leave vision enabled on only the tab you are watching.

## Benchmark before enabling it during driving

Run the repository tests first:

```bash
cd ~/STEMResearchAcademy
.venv/bin/python -m unittest discover -s tests -v
```

Then, with wheels raised, run the preview repeatedly while a second device uses the dashboard. Verify that controls stay responsive and that `Space` and `Esc` immediately stop motion. Start at 2 FPS and 320px; lower the inference rate or disable vision if control, Wi-Fi, temperature, or power stability is affected.

The existing simulation suite validates application control paths, not camera-to-model speed on physical Pi hardware. Measure final performance on the deployed Pi with the actual C270 and one actual ESP32-CAM feed.

## Optional future additions

After basic person detection is stable, the model can be connected to the currently selected dashboard tab to display its latest labelled frame and status. A tracker such as ByteTrack can be evaluated later if persistent object IDs are useful, but initial deployment should use detection alone to minimize overhead. See the [Ultralytics tracking guide](https://docs.ultralytics.com/modes/track/).
