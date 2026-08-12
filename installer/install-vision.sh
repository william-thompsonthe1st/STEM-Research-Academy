#!/usr/bin/env bash
# Optional pretrained YOLO11 Nano + NCNN setup for an already-installed Pi hub.
set -Eeuo pipefail

APP_DIR="${STEM_APP_DIR:-$HOME/STEMResearchAcademy}"
VISION_ENV="$APP_DIR/.vision-venv"
MODEL_NAME="${VISION_MODEL:-yolo11n.pt}"
IMAGE_SIZE="${VISION_IMAGE_SIZE:-320}"

if [ "$(id -u)" -eq 0 ]; then
    echo "Run this as the normal Raspberry Pi user, without sudo." >&2
    exit 1
fi
[ -f "$APP_DIR/run.py" ] || {
    echo "3TSahur application not found at $APP_DIR. Run the base installer first." >&2
    exit 1
}

echo "Creating optional vision environment..."
python3 -m venv --system-site-packages "$VISION_ENV"
"$VISION_ENV/bin/python" -m pip install --upgrade pip
"$VISION_ENV/bin/python" -m pip install "ultralytics>=8.3,<9" ncnn

echo "Downloading pretrained weights and exporting NCNN at ${IMAGE_SIZE}px..."
(
    cd "$APP_DIR"
    MODEL_NAME="$MODEL_NAME" IMAGE_SIZE="$IMAGE_SIZE" "$VISION_ENV/bin/python" - <<'PY'
import os
from ultralytics import YOLO
model = YOLO(os.environ["MODEL_NAME"])
model.export(format="ncnn", imgsz=int(os.environ["IMAGE_SIZE"]))
print("Vision model export complete.")
PY
)

echo "Optional vision setup complete. Restart the dashboard, then enable Vision from a robot tab."
