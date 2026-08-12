#!/usr/bin/env bash
set -Eeuo pipefail

CONFIG_FILE="/etc/stem-research-academy/config.env"
CONNECTION_NAME="stem-robot-hotspot"

if [ ! -r "$CONFIG_FILE" ]; then
    echo "Missing $CONFIG_FILE" >&2
    exit 1
fi

# This file is root-owned and mode 0600. It contains the hotspot password.
# shellcheck disable=SC1090
source "$CONFIG_FILE"

if [ "${1:-start}" = "stop" ]; then
    nmcli connection down "$CONNECTION_NAME" 2>/dev/null || true
    exit 0
fi

: "${HOTSPOT_SSID:?HOTSPOT_SSID is required}"
: "${HOTSPOT_PASSWORD:?HOTSPOT_PASSWORD is required}"
: "${WIFI_INTERFACE:=wlan0}"
: "${HOTSPOT_ADDRESS:=10.42.0.1/24}"
: "${HOTSPOT_CHANNEL:=6}"

if [ "${#HOTSPOT_PASSWORD}" -lt 8 ]; then
    echo "HOTSPOT_PASSWORD must contain at least 8 characters" >&2
    exit 1
fi

systemctl is-active --quiet NetworkManager || systemctl start NetworkManager
nmcli radio wifi on

if ! nmcli --terse --fields NAME connection show | grep -Fxq "$CONNECTION_NAME"; then
    nmcli connection add \
        type wifi \
        ifname "$WIFI_INTERFACE" \
        con-name "$CONNECTION_NAME" \
        ssid "$HOTSPOT_SSID"
fi

nmcli connection modify "$CONNECTION_NAME" \
    connection.autoconnect yes \
    connection.autoconnect-priority 100 \
    connection.interface-name "$WIFI_INTERFACE" \
    802-11-wireless.ssid "$HOTSPOT_SSID" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    802-11-wireless.channel "$HOTSPOT_CHANNEL" \
    802-11-wireless.powersave 2 \
    802-11-wireless-security.key-mgmt wpa-psk \
    802-11-wireless-security.psk "$HOTSPOT_PASSWORD" \
    ipv4.method shared \
    ipv4.addresses "$HOTSPOT_ADDRESS" \
    ipv6.method disabled

nmcli connection up "$CONNECTION_NAME"
