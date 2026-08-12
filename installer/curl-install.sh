#!/usr/bin/env bash
# One-command bootstrap for a trusted Raspberry Pi OS installation.
# It downloads the versioned installer, which then performs the validated,
# atomic application installation. Do not run this as root.
set -Eeuo pipefail

REPO_URL="${STEM_REPO_URL:-https://github.com/william-thompsonthe1st/STEM-Research-Academy.git}"
REPO_BRANCH="${STEM_REPO_BRANCH:-main}"
RAW_REPO="${REPO_URL#https://github.com/}"
RAW_REPO="${RAW_REPO%.git}"
INSTALLER_URL="https://raw.githubusercontent.com/${RAW_REPO}/${REPO_BRANCH}/installer/install.sh"
TEMP_INSTALLER="$(mktemp)"

cleanup() { rm -f -- "$TEMP_INSTALLER"; }
trap cleanup EXIT

if [ "$(id -u)" -eq 0 ]; then
    echo "Run this as the normal Raspberry Pi user, without sudo." >&2
    exit 1
fi
command -v curl >/dev/null 2>&1 || {
    echo "curl is required. Install curl, then rerun this command." >&2
    exit 1
}

echo "Downloading 3TSahur/LARP installer from ${REPO_BRANCH}..."
curl --fail --location --retry 3 --retry-delay 2 --silent --show-error \
    "$INSTALLER_URL" -o "$TEMP_INSTALLER"
STEM_REPO_URL="$REPO_URL" STEM_REPO_BRANCH="$REPO_BRANCH" \
    bash "$TEMP_INSTALLER"
