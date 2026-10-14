#!/usr/bin/env python3
"""
sync-pbs-backup-to-gdrive.py
Standalone Proxmox Backup Server (PBS) Google Drive Mirror Orchestrator.
Manages encrypted chunk and metadata mirroring from LXC 105 to Google Drive.
Enforces mutual exclusion with legacy vzdump migrations to prevent bandwidth/rate-limit contention.
"""

import sys
import os
import argparse
from importlib import import_module

sys.path.insert(0, os.path.dirname(__file__))
sync = import_module('sync-live-fleet')

PVE3_IP = "192.168.1.245"
PBS_CT_ID = "105"
VZDUMP_NODES = [
    ("pve", "192.168.1.250"),
    ("pve2", "192.168.1.240"),
    ("pve3", "192.168.1.245"),
]

def check_vzdump_running():
    """Verify if any legacy vzdump migrations are actively running across the fleet."""
    running_hosts = []
    for name, ip in VZDUMP_NODES:
        code, ps_out, _ = sync.run_ssh(ip, "ps aux | grep 'rclone copy' | grep -v grep")
        if ps_out.strip():
            running_hosts.append(f"{name} ({ip})")
    return running_hosts

def get_pbs_status():
    """Query live execution and timer state of the PBS mirror inside LXC 105."""
    code, ps_out, _ = sync.run_ssh(PVE3_IP, f"pct exec {PBS_CT_ID} -- ps aux | grep 'rclone sync' | grep -v grep || true")
    is_running = bool(ps_out.strip())

    code, timer_out, _ = sync.run_ssh(PVE3_IP, f"pct exec {PBS_CT_ID} -- systemctl is-active pbs-gdrive-sync.timer 2>/dev/null || echo 'inactive'")
    timer_active = (timer_out.strip() == "active")

    code, log_out, _ = sync.run_ssh(PVE3_IP, f"pct exec {PBS_CT_ID} -- tail -n 10 /var/log/rclone-pbs-sync.log 2>/dev/null || true")

    return {
        "running": is_running,
        "timer_active": timer_active,
        "logs": log_out.strip(),
    }

def deploy_service():
    """Deploy the robust sync script, systemd service, and nightly timer into LXC 105."""
    print("📦 Deploying PBS Google Drive mirror sync script and timer to LXC 105...")

    sync_script = """#!/bin/bash
set -euo pipefail

echo "=================================================================="
echo "🚀 Starting PBS Full Datastore Sync to Encrypted Google Drive"
echo "Timestamp: $(date -Iseconds)"
echo "=================================================================="

rclone sync /backup/pbs-datastore/ gdrive-encrypted:homelab-backups/pbs-datastore/ \\
    --fast-list \\
    --transfers 4 \\
    --checkers 8 \\
    --bwlimit 25M \\
    --exclude ".lock" \\
    --exclude "lost+found/**" \\
    --stats 30s \\
    --stats-one-line \\
    --log-file /var/log/rclone-pbs-sync.log \\
    --log-level NOTICE

echo "✅ PBS Datastore successfully mirrored to Google Drive!"
"""

    code, _, err = sync.run_ssh(PVE3_IP, f"pct exec {PBS_CT_ID} -- bash -c 'cat << \"EOF\" > /usr/local/bin/pbs-gdrive-sync.sh\n{sync_script}\nEOF\nchmod +x /usr/local/bin/pbs-gdrive-sync.sh'")
    if code != 0:
        raise RuntimeError(f"Failed to write sync script: {err}")

    service_unit = """[Unit]
Description=Proxmox Backup Server Encrypted Google Drive Mirror
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/pbs-gdrive-sync.sh
StandardOutput=journal
StandardError=journal
"""

    timer_unit = """[Unit]
Description=Nightly PBS Encrypted Google Drive Mirror Timer

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""

    deploy_cmd = f"""pct exec {PBS_CT_ID} -- bash -c '
cat << "EOF" > /etc/systemd/system/pbs-gdrive-sync.service
{service_unit}
EOF
cat << "EOF" > /etc/systemd/system/pbs-gdrive-sync.timer
{timer_unit}
EOF
systemctl daemon-reload
systemctl enable pbs-gdrive-sync.timer
systemctl restart pbs-gdrive-sync.timer
'"""

    code, _, err = sync.run_ssh(PVE3_IP, deploy_cmd)
    if code != 0:
        raise RuntimeError(f"Failed to configure systemd units: {err}")

    print("✅ Successfully deployed PBS sync service and enabled nightly timer (03:00)!")

def start_sync(force=False):
    """Trigger manual run of PBS sync, enforcing mutex against vzdump unless forced."""
    running_vzdump = check_vzdump_running()
    if running_vzdump and not force:
        print("⚠️ CONTROLLER LOCKOUT PREVENTED:")
        print(f"Legacy vzdump migration is currently active on: {', '.join(running_vzdump)}")
        print("Refusing to start PBS mirror simultaneously to protect network bandwidth and avoid Google Drive rate limits.")
        print("Wait for vzdump migrations to finish, or pass --force to override.")
        sys.exit(1)

    print("🚀 Triggering PBS Google Drive mirror sync inside LXC 105...")
    code, _, err = sync.run_ssh(PVE3_IP, f"pct exec {PBS_CT_ID} -- nohup /usr/local/bin/pbs-gdrive-sync.sh >/dev/null 2>&1 &")
    if code != 0:
        raise RuntimeError(f"Failed to start sync: {err}")
    print("✅ PBS sync job started in background.")

def main():
    parser = argparse.ArgumentParser(description="PBS Encrypted Google Drive Mirror Orchestrator")
    parser.add_argument("action", choices=["status", "deploy", "start", "stop", "logs"], default="status", nargs="?", help="Action to perform")
    parser.add_argument("--force", action="store_true", help="Override vzdump concurrency mutex")
    args = parser.parse_args()

    if args.action == "status":
        vzdump_active = check_vzdump_running()
        st = get_pbs_status()
        print("=" * 65)
        print("📦 PROXMOX BACKUP SERVER (PBS) OFFSITE GOOGLE DRIVE STATUS")
        print("=" * 65)
        print(f"Node:              pve3 ({PVE3_IP})")
        print(f"Container:         LXC {PBS_CT_ID} (pbs-server)")
        print(f"Sync Job State:    {'RUNNING' if st['running'] else 'IDLE'}")
        print(f"Nightly Timer:     {'ACTIVE (03:00 daily)' if st['timer_active'] else 'INACTIVE'}")
        print(f"vzdump Mutex:      {'BLOCKED by ' + ', '.join(vzdump_active) if vzdump_active else 'CLEAR (No active vzdump jobs)'}")
        print("\nRecent Logs:")
        print("-" * 65)
        print(st["logs"] if st["logs"] else "No recent log entries.")
        print("=" * 65)

    elif args.action == "deploy":
        deploy_service()

    elif args.action == "start":
        start_sync(force=args.force)

    elif args.action == "stop":
        print("🛑 Halting PBS sync inside LXC 105...")
        sync.run_ssh(PVE3_IP, f"pct exec {PBS_CT_ID} -- pkill -f 'rclone sync' || true")
        print("✅ PBS sync process terminated.")

    elif args.action == "logs":
        st = get_pbs_status()
        print(st["logs"] if st["logs"] else "No log entries found.")

if __name__ == "__main__":
    main()
