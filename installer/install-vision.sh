#!/usr/bin/env bash
# Optional YOLO11n -> NCNN deployment for the merge branch.
# This branch still uses the base dashboard interpreter, so the isolated ML
# environment is exposed lazily through VISION_SITE_PACKAGES only when Vision is enabled.
set -Eeuo pipefail

APP_DIR="${STEM_APP_DIR:-$HOME/STEMResearchAcademy}"
VISION_ROOT="${STEM_VISION_DIR:-$HOME/.local/share/stem-research-academy/vision}"
VISION_ENV="$VISION_ROOT/.vision-venv"
MODEL_NAME="yolo11n.pt"
MODEL_DIR="$VISION_ROOT/yolo11n_ncnn_model"
IMAGE_SIZE="${VISION_IMAGE_SIZE:-320}"
CONFIG_FILE="/etc/stem-research-academy/config.env"
DASHBOARD_PYTHON="$APP_DIR/.venv/bin/python"
MANIFEST="$VISION_ROOT/deployment-manifest.txt"

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
[ -x "$DASHBOARD_PYTHON" ] || fail "base dashboard Python is missing."
command -v sudo >/dev/null 2>&1 || fail "sudo is required."
sudo test -f "$CONFIG_FILE" || fail "$CONFIG_FILE is missing. Run the base installer first."
[ "$(getconf LONG_BIT)" = "64" ] || fail "YOLO11n requires 64-bit Raspberry Pi OS."

available_kb="$(df -Pk "$HOME" | awk 'END {print $4}')"
[ -n "$available_kb" ] && [ "$available_kb" -ge 3145728 ] || fail "at least 3 GB of free storage is required."

mkdir -p "$VISION_ROOT"
python3 -m venv --clear --system-site-packages "$VISION_ENV"
PIP_NO_CACHE_DIR=1 "$VISION_ENV/bin/python" -m pip install --upgrade pip setuptools wheel
PIP_NO_CACHE_DIR=1 "$VISION_ENV/bin/python" -m pip install "ultralytics[export]>=8.3,<9" ncnn

(
    cd "$VISION_ROOT"
    IMAGE_SIZE="$IMAGE_SIZE" "$VISION_ENV/bin/python" - <<'PY'
import os
from pathlib import Path
from ultralytics import YOLO
size = int(os.environ["IMAGE_SIZE"])
model = YOLO("yolo11n.pt")
exported = Path(model.export(format="ncnn", imgsz=size, batch=1, device="cpu"))
if not exported.is_dir():
    raise RuntimeError("NCNN export failed")
result = YOLO(str(exported))("https://ultralytics.com/images/bus.jpg", classes=[0], conf=0.20, imgsz=size, max_det=10, verbose=False)[0]
classes = [] if result.boxes is None else [int(v) for v in result.boxes.cls.tolist()]
if 0 not in classes:
    raise RuntimeError("person-detection self-test failed")
print("YOLO11n NCNN self-test: OK")
PY
)
[ -d "$MODEL_DIR" ] || fail "expected model directory missing: $MODEL_DIR"
VISION_SITE_PACKAGES="$("$VISION_ENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"

PYTHONPATH="$APP_DIR" VISION_SITE_PACKAGES="$VISION_SITE_PACKAGES" VISION_MODEL="$MODEL_DIR" "$DASHBOARD_PYTHON" - <<'PY'
from robot_server.vision import VisionManager
VisionManager({})._load_model()
print("Base dashboard can load isolated YOLO runtime: OK")
PY

{
    printf 'model_source=%s\n' "$MODEL_NAME"
    printf 'deployment_format=NCNN\nimage_size=%s\nmodel_dir=%s\n' "$IMAGE_SIZE" "$MODEL_DIR"
    printf 'created_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$MANIFEST"

set_config_key VISION_SITE_PACKAGES "$VISION_SITE_PACKAGES"
set_config_key VISION_MODEL "$MODEL_DIR"
set_config_key VISION_IMAGE_SIZE "$IMAGE_SIZE"
set_config_key VISION_PERSON_CONFIDENCE "0.20"
set_config_key VISION_PERSON_INTERVAL_SECONDS "0.50"
sudo systemctl restart stem-robot-dashboard.service
curl -fsS http://127.0.0.1:8080/healthz >/dev/null || fail "dashboard health check failed after vision install"

echo "YOLO11n deployment passed. Reload the dashboard and press C to toggle Vision."
