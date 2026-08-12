# Pretrained vision setup (Raspberry Pi 4)

This guide prepares the 3TSahur Raspberry Pi for **pretrained person detection**. It uses Ultralytics YOLO11 Nano (`yolo11n`), whose standard weights are trained on the COCO dataset. No dataset collection, labeling, or training is required.

> Current repository status: the dashboard and robot-control service do not yet launch a YOLO process. This guide installs and verifies the model in an isolated environment, ready for a future optional dashboard integration. It does not change the motor GPIO mapping, LARP firmware, or control service.

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

Do not run model installation as `root`, and do not install the ML packages into `/usr/lib/python3`. The separate environment below keeps the established dashboard dependencies unchanged.

## Install YOLO11 Nano and NCNN

Run these commands as the Pi's normal user after the base project is installed:

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
2. Confirm the selected LARP tab plays `http://larp-a-cam.local/stream` or `http://larp-b-cam.local/stream` (or its configured static-IP fallback).
3. Keep only the selected dashboard stream open. The existing dashboard does this automatically to preserve Wi-Fi capacity for robot control.
4. Start with **one** vision source at a time. Do not run inference on both ESP32-CAM streams and the C270 simultaneously on a Pi 4.

The ESP32-CAM stream itself does not need new firmware for this model. It must simply be reachable by the Pi and produce a valid MJPEG stream.

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

When vision is integrated into the dashboard, it must run in a separate worker, process only the newest available frame, and drop stale frames. It must never wait in a motor-command request path. The dashboard's current one-active-camera policy should remain in place.

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
