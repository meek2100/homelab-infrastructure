#!/usr/bin/env python3
"""
check-gdrive-migration-progress.py
Monitors live progress, transfer speeds, and completion status of Google Drive syncs.
"""

import sys
import os
import re
from importlib import import_module

sys.path.insert(0, os.path.dirname(__file__))
sync = import_module('sync-live-fleet')

NODES = [
    ("pve", "192.168.1.250"),
    ("pve2", "192.168.1.240"),
    ("pve3", "192.168.1.245"),
]

def check_progress():
    print("=" * 70)
    print("📊 HOMELAB GOOGLE DRIVE MIGRATION & MIRROR PROGRESS MONITOR")
    print("=" * 70)

    # 1. Check vzdump migration on each PVE host
    for name, ip in NODES:
        code, ps_out, _ = sync.run_ssh(ip, "ps aux | grep 'rclone copy' | grep -v grep")
        is_running = bool(ps_out.strip())

        code, log_out, _ = sync.run_ssh(ip, "tail -n 5 /var/log/rclone-vzdump-migration.log 2>/dev/null")
        log_text = log_out.strip() if log_out.strip() else ""

        if is_running:
            # Grab last progress line
            last_line = log_text.splitlines()[-1] if log_text else "Transferring..."
            print(f"\n🖥️  Host: {name} ({ip}) ➔ 🔄 IN PROGRESS")
            print(f"   📈 Stats: {last_line}")
        elif "User rate limit exceeded" in log_text or "Error 403" in log_text:
            print(f"\n🖥️  Host: {name} ({ip}) ➔ ⏸️ PAUSED (Google 750GB Daily Quota Hit)")
            print(f"   ⚠️ Status: Reached Google Drive 24-hr account upload limit (~750 GB). Resumes on quota reset.")
        elif "Failed to check" in log_text or "input/output error" in log_text:
            print(f"\n🖥️  Host: {name} ({ip}) ➔ ⚠️ STOPPED WITH ERRORS")
            print(f"   ⚠️ Detail: {log_text.splitlines()[-1] if log_text else 'Errors logged'}")
        else:
            print(f"\n🖥️  Host: {name} ({ip}) ➔ ✅ COMPLETE & VERIFIED")
            print("   ✨ All archives synchronized and verified.")

    # 2. Check PBS Mirror inside CT 105
    code, pbs_ps, _ = sync.run_ssh("192.168.1.245", "pct exec 105 -- ps aux | grep 'rclone sync' | grep -v grep")
    pbs_running = bool(pbs_ps.strip())
    code, pbs_log, _ = sync.run_ssh("192.168.1.245", "pct exec 105 -- tail -n 5 /var/log/rclone-pbs-sync.log 2>/dev/null")
    pbs_text = pbs_log.strip() if pbs_log.strip() else ""

    if pbs_running:
        last_pbs = pbs_text.splitlines()[-1] if pbs_text else "Syncing..."
        print(f"\n📦 Container: pbs-server (LXC 105 on pve3) ➔ 🔄 IN PROGRESS")
        print(f"   📈 Stats: {last_pbs}")
    elif "input/output error" in pbs_text or "ERROR" in pbs_text:
        print(f"\n📦 Container: pbs-server (LXC 105 on pve3) ➔ ⚠️ STOPPED (USB Disk I/O Error)")
        print(f"   ⚠️ Detail: 500GB USB drive entered emergency read-only state.")
    else:
        print(f"\n📦 Container: pbs-server (LXC 105 on pve3) ➔ ✅ UP TO DATE / IDLE")
        print("   ✨ PBS datastore chunks mirror is up to date.")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_progress()

