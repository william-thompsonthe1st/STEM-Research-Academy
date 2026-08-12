#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="/etc/stem-research-academy/config.env"
KIOSK_LOG="$HOME/.local/state/stem-robot-kiosk.log"
KIOSK_PROFILE="$HOME/.config/stem-robot-kiosk/chromium"
KIOSK_URL="http://127.0.0.1:8080"

if [ -r "$CONFIG_FILE" ]; then
    # This root-owned file is also used by the dashboard service.
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

mkdir -p "$(dirname "$KIOSK_LOG")" "$KIOSK_PROFILE"

# Raspberry Pi OS releases have used both executable names.
if command -v chromium >/dev/null 2>&1; then
    BROWSER="$(command -v chromium)"
elif command -v chromium-browser >/dev/null 2>&1; then
    BROWSER="$(command -v chromium-browser)"
else
    printf '%s Chromium is not installed. Rerun installer/install.sh.\n' "$(date -Is)" >> "$KIOSK_LOG"
    exit 1
fi

# XDG autostart and labwc autostart can both run on some Pi OS releases.
# Only one launcher may own the kiosk browser.
exec 9>"/tmp/stem-robot-kiosk-${UID}.lock"
flock -n 9 || exit 0

printf '\n===== Kiosk startup: %s =====\n' "$(date)" >> "$KIOSK_LOG"

until curl --fail --silent --max-time 2 "$KIOSK_URL/healthz" >/dev/null; do
    sleep 1
done

# Use a normal resizable app window so Terminal and other Pi tools remain
# accessible. If the window is closed, relaunch it; minimizing is unaffected.
while true; do
    "$BROWSER" \
        --app="$KIOSK_URL" \
        --window-size=1200,760 \
        --no-first-run \
        --no-default-browser-check \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-component-update \
        --disable-background-networking \
        --disable-sync \
        --disable-translate \
        --disable-features=MediaRouter \
        --disk-cache-size=1 \
        --media-cache-size=1 \
        --disable-pinch \
        --overscroll-history-navigation=0 \
        --password-store=basic \
        --user-data-dir="$KIOSK_PROFILE" >> "$KIOSK_LOG" 2>&1 || true
    sleep 2
done
