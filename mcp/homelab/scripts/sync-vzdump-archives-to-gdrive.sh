#!/bin/bash
set -euo pipefail

NODE="$1"
REMOTE_PATH="gdrive-encrypted:homelab-archives/vzdumps/${NODE}"

echo "=================================================================="
echo "🚀 Starting Encrypted Backup Stream to Google Drive for: ${NODE}"
echo "Target: ${REMOTE_PATH}"
echo "=================================================================="

# Detect backup directories
DIRS=()
[ -d "/mnt/pve/backup/dump" ] && DIRS+=("/mnt/pve/backup/dump")
[ -d "/mnt/pve/backup-sd/dump" ] && DIRS+=("/mnt/pve/backup-sd/dump")

for src in "${DIRS[@]}"; do
    echo "📦 Syncing directory: ${src} -> ${REMOTE_PATH}"
    rclone copy "${src}" "${REMOTE_PATH}" \
        --fast-list \
        --transfers 4 \
        --checkers 8 \
        --bwlimit 25M \
        --stats 15s \
        --stats-one-line \
        --checksum \
        --log-file "/var/log/rclone-vzdump-migration.log" \
        --log-level NOTICE
done

echo "✅ Node ${NODE} vzdump archives successfully synchronized to Google Drive!"
