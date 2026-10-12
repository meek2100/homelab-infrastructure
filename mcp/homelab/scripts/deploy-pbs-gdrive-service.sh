#!/bin/bash
set -euo pipefail

# 1. Create backup sync script inside PBS CT 105
pct exec 105 -- bash -c 'cat << "EOS" > /usr/local/bin/pbs-gdrive-sync.sh
#!/bin/bash
set -euo pipefail

echo "=================================================================="
echo "🚀 Starting PBS Chunks Sync to Encrypted Google Drive"
echo "Timestamp: $(date -Iseconds)"
echo "=================================================================="

rclone sync /backup/pbs-datastore/.chunks/ gdrive-encrypted:homelab-backups/pbs-chunks/ \
    --fast-list \
    --transfers 4 \
    --checkers 8 \
    --bwlimit 25M \
    --stats 30s \
    --stats-one-line \
    --log-file /var/log/rclone-pbs-sync.log \
    --log-level NOTICE

echo "✅ PBS Chunks successfully mirrored to Google Drive!"
EOS
chmod +x /usr/local/bin/pbs-gdrive-sync.sh
'

# 2. Create systemd service inside CT 105
pct exec 105 -- bash -c 'cat << "EOS" > /etc/systemd/system/pbs-gdrive-sync.service
[Unit]
Description=Proxmox Backup Server Encrypted Google Drive Mirror
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/pbs-gdrive-sync.sh
EOS
'

# 3. Create systemd timer inside CT 105 (Runs nightly at 03:00)
pct exec 105 -- bash -c 'cat << "EOS" > /etc/systemd/system/pbs-gdrive-sync.timer
[Unit]
Description=Nightly PBS Encrypted Google Drive Mirror Timer

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOS
systemctl daemon-reload
systemctl enable pbs-gdrive-sync.timer
systemctl start pbs-gdrive-sync.timer
'

echo "✅ PBS Google Drive Mirror systemd service and nightly timer deployed!"
