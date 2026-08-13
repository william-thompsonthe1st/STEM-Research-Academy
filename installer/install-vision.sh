#!/usr/bin/env bash
# Optional pretrained Ultralytics YOLO11n -> NCNN deployment for 3TSAHUR.
# The ML runtime is isolated from the base dashboard environment and is only
# activated after export, inference, and dashboard health checks pass.
set -Eeuo pipefail

APP_DIR="${STEM_APP_DIR:-$HOME/STEMResearchAcademy}"
VISION_ROOT="${STEM_VISION_DIR:-$HOME/.local/share/stem-research-academy/vision}"
VISION_ENV="$VISION_ROOT/.vision-venv"
MODEL_NAME="yolo11n.pt"
MODEL_DIR="$VISION_ROOT/yolo11n_ncnn_model"
IMAGE_SIZE="${VISION_IMAGE_SIZE:-320}"
CONFIG_FILE="/etc/stem-research-academy/config.env"
MANIFEST="$VISION_ROOT/deployment-manifest.txt"

fail() { printf 'Vision installation failed: %s\n' "$*" >&2; exit 1; }

set_config_key() {
    local key="$1" value="$2" temporary
    temporary="$(mktemp)"
    sudo awk -v key="$key" -v value="$value" '
        BEGIN { replaced = 0 }
        index($0, key "=") == 1 {
            if (!replaced) print key "=" value
            replaced = 1
            next
        }
        { print }
        END { if (!replaced) print key "=" value }
    ' "$CONFIG_FILE" > "$temporary" || { rm -f -- "$temporary"; return 1; }
    sudo install -o root -g root -m 0600 "$temporary" "$CONFIG_FILE" || {
        rm -f -- "$temporary"; return 1;
    }
    rm -f -- "$temporary"
}

[ "$(id -u)" -ne 0 ] || fail "run this as the normal Raspberry Pi user, without sudo."
[ -f "$APP_DIR/run.py" ] || fail "3TSAHUR application not found at $APP_DIR. Run the base installer first."
[ -f "$APP_DIR/installer/start-dashboard.sh" ] || fail "dashboard launcher is missing. Pull the latest branch and rerun the base installer."
command -v sudo >/dev/null 2>&1 || fail "sudo is required."
command -v python3 >/dev/null 2>&1 || fail "python3 is not installed."
sudo test -f "$CONFIG_FILE" || fail "$CONFIG_FILE is missing. Run the base installer first."
[ "$(getconf LONG_BIT)" = "64" ] || fail "YOLO11n on this project requires a 64-bit Raspberry Pi OS userspace."

available_kb="$(df -Pk "$HOME" | awk 'END {print $4}')"
[ -n "$available_kb" ] && [ "$available_kb" -ge 3145728 ] || fail "at least 3 GB of free storage is required for installation/export."

printf 'Creating isolated YOLO11n runtime at %s...\n' "$VISION_ENV"
mkdir -p "$VISION_ROOT"
python3 -m venv --clear --system-site-packages "$VISION_ENV"
PIP_NO_CACHE_DIR=1 "$VISION_ENV/bin/python" -m pip install --upgrade pip setuptools wheel
PIP_NO_CACHE_DIR=1 "$VISION_ENV/bin/python" -m pip install "ultralytics[export]>=8.3,<9" ncnn

"$VISION_ENV/bin/python" - <<'PY'
import platform
import cv2
import ncnn
import torch
import torchvision
import ultralytics
print("Architecture:", platform.machine())
print("Ultralytics:", ultralytics.__version__)
print("PyTorch:", torch.__version__)
print("Torchvision:", torchvision.__version__)
print("OpenCV:", cv2.__version__)
print("NCNN/YOLO imports: OK")
PY

printf 'Downloading %s and exporting NCNN at %spx...\n' "$MODEL_NAME" "$IMAGE_SIZE"
(
    cd "$VISION_ROOT"
    MODEL_NAME="$MODEL_NAME" IMAGE_SIZE="$IMAGE_SIZE" "$VISION_ENV/bin/python" - <<'PY'
import os
from pathlib import Path
from ultralytics import YOLO

weights = os.environ["MODEL_NAME"]
image_size = int(os.environ["IMAGE_SIZE"])
model = YOLO(weights)
exported = Path(model.export(format="ncnn", imgsz=image_size, batch=1, device="cpu"))
if not exported.is_dir():
    raise RuntimeError(f"NCNN export directory was not created: {exported}")

# Prove that the exported runtime can execute the exact class filter used by
# the dashboard before changing systemd configuration.
ncnn_model = YOLO(str(exported))
result = ncnn_model(
    "https://ultralytics.com/images/bus.jpg",
    classes=[0], conf=0.20, imgsz=image_size, max_det=10, verbose=False,
)[0]
classes = [] if result.boxes is None else [int(v) for v in result.boxes.cls.tolist()]
if 0 not in classes:
    raise RuntimeError("YOLO11n NCNN loaded but failed the installer person-detection self-test")
print("YOLO11n NCNN person-detection self-test: OK")
print("Exported model:", exported.resolve())
PY
)
[ -d "$MODEL_DIR" ] || fail "expected NCNN model was not found at $MODEL_DIR."

# Record the exact deployment artifact. This is an optimized export of the
# official pretrained weights, not a newly trained custom model.
{
    printf 'model_source=%s\n' "$MODEL_NAME"
    printf 'deployment_format=NCNN\n'
    printf 'image_size=%s\n' "$IMAGE_SIZE"
    printf 'model_dir=%s\n' "$MODEL_DIR"
    printf 'created_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if command -v sha256sum >/dev/null 2>&1; then
        [ -f "$VISION_ROOT/$MODEL_NAME" ] && sha256sum "$VISION_ROOT/$MODEL_NAME"
        find "$MODEL_DIR" -maxdepth 1 -type f -print0 | sort -z | xargs -0 -r sha256sum
    fi
} > "$MANIFEST"

# Verify our actual VisionManager against the exported artifact.
PYTHONPATH="$APP_DIR" VISION_MODEL="$MODEL_DIR" "$VISION_ENV/bin/python" - <<'PY'
from robot_server.vision import VisionManager
manager = VisionManager({})
manager._load_model()
print("3TSAHUR VisionManager model load: OK")
PY

backup="$(mktemp)"
sudo cat "$CONFIG_FILE" > "$backup"
restore_config() {
    sudo install -o root -g root -m 0600 "$backup" "$CONFIG_FILE"
    sudo systemctl restart stem-robot-dashboard.service 2>/dev/null || true
    rm -f -- "$backup"
}

# Conservative Pi 4 defaults: at most one source, two native compute threads,
# 320px inference, and about two scheduled inference cycles per second. The
# server's control-priority guard pauses optional inference during active drive.
if ! set_config_key VISION_VENV "$VISION_ENV" || \
   ! set_config_key VISION_MODEL "$MODEL_DIR" || \
   ! set_config_key VISION_CPU_THREADS "2" || \
   ! set_config_key VISION_IMAGE_SIZE "$IMAGE_SIZE" || \
   ! set_config_key VISION_PERSON_CONFIDENCE "0.20" || \
   ! set_config_key VISION_PERSON_INTERVAL_SECONDS "0.50" || \
   ! set_config_key VISION_INTERVAL_SECONDS "0.50"; then
    restore_config
    fail "dashboard vision configuration could not be updated."
fi

if ! sudo systemctl restart stem-robot-dashboard.service; then
    restore_config
    fail "dashboard could not restart with the optional vision runtime."
fi
healthy=0
for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1; then
        healthy=1
        break
    fi
    sleep 1
done
if [ "$healthy" != "1" ]; then
    sudo journalctl -u stem-robot-dashboard.service -n 60 --no-pager || true
    restore_config
    fail "dashboard health check failed; previous configuration restored."
fi
rm -f -- "$backup"

printf '\nYOLO11n deployment passed.\n'
printf 'Model: %s\n' "$MODEL_DIR"
printf 'Manifest: %s\n' "$MANIFEST"
printf 'Reload the dashboard and press C to toggle person detection ON/OFF.\n'
