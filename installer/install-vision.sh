#!/usr/bin/env bash
# Optional pretrained Ultralytics YOLO11n + NCNN setup.
set -Eeuo pipefail

APP_DIR="${STEM_APP_DIR:-$HOME/STEMResearchAcademy}"
VISION_ENV="$APP_DIR/.vision-venv"
CONFIG_FILE="/etc/stem-research-academy/config.env"
DASHBOARD_PYTHON="$APP_DIR/.venv/bin/python"
WEIGHTS_NAME="yolo11n.pt"
IMAGE_SIZE="${VISION_IMAGE_SIZE:-320}"
MODEL_DIR="$APP_DIR/yolo11n_ncnn_model"

if [ "$(id -u)" -eq 0 ]; then
    echo "Run this as the normal Raspberry Pi user, without sudo." >&2
    exit 1
fi
[ -f "$APP_DIR/run.py" ] || { echo "Application not found at $APP_DIR. Run the base installer first." >&2; exit 1; }
[ -x "$DASHBOARD_PYTHON" ] || { echo "Dashboard Python runtime is missing." >&2; exit 1; }
[ -f "$CONFIG_FILE" ] || { echo "Dashboard configuration is missing." >&2; exit 1; }

python3 - <<'PY'
import platform, sys
print("Vision Python:", sys.version.split()[0], platform.machine())
if sys.version_info < (3, 8):
    raise SystemExit("Ultralytics requires Python 3.8 or newer")
PY

echo "Creating a clean optional vision environment..."
python3 -m venv --clear --system-site-packages "$VISION_ENV"
"$VISION_ENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VISION_ENV/bin/python" -m pip install "ultralytics>=8.3,<9" ncnn

"$VISION_ENV/bin/python" - <<'PY'
import torch, torchvision, ncnn, ultralytics
from ultralytics import YOLO
print("Ultralytics:", ultralytics.__version__)
print("PyTorch:", torch.__version__)
print("Torchvision:", torchvision.__version__)
print("YOLO Python API: OK")
PY

echo "Exporting pretrained YOLO11n to NCNN at ${IMAGE_SIZE}px..."
(
    cd "$APP_DIR"
    IMAGE_SIZE="$IMAGE_SIZE" "$VISION_ENV/bin/python" - <<'PY'
import os
from ultralytics import YOLO
model = YOLO("yolo11n.pt")
print("NCNN export:", model.export(format="ncnn", imgsz=int(os.environ["IMAGE_SIZE"])))
PY
)

[ -d "$MODEL_DIR" ] || { echo "Expected model directory missing: $MODEL_DIR" >&2; exit 1; }
VISION_SITE_PACKAGES="$("$VISION_ENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"

"$DASHBOARD_PYTHON" - "$VISION_SITE_PACKAGES" "$MODEL_DIR" <<'PY'
import site, sys
from pathlib import Path
site_packages, model_path = sys.argv[1:]
if not Path(site_packages).is_dir():
    raise RuntimeError("Vision site-packages directory is missing")
if not Path(model_path).is_dir():
    raise RuntimeError("YOLO11n NCNN model directory is missing")
site.addsitedir(site_packages)
from ultralytics import YOLO
YOLO(model_path)
print("Dashboard YOLO11n load check: OK")
PY

sudo sed -i -E '/^(VISION_SITE_PACKAGES|VISION_MODEL|VISION_IMAGE_SIZE)=/d' "$CONFIG_FILE"
printf 'VISION_SITE_PACKAGES=%s\n' "$VISION_SITE_PACKAGES" | sudo tee -a "$CONFIG_FILE" >/dev/null
printf 'VISION_MODEL=%s\n' "$MODEL_DIR" | sudo tee -a "$CONFIG_FILE" >/dev/null
printf 'VISION_IMAGE_SIZE=%s\n' "$IMAGE_SIZE" | sudo tee -a "$CONFIG_FILE" >/dev/null
sudo systemctl restart stem-robot-dashboard.service

echo "YOLO11n setup complete. Reload the dashboard and press C to toggle Vision."
