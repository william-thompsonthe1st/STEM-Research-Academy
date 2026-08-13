#!/usr/bin/env bash
# Optional pretrained YOLO11 Nano + NCNN setup for an already-installed Pi hub.
set -Eeuo pipefail

APP_DIR="${STEM_APP_DIR:-$HOME/STEMResearchAcademy}"
VISION_ENV="$APP_DIR/.vision-venv"
CONFIG_FILE="/etc/stem-research-academy/config.env"
DASHBOARD_PYTHON="$APP_DIR/.venv/bin/python"
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
[ -x "$DASHBOARD_PYTHON" ] || {
    echo "Dashboard Python runtime not found at $DASHBOARD_PYTHON. Run the base installer first." >&2
    exit 1
}
[ -f "$CONFIG_FILE" ] || {
    echo "Dashboard configuration not found at $CONFIG_FILE. Run the base installer first." >&2
    exit 1
}
command -v sudo >/dev/null 2>&1 || {
    echo "sudo is required to update the dashboard vision setting." >&2
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

VISION_SITE_PACKAGES="$("$VISION_ENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"

echo "Verifying the dashboard can load the optional vision environment..."
"$DASHBOARD_PYTHON" - "$VISION_SITE_PACKAGES" "$APP_DIR/yolo11n_ncnn_model" <<'PY'
import site
import sys
from pathlib import Path

site_packages, model_path = sys.argv[1:]
if not Path(site_packages).is_dir():
    raise RuntimeError(f"Vision site-packages directory is missing: {site_packages}")
if not Path(model_path).is_dir():
    raise RuntimeError(f"Exported NCNN model is missing: {model_path}")
site.addsitedir(site_packages)
from ultralytics import YOLO
YOLO(model_path)
print("Dashboard vision import and model load passed.")
PY

# The dashboard normally runs from .venv; point it at the separately managed
# ML environment only when a Vision toggle is used. Preserve every other Pi
# setting, including hotspot credentials and camera addresses.
sudo sed -i -E '/^VISION_SITE_PACKAGES=/d' "$CONFIG_FILE"
printf 'VISION_SITE_PACKAGES=%s\n' "$VISION_SITE_PACKAGES" | sudo tee -a "$CONFIG_FILE" >/dev/null
sudo systemctl restart stem-robot-dashboard.service

echo "Optional vision setup complete. Reload the dashboard, select one robot tab, then use Vision or C to toggle it on/off."
