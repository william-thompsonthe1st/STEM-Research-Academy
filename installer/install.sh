#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${STEM_REPO_URL:-https://github.com/william-thompsonthe1st/STEM-Research-Academy.git}"
REPO_BRANCH="${STEM_REPO_BRANCH:-main}"
SOURCE_SUBDIR="${STEM_SOURCE_SUBDIR:-.}"
APP_DIR="${STEM_APP_DIR:-$HOME/STEMResearchAcademy}"
VENV_DIR="$APP_DIR/.venv"
CONFIG_DIR="/etc/stem-research-academy"
CONFIG_FILE="$CONFIG_DIR/config.env"
APP_USER="$(id -un)"
TEMP_CHECKOUT=""
STAGED_APP_DIR=""
APP_SWAPPED=0
CONFIG_ROLLBACK=""
CONFIG_WAS_PRESENT=0
HOSTS_ROLLBACK=""
ORIGINAL_HOSTNAME="$(hostnamectl --static 2>/dev/null || hostname)"
AUTOSTART_DIR="$HOME/.config/autostart"
LABWC_DIR="$HOME/.config/labwc"
KIOSK_URL="http://127.0.0.1:8080"
APP_PARENT="$(dirname "$APP_DIR")"
APP_NAME="$(basename "$APP_DIR")"
PREVIOUS_APP_DIR="${APP_DIR}.previous"
MIN_FREE_KB=131072

say() { printf '\n\033[1;36m[STEM Robot Lab]\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31m[INSTALL ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

cleanup() {
    local status=$?
    if [ "$status" -ne 0 ] && [ "$APP_SWAPPED" = "1" ] && [ -d "$PREVIOUS_APP_DIR" ]; then
        say "Restoring the previous working application after the failed update..."
        sudo systemctl stop stem-robot-dashboard.service 2>/dev/null || true
        rm -rf -- "$APP_DIR"
        mv "$PREVIOUS_APP_DIR" "$APP_DIR"
        if [ "$CONFIG_WAS_PRESENT" = "1" ] && [ -n "$CONFIG_ROLLBACK" ]; then
            sudo install -o root -g root -m 0600 "$CONFIG_ROLLBACK" "$CONFIG_FILE"
        elif [ "$CONFIG_WAS_PRESENT" = "0" ]; then
            sudo rm -f -- "$CONFIG_FILE"
        fi
        if [ -n "$HOSTS_ROLLBACK" ] && [ -f "$HOSTS_ROLLBACK" ]; then
            sudo install -o root -g root -m 0644 "$HOSTS_ROLLBACK" /etc/hosts
        fi
        [ -n "$ORIGINAL_HOSTNAME" ] && sudo hostnamectl set-hostname "$ORIGINAL_HOSTNAME" || true
        sudo systemctl restart stem-robot-dashboard.service 2>/dev/null || true
    fi
    if [ -n "$TEMP_CHECKOUT" ] && [ -d "$TEMP_CHECKOUT" ]; then
        rm -rf -- "$TEMP_CHECKOUT"
    fi
    if [ -n "$STAGED_APP_DIR" ] && [ -d "$STAGED_APP_DIR" ]; then
        rm -rf -- "$STAGED_APP_DIR"
    fi
    [ -n "$CONFIG_ROLLBACK" ] && rm -f -- "$CONFIG_ROLLBACK"
}

trap cleanup EXIT
trap 'status=$?; fail "Installation stopped on line $LINENO (exit $status): $BASH_COMMAND. Fix the error above and rerun the same command."' ERR

apt_get() {
    local attempt=1 output
    output="$(mktemp)"
    while true; do
        if sudo env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=60 "$@" 2>&1 | tee "$output"; then
            rm -f "$output"
            return 0
        fi
        if ! grep -Eq 'Could not get lock|Unable to (acquire|lock)|is another process using it' "$output"; then
            rm -f "$output"
            return 1
        fi
        if [ "$attempt" -ge 20 ]; then
            rm -f "$output"
            fail "APT stayed busy. Wait for Raspberry Pi OS updates to finish, then rerun the installer."
        fi
        say "APT is busy; retrying in 15 seconds ($attempt/20)..."
        sleep 15
        attempt=$((attempt + 1))
        : > "$output"
    done
}

prune_old_installations() {
    local candidate resolved_parent resolved_candidate
    resolved_parent="$(realpath -m "$APP_PARENT")"
    if [ "$APP_NAME" = "." ] || [ "$APP_NAME" = "/" ] || [ "$resolved_parent" = "/" ]; then
        fail "Unsafe application path: $APP_DIR"
    fi
    while IFS= read -r -d '' candidate; do
        resolved_candidate="$(realpath -m "$candidate")"
        case "$resolved_candidate" in
            "$resolved_parent"/"$APP_NAME".backup.*|"$resolved_parent"/"$APP_NAME".installing.*)
                say "Removing stale installer backup: $resolved_candidate"
                rm -rf -- "$resolved_candidate"
                ;;
            *) fail "Refusing to remove unexpected backup path: $resolved_candidate" ;;
        esac
    done < <(
        find "$resolved_parent" -mindepth 1 -maxdepth 1 -type d \
            \( -name "$APP_NAME.backup.*" -o -name "$APP_NAME.installing.*" \) -print0
    )
}

check_free_space() {
    local available_kb
    available_kb="$(df -Pk "$APP_PARENT" | awk 'END {print $4}')"
    if [ -z "$available_kb" ] || [ "$available_kb" -lt "$MIN_FREE_KB" ]; then
        df -h "$APP_PARENT" || true
        fail "At least 128 MB of free space is required after cleanup. Remove unrelated files, then rerun the same command."
    fi
    say "Disk check passed: $((available_kb / 1024)) MB available."
}

if [ "$(id -u)" -eq 0 ]; then
    fail "Run this as the normal Raspberry Pi user, without sudo."
fi
command -v sudo >/dev/null 2>&1 || fail "sudo is required."

say "Cleaning space left by earlier installer runs..."
prune_old_installations
sudo apt-get clean
check_free_space

say "Installing current Raspberry Pi OS packages..."
apt_get update
if [ "${STEM_SKIP_OS_UPGRADE:-0}" != "1" ]; then
    # Keep the complete Pi OS image current, including kernel, firmware,
    # Chromium, NetworkManager, and desktop compatibility packages.
    apt_get full-upgrade -y
fi
apt_get install -y \
    avahi-daemon \
    ca-certificates \
    curl \
    git \
    libnss-mdns \
    network-manager \
    nginx-light \
    python3 \
    python3-flask \
    python3-opencv \
    python3-pip \
    python3-venv \
    util-linux \
    v4l-utils

# Package and command names differ between Raspberry Pi OS generations.
if apt-cache show chromium >/dev/null 2>&1; then
    apt_get install -y chromium
elif apt-cache show chromium-browser >/dev/null 2>&1; then
    apt_get install -y chromium-browser
else
    fail "A Chromium package was not found for this Raspberry Pi OS image."
fi

# A Pi flashed with Raspberry Pi OS Lite needs a desktop for the local kiosk.
if ! command -v labwc >/dev/null 2>&1 && \
   ! command -v startlxde-pi >/dev/null 2>&1; then
    say "No graphical desktop was found; installing the Raspberry Pi desktop..."
    if apt-cache show rpd-wayland-core >/dev/null 2>&1; then
        apt_get install -y rpd-wayland-core rpd-theme rpd-preferences lightdm
    elif apt-cache show raspberrypi-ui-mods >/dev/null 2>&1; then
        apt_get install -y raspberrypi-ui-mods lightdm
    else
        fail "Raspberry Pi desktop packages were not found. Use a current Raspberry Pi OS image."
    fi
fi

if apt-cache show python3-rpi-lgpio >/dev/null 2>&1; then
    apt_get install -y python3-rpi-lgpio
else
    apt_get install -y python3-rpi.gpio
fi

# Package downloads are no longer needed after installation. Reclaim them
# before creating the temporary project checkout and Python environment.
sudo apt-get clean
check_free_space

say "Downloading a clean copy of the latest project..."
TEMP_CHECKOUT="$(mktemp -d)"
DOWNLOAD_ROOT=""

# Download only this project directory. This avoids both Git index-pack errors
# and the space cost of unrelated large files elsewhere in the monorepo.
REPO_PATH="${REPO_URL#https://github.com/}"
if [ "$REPO_PATH" != "$REPO_URL" ]; then
    REPO_PATH="${REPO_PATH%.git}"
    API_ROOT="$TEMP_CHECKOUT/api-repository"
    say "Downloading only $SOURCE_SUBDIR from GitHub..."
    if python3 - "$REPO_PATH" "$REPO_BRANCH" "$SOURCE_SUBDIR" "$API_ROOT" <<'PY'
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

repo, branch, source_subdir, destination = sys.argv[1:]
headers = {"User-Agent": "STEM-Research-Academy-Installer"}

def download(url, attempts=5):
    last_error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                return response.read()
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2)
    raise last_error

ref = urllib.parse.quote(branch, safe="")
tree_url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
tree = json.loads(download(tree_url))
if tree.get("truncated"):
    raise RuntimeError("GitHub returned a truncated repository tree")

source_subdir = source_subdir.strip("/")
prefix = f"{source_subdir}/" if source_subdir else ""
files = [entry["path"] for entry in tree.get("tree", []) if entry.get("type") == "blob" and entry["path"].startswith(prefix)]
if not files:
    raise RuntimeError(f"{source_subdir} was not found in {repo}@{branch}")

root = pathlib.Path(destination).resolve()
for path in files:
    target = (root / path).resolve()
    if root not in target.parents:
        raise RuntimeError(f"Unsafe repository path: {path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    raw_path = urllib.parse.quote(path, safe="/")
    raw_branch = urllib.parse.quote(branch, safe="")
    target.write_bytes(download(f"https://raw.githubusercontent.com/{repo}/{raw_branch}/{raw_path}"))
print(f"Downloaded {len(files)} project files.")
PY
    then
        DOWNLOAD_ROOT="$API_ROOT"
    else
        say "Directory download failed; trying a sparse low-memory Git clone..."
    fi
fi

if [ -z "$DOWNLOAD_ROOT" ]; then
    GIT_ROOT="$TEMP_CHECKOUT/git-repository"
    git -c http.version=HTTP/1.1 -c core.compression=0 clone \
        --depth 1 --filter=blob:none --no-checkout --branch "$REPO_BRANCH" --single-branch \
        "$REPO_URL" "$GIT_ROOT"
    if [ "$SOURCE_SUBDIR" != "." ] && [ -n "$SOURCE_SUBDIR" ]; then
        git -C "$GIT_ROOT" sparse-checkout init --cone
        git -C "$GIT_ROOT" sparse-checkout set "$SOURCE_SUBDIR"
    fi
    git -C "$GIT_ROOT" checkout "$REPO_BRANCH"
    DOWNLOAD_ROOT="$GIT_ROOT"
fi

FRESH_SOURCE="$DOWNLOAD_ROOT"
if [ "$SOURCE_SUBDIR" != "." ] && [ -n "$SOURCE_SUBDIR" ]; then
    FRESH_SOURCE="$DOWNLOAD_ROOT/$SOURCE_SUBDIR"
fi
[ -f "$FRESH_SOURCE/run.py" ] || fail "Robot project was not found in the downloaded repository."
python3 -m compileall -q "$FRESH_SOURCE/robot_server" "$FRESH_SOURCE/run.py"

say "Building and validating the replacement application..."
STAGED_APP_DIR="${APP_DIR}.installing.$$"
mkdir -p "$STAGED_APP_DIR"
cp -a "$FRESH_SOURCE/." "$STAGED_APP_DIR/"

# Flask, OpenCV, and GPIO are installed above from Raspberry Pi OS packages.
# Avoid ensurepip and a second network download here: those are unnecessary,
# consume scarce storage, and commonly make venv creation fail on small Pis.
python3 -m venv --without-pip --system-site-packages "$STAGED_APP_DIR/.venv"
"$STAGED_APP_DIR/.venv/bin/python" -m compileall -q \
    "$STAGED_APP_DIR/robot_server" "$STAGED_APP_DIR/run.py"
(
    cd "$STAGED_APP_DIR"
    "$STAGED_APP_DIR/.venv/bin/python" -c \
        'import flask; import cv2; print("Flask and OpenCV imports passed.")'
)

# Keep the current robot dashboard running until the replacement has passed
# compilation and dependency imports. A live health request runs after restart.
sudo systemctl stop stem-robot-dashboard.service 2>/dev/null || true
if [ -e "$PREVIOUS_APP_DIR" ]; then
    rm -rf -- "$PREVIOUS_APP_DIR"
fi
if [ -e "$APP_DIR" ]; then
    say "Replacing the previous installation..."
    mv "$APP_DIR" "$PREVIOUS_APP_DIR"
fi
mv "$STAGED_APP_DIR" "$APP_DIR"
STAGED_APP_DIR=""
APP_SWAPPED=1

say "Migrating persistent robot, hotspot, and kiosk configuration..."
sudo install -d -m 0755 "$CONFIG_DIR"
CONFIG_ROLLBACK="$(mktemp)"
if sudo test -f "$CONFIG_FILE"; then
    CONFIG_WAS_PRESENT=1
    sudo cat "$CONFIG_FILE" > "$CONFIG_ROLLBACK"
fi
if ! sudo test -f "$CONFIG_FILE"; then
    CONFIG_TEMP="$(mktemp)"
    cat > "$CONFIG_TEMP" <<'EOF'
# This file survives application upgrades. Edit it, then reboot or restart services.
HOTSPOT_SSID=3TSahur-Swarm
HOTSPOT_PASSWORD=roboswarm1
WIFI_INTERFACE=wlan0
HOTSPOT_ADDRESS=10.42.0.1/24
HOTSPOT_CHANNEL=6
PORT=8080
CAMERA_DEVICE=auto
CAMERA_WIDTH=640
CAMERA_HEIGHT=480
CAMERA_FPS=10
DRIVE_WATCHDOG_SECONDS=0.20
LARP_A_CAMERA_URL=
LARP_B_CAMERA_URL=
KIOSK_URL=http://127.0.0.1:8080
LARP_A_HOST=larp-a.local
LARP_B_HOST=larp-b.local
VISION_MODEL=yolo11n_ncnn_model
VISION_IMAGE_SIZE=320
VISION_CONFIDENCE=0.45
VISION_INTERVAL_SECONDS=0.5
EOF
    sudo install -m 0600 "$CONFIG_TEMP" "$CONFIG_FILE"
    rm -f "$CONFIG_TEMP"
fi

# Add keys introduced by later installer versions without discarding camera,
# ESP32, or custom hardware settings from an earlier installation.
ensure_config_key() {
    local key="$1" value="$2"
    if ! sudo grep -qE "^${key}=" "$CONFIG_FILE"; then
        printf '%s=%s\n' "$key" "$value" | sudo tee -a "$CONFIG_FILE" >/dev/null
    fi
}

# Translate partner-era setting names on first upgrade. Keep the old lines as
# a readable rollback record, but make their values active under LARP names.
migrate_config_key() {
    local new_key="$1" old_key="$2" fallback="$3" value
    if sudo grep -qE "^${new_key}=" "$CONFIG_FILE"; then
        return
    fi
    value="$(sudo sed -n -E "s/^${old_key}=(.*)$/\1/p" "$CONFIG_FILE" | tail -n 1)"
    printf '%s=%s\n' "$new_key" "${value:-$fallback}" | sudo tee -a "$CONFIG_FILE" >/dev/null
}

ensure_config_key KIOSK_URL "$KIOSK_URL"
ensure_config_key HOTSPOT_SSID "3TSahur-Swarm"
ensure_config_key HOTSPOT_PASSWORD "roboswarm1"
ensure_config_key WIFI_INTERFACE "wlan0"
ensure_config_key HOTSPOT_ADDRESS "10.42.0.1/24"
ensure_config_key HOTSPOT_CHANNEL "6"
ensure_config_key PORT "8080"
ensure_config_key CAMERA_DEVICE "auto"
ensure_config_key CAMERA_WIDTH "640"
ensure_config_key CAMERA_HEIGHT "480"
ensure_config_key CAMERA_FPS "10"
ensure_config_key DRIVE_WATCHDOG_SECONDS "0.20"
migrate_config_key LARP_A_CAMERA_URL ESP32_ONE_STREAM_URL ""
migrate_config_key LARP_B_CAMERA_URL ESP32_TWO_STREAM_URL ""
migrate_config_key LARP_A_HOST SCOUT_A_HOST "larp-a.local"
migrate_config_key LARP_B_HOST SCOUT_B_HOST "larp-b.local"
ensure_config_key VISION_MODEL "yolo11n_ncnn_model"
ensure_config_key VISION_IMAGE_SIZE "320"
ensure_config_key VISION_CONFIDENCE "0.45"
ensure_config_key VISION_INTERVAL_SECONDS "0.5"

# Hotspot credentials are installer-managed so firmware and Pi stay in sync.
sudo sed -i -E \
    -e 's/^HOTSPOT_SSID=.*/HOTSPOT_SSID=3TSahur-Swarm/' \
    -e 's/^HOTSPOT_PASSWORD=.*/HOTSPOT_PASSWORD=roboswarm1/' \
    -e 's|^CAMERA_DEVICE=.*|CAMERA_DEVICE=auto|' \
    -e 's/^CAMERA_WIDTH=.*/CAMERA_WIDTH=640/' \
    -e 's/^CAMERA_HEIGHT=.*/CAMERA_HEIGHT=480/' \
    -e 's/^CAMERA_FPS=.*/CAMERA_FPS=10/' \
    -e 's/^DRIVE_WATCHDOG_SECONDS=.*/DRIVE_WATCHDOG_SECONDS=0.20/' \
    "$CONFIG_FILE"
sudo chmod 0600 "$CONFIG_FILE"

# Keep sudo/local name resolution working after the intentional hostname
# change. Preserve unrelated aliases and replace only the 127.0.1.1 mapping.
HOSTS_TEMP="$(mktemp)"
HOSTS_ROLLBACK="/etc/hosts.before-3tsahur-$(date +%Y%m%d-%H%M%S)"
python3 - /etc/hosts "$HOSTS_TEMP" <<'PY'
from pathlib import Path
import sys

source, destination = map(Path, sys.argv[1:])
lines = source.read_text(encoding="utf-8").splitlines() if source.exists() else []
result = []
replaced = False
for line in lines:
    fields = line.split()
    if fields and fields[0] == "127.0.1.1":
        if not replaced:
            result.append("127.0.1.1\t3tsahur")
            replaced = True
        continue
    result.append(line)
if not any(line.split()[:1] == ["127.0.0.1"] for line in result):
    result.insert(0, "127.0.0.1\tlocalhost")
if not replaced:
    result.append("127.0.1.1\t3tsahur")
destination.write_text("\n".join(result) + "\n", encoding="utf-8")
PY
sudo cp -a -- /etc/hosts "$HOSTS_ROLLBACK"
sudo install -o root -g root -m 0644 "$HOSTS_TEMP" /etc/hosts
rm -f "$HOSTS_TEMP"
sudo hostnamectl set-hostname 3tsahur

say "Installing the hotspot and dashboard services..."
sudo install -m 0755 "$APP_DIR/installer/hotspot.sh" /usr/local/sbin/stem-robot-hotspot

SERVICE_TEMP="$(mktemp)"
sed -e "s|@APP_USER@|$APP_USER|g" -e "s|@APP_DIR@|$APP_DIR|g" \
    "$APP_DIR/installer/systemd/stem-robot-dashboard.service" > "$SERVICE_TEMP"
sudo install -m 0644 "$SERVICE_TEMP" /etc/systemd/system/stem-robot-dashboard.service
rm -f "$SERVICE_TEMP"
sudo install -m 0644 \
    "$APP_DIR/installer/systemd/stem-robot-hotspot.service" \
    /etc/systemd/system/stem-robot-hotspot.service

getent group gpio >/dev/null && sudo usermod -aG gpio "$APP_USER" || true
getent group video >/dev/null && sudo usermod -aG video "$APP_USER" || true
sudo systemctl enable NetworkManager.service
sudo systemctl enable avahi-daemon.service
sudo systemctl set-default graphical.target
sudo systemctl enable lightdm.service 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable stem-robot-hotspot.service stem-robot-dashboard.service

say "Configuring the attached screen as a resizable robot dashboard window..."
chmod +x "$APP_DIR/installer/kiosk.sh"
mkdir -p "$AUTOSTART_DIR" "$LABWC_DIR"

cat > "$AUTOSTART_DIR/stem-robot-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=3TSahur Robot Dashboard
Comment=Resizable 3TSahur and LARP robot controls
Exec=$APP_DIR/installer/kiosk.sh
Path=$APP_DIR
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

# Current Pi OS uses labwc; older releases use the XDG desktop entry above.
touch "$LABWC_DIR/autostart"
sed -i '/# STEM ROBOT KIOSK START/,/# STEM ROBOT KIOSK END/d' "$LABWC_DIR/autostart"
cat >> "$LABWC_DIR/autostart" <<EOF
# STEM ROBOT KIOSK START
$APP_DIR/installer/kiosk.sh &
# STEM ROBOT KIOSK END
EOF

if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_boot_behaviour B4 || true
    sudo raspi-config nonint do_blanking 1 || true
fi

# Keep the dashboard visible across old X11 and current Wayland Pi desktops.
sudo install -d -m 0755 /etc/systemd/logind.conf.d
sudo tee /etc/systemd/logind.conf.d/90-stem-robot.conf >/dev/null <<'EOF'
[Login]
IdleAction=ignore
EOF

if [ -d /etc/lightdm ] || command -v lightdm >/dev/null 2>&1; then
    sudo install -d -m 0755 /etc/lightdm/lightdm.conf.d
    sudo tee /etc/lightdm/lightdm.conf.d/90-stem-robot.conf >/dev/null <<'EOF'
[Seat:*]
xserver-command=X -s 0 -dpms
EOF
fi

sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target 2>/dev/null || true

say "Adding simple dashboard addresses for hotspot devices..."
NGINX_TEMP="$(mktemp)"
cat > "$NGINX_TEMP" <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_read_timeout 1h;
    }
}
EOF
sudo install -m 0644 "$NGINX_TEMP" /etc/nginx/sites-available/3tsahur-dashboard
rm -f "$NGINX_TEMP"
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sfn /etc/nginx/sites-available/3tsahur-dashboard /etc/nginx/sites-enabled/3tsahur-dashboard
sudo nginx -t
sudo systemctl enable nginx.service
sudo systemctl restart nginx.service

CMDLINE_FILE="/boot/firmware/cmdline.txt"
[ -f "$CMDLINE_FILE" ] || CMDLINE_FILE="/boot/cmdline.txt"
if [ -f "$CMDLINE_FILE" ]; then
    if grep -qE '(^| )consoleblank=[^ ]+' "$CMDLINE_FILE"; then
        sudo sed -i -E 's/(^| )consoleblank=[^ ]+/ consoleblank=0/g; s/^ //' "$CMDLINE_FILE"
    else
        sudo sed -i 's/$/ consoleblank=0/' "$CMDLINE_FILE"
    fi
fi

say "Validating the server before enabling it..."
"$VENV_DIR/bin/python" -m compileall -q "$APP_DIR/robot_server" "$APP_DIR/run.py"
"$VENV_DIR/bin/python" -c 'import flask; import cv2; print("Flask and OpenCV imports passed.")'
sudo systemctl restart stem-robot-dashboard.service
DASHBOARD_READY=0
for attempt in $(seq 1 30); do
    if curl --fail --silent --max-time 2 http://127.0.0.1:8080/healthz >/dev/null; then
        DASHBOARD_READY=1
        break
    fi
    sleep 1
done
if [ "$DASHBOARD_READY" != "1" ]; then
    sudo journalctl -u stem-robot-dashboard.service -n 40 --no-pager || true
    fail "The dashboard did not pass its local health check. The service log is shown above."
fi

if [ -n "${PREVIOUS_APP_DIR:-}" ] && [ -d "$PREVIOUS_APP_DIR" ]; then
    rm -rf -- "$PREVIOUS_APP_DIR"
fi
APP_SWAPPED=0

say "Installation complete."
echo "Pi name: 3tsahur"
echo "Hotspot name: 3TSahur-Swarm"
echo "Hotspot password: roboswarm1"
echo "Dashboard: http://10.42.0.1"
echo "Dashboard name: http://3tsahur.local"
echo "Direct fallback: http://10.42.0.1:8080"
echo "The hotspot starts at boot and can accept both ESP32 robots."
echo "The attached Pi screen opens the dashboard in a resizable application window."
echo "The Pi will reboot automatically in 10 seconds."

# A transient systemd timer survives this piped installer process exiting.
# This is more reliable than sleeping inside `curl | bash` and then rebooting.
sync
if command -v systemd-run >/dev/null 2>&1; then
    REBOOT_UNIT="stem-robot-installer-reboot-$(date +%s)"
    sudo systemd-run \
        --unit="$REBOOT_UNIT" \
        --on-active=10s \
        --timer-property=AccuracySec=1s \
        "$(command -v systemctl)" reboot
else
    sudo shutdown -r +1 "STEM robot installation complete"
fi
