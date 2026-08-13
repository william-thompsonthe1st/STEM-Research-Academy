#!/usr/bin/env bash
# Optional pretrained Ultralytics YOLO11n + NCNN setup for an installed Pi hub.
set -Eeuo pipefail

APP_DIR="${STEM_APP_DIR:-$HOME/STEMResearchAcademy}"
VISION_ROOT="${STEM_VISION_DIR:-$HOME/.local/share/stem-research-academy/vision}"
VISION_ENV="$VISION_ROOT/.vision-venv"
MODEL_NAME="yolo11n.pt"
MODEL_DIR="$VISION_ROOT/yolo11n_ncnn_model"
IMAGE_SIZE="${VISION_IMAGE_SIZE:-320}"
CONFIG_FILE="/etc/stem-research-academy/config.env"

fail() { printf 'Vision installation failed: %s\n' "$*" >&2; exit 1; }

set_config_key() {
    local key="$1" value="$2" temporary
    temporary="$(mktemp)"
    sudo awk -v key="$key" -v value="$value" '
        BEGIN { replaced = 0 }
        index($0, key "=") == 1 { if (!replaced) print key "=" value; replaced = 1; next }
        { print }
        END { if (!replaced) print key "=" value }
    ' "$CONFIG_FILE" > "$temporary" || { rm -f -- "$temporary"; return 1; }
    sudo install -o root -g root -m 0600 "$temporary" "$CONFIG_FILE" || { rm -f -- "$temporary"; return 1; }
    rm -f -- "$temporary"
}

[ "$(id -u)" -ne 0 ] || fail "run this as the normal Raspberry Pi user, without sudo."
[ -f "$APP_DIR/run.py" ] || fail "3TSAHUR application not found at $APP_DIR. Run the base installer first."
[ -f "$APP_DIR/installer/start-dashboard.sh" ] || fail "dashboard launcher is missing. Pull the latest main branch and rerun the base installer."
command -v sudo >/dev/null 2>&1 || fail "sudo is required."
sudo test -f "$CONFIG_FILE" || fail "$CONFIG_FILE is missing. Run the base installer first."
[ "$(getconf LONG_BIT)" = "64" ] || fail "YOLO11n on this project requires 64-bit Raspberry Pi OS."
command -v python3 >/dev/null 2>&1 || fail "python3 is not installed."

available_kb="$(df -Pk "$HOME" | awk 'END {print $4}')"
[ -n "$available_kb" ] && [ "$available_kb" -ge 3145728 ] || fail "at least 3 GB of free storage is required."

echo "Creating persistent YOLO11n environment..."
mkdir -p "$VISION_ROOT"
python3 -m venv --clear --system-site-packages "$VISION_ENV"
PIP_NO_CACHE_DIR=1 "$VISION_ENV/bin/python" -m pip install --upgrade pip setuptools wheel
PIP_NO_CACHE_DIR=1 "$VISION_ENV/bin/python" -m pip install "ultralytics[export]>=8.3,<9" ncnn

"$VISION_ENV/bin/python" - <<'PY'
import platform
import ncnn, torch, torchvision, ultralytics
from ultralytics import YOLO
print("Architecture:", platform.machine())
print("Ultralytics:", ultralytics.__version__)
print("PyTorch:", torch.__version__)
print("Torchvision:", torchvision.__version__)
print("NCNN/YOLO imports: OK")
PY

echo "Downloading yolo11n.pt and exporting NCNN at ${IMAGE_SIZE}px..."
(
    cd "$VISION_ROOT"
    MODEL_NAME="$MODEL_NAME" IMAGE_SIZE="$IMAGE_SIZE" "$VISION_ENV/bin/python" - <<'PY'
import os
from pathlib import Path
from ultralytics import YOLO
model = YOLO(os.environ["MODEL_NAME"])
exported = Path(model.export(format="ncnn", imgsz=int(os.environ["IMAGE_SIZE"]), batch=1, device="cpu"))
if not exported.is_dir():
    raise RuntimeError(f"NCNN export directory was not created: {exported}")
print("NCNN model:", exported.resolve())
PY
)
[ -d "$MODEL_DIR" ] || fail "expected NCNN model was not found at $MODEL_DIR."

# Verify the exact runtime that systemd will use before touching the service.
PYTHONPATH="$APP_DIR" VISION_MODEL="$MODEL_DIR" "$VISION_ENV/bin/python" - <<'PY'
from robot_server.vision import VisionManager
manager = VisionManager({})
model = manager._load_model()
print("Dashboard VisionManager YOLO11n load: OK", model)
PY

backup="$(mktemp)"
sudo cat "$CONFIG_FILE" > "$backup"
restore_config() {
    sudo install -o root -g root -m 0600 "$backup" "$CONFIG_FILE"
    sudo systemctl restart stem-robot-dashboard.service 2>/dev/null || true
    rm -f -- "$backup"
}

if ! set_config_key VISION_VENV "$VISION_ENV" || \
   ! set_config_key VISION_MODEL "$MODEL_DIR" || \
   ! set_config_key VISION_CPU_THREADS "2" || \
   ! set_config_key VISION_IMAGE_SIZE "$IMAGE_SIZE" || \
   ! set_config_key VISION_PERSON_CONFIDENCE "0.20" || \
   ! set_config_key VISION_PERSON_INTERVAL_SECONDS "0.35"; then
    restore_config
    fail "dashboard vision configuration could not be updated."
fi

if ! sudo systemctl restart stem-robot-dashboard.service; then
    restore_config
    fail "dashboard could not restart with the optional vision runtime."
fi
healthy=0
for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1; then healthy=1; break; fi
    sleep 1
done
if [ "$healthy" != "1" ]; then
    sudo journalctl -u stem-robot-dashboard.service -n 50 --no-pager || true
    restore_config
    fail "dashboard health check failed; previous configuration restored."
fi
rm -f -- "$backup"

echo "YOLO11n installation passed. Reload the dashboard and press C to toggle person detection on/off."
