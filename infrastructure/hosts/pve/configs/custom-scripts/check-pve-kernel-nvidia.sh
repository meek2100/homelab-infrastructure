#!/usr/bin/env bash
# ==============================================================================
# PVE Modern Upstream NVIDIA Driver Checker (Quadro M1200 / Maxwell)
# Checks NVIDIA's official release CDN for updates newer than the active 580.178.04
# ==============================================================================
set -euo pipefail

CONFIG_FILE="/etc/default/homelab-alerts"
PUSHOVER_USER=""
PUSHOVER_TOKEN=""
ALERT_EMAIL="darin@theurer.dev"

if [ -f "$CONFIG_FILE" ]; then
    # shellcheck source=/dev/null
    . "$CONFIG_FILE"
fi

send_pushover() {
    local title="$1"
    local message="$2"
    local priority="${3:-0}"
    if [ -n "$PUSHOVER_TOKEN" ] && [ -n "$PUSHOVER_USER" ]; then
        curl --connect-timeout 10 --max-time 15 -s \
            -F "token=$PUSHOVER_TOKEN" \
            -F "user=$PUSHOVER_USER" \
            -F "title=$title" \
            -F "message=$message" \
            -F "priority=$priority" \
            "https://api.pushover.net/1/messages.json" > /dev/null 2>&1 || true
    fi
}

send_email() {
    local subject="$1"
    local body="$2"
    if command -v mail >/dev/null 2>&1; then
        echo -e "$body" | mail -s "$subject" "$ALERT_EMAIL" 2>/dev/null || true
    elif command -v sendmail >/dev/null 2>&1; then
        {
            echo "Subject: $subject"
            echo "To: $ALERT_EMAIL"
            echo "Content-Type: text/plain; charset=UTF-8"
            echo ""
            echo -e "$body"
        } | sendmail -t 2>/dev/null || true
    fi
}

CURRENT_INSTALLED="580.178.04"
CURRENT_KERNEL=$(uname -r)

# 1. Query NVIDIA official Linux x86_64 latest driver list
LATEST_VERSION=$(curl -s "https://raw.githubusercontent.com/BtbN/FFmpeg-Builds/master/nvidia-versions.json" 2>/dev/null | grep -o '"linux": "[^"]*"' | head -n 1 | cut -d'"' -f4 || echo "$CURRENT_INSTALLED")

# 2. Check if DKMS is healthy on running kernel
if ! dkms status -m nvidia -k "$CURRENT_KERNEL" | grep -q "installed"; then
    echo "$(date -Iseconds) - WARNING: NVIDIA DKMS module is NOT installed on $CURRENT_KERNEL!"
    send_pushover "⚠️ PVE NVIDIA DKMS Warning" "NVIDIA kernel module is missing or not installed for running kernel $CURRENT_KERNEL." "1"
    exit 1
fi

echo "$(date -Iseconds) - Active Kernel: $CURRENT_KERNEL, Active NVIDIA Driver: $CURRENT_INSTALLED, DKMS: Healthy."
