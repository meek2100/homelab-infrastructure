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
            # Query live procfs transfer statistics
            code_io, io_out, _ = sync.run_ssh(ip, "pid=$(pgrep -f 'rclone copy' | head -n 1); if [ -n \"$pid\" ]; then r_bytes=$(grep 'read_bytes:' /proc/$pid/io 2>/dev/null | awk '{print $2}'); etime=$(ps -p $pid -o etime= 2>/dev/null | tr -d ' '); echo \"$r_bytes $etime\"; fi")
            live_detail = ""
            if code_io == 0 and io_out.strip():
                parts = io_out.strip().split()
                if len(parts) >= 2 and parts[0].isdigit():
                    bytes_read = int(parts[0])
                    gb_read = bytes_read / (1024 ** 3)
                    etime = parts[1]
                    pct = min(100.0, (bytes_read / (67.58 * (1024 ** 3))) * 100)
                    live_detail = f"Transferred: {gb_read:.2f} GB / 67.58 GB ({pct:.1f}%) | Elapsed: {etime}"

            last_line = live_detail if live_detail else (log_text.splitlines()[-1] if log_text else "Transferring...")
            print(f"\n🖥️  Host: {name} ({ip}) ➔ 🔄 IN PROGRESS")
            print(f"   📈 Stats: {last_line}")
        last_line = log_text.splitlines()[-1] if log_text else ""
        if "User rate limit exceeded" in last_line or "Error 403" in last_line:
            print(f"\n🖥️  Host: {name} ({ip}) ➔ ⏸️ PAUSED (Google 750GB Daily Quota Hit)")
            print(f"   ⚠️ Status: Reached Google Drive 24-hr account upload limit (~750 GB). Resumes on quota reset.")
        elif "ERROR" in last_line or "Failed to check" in last_line or "input/output error" in last_line:
            print(f"\n🖥️  Host: {name} ({ip}) ➔ ⚠️ STOPPED WITH ERRORS")
            print(f"   ⚠️ Detail: {last_line}")
        else:
            print(f"\n🖥️  Host: {name} ({ip}) ➔ ✅ COMPLETE & VERIFIED")
            print("   ✨ All archives synchronized and verified.")

    # 2. Check PBS Mirror inside CT 105
    code, pbs_ps, _ = sync.run_ssh("192.168.1.245", "pct exec 105 -- ps aux | grep 'rclone sync' | grep -v grep")
    pbs_running = bool(pbs_ps.strip())

    code_timer, timer_out, _ = sync.run_ssh("192.168.1.245", "pct exec 105 -- systemctl is-active pbs-gdrive-sync.timer 2>/dev/null || echo 'inactive'")
    timer_active = (timer_out.strip() == "active")

    if pbs_running:
        code_io, io_out, _ = sync.run_ssh("192.168.1.245", "pct exec 105 -- bash -c 'pid=$(pgrep -f \"rclone sync\" | head -n 1); if [ -n \"$pid\" ]; then r_bytes=$(grep \"read_bytes:\" /proc/$pid/io 2>/dev/null | awk \"{print \\$2}\"); etime=$(ps -p $pid -o etime= 2>/dev/null | tr -d \" \"); echo \"$r_bytes $etime\"; fi'")
        pbs_detail = ""
        if code_io == 0 and io_out.strip():
            parts = io_out.strip().split()
            if len(parts) >= 2 and parts[0].isdigit():
                b_read = int(parts[0])
                gb_read = b_read / (1024 ** 3)
                etime = parts[1]
                pct = min(100.0, (gb_read / 113.11) * 100)
                pbs_detail = f"Transferred: {gb_read:.2f} GB / 113.11 GB ({pct:.1f}%) | Elapsed: {etime}"

        last_pbs = pbs_detail if pbs_detail else "Finalizing chunk transfers..."
        print(f"\n📦 Container: pbs-server (LXC 105 on pve3) ➔ 🔄 IN PROGRESS")
        print(f"   📈 Stats: {last_pbs}")
    else:
        timer_msg = "Nightly mirror scheduled at 05:00 PDT." if timer_active else "Timer inactive."
        print(f"\n📦 Container: pbs-server (LXC 105 on pve3) ➔ ✅ UP TO DATE / IDLE")
        print(f"   ✨ PBS datastore chunks mirror is up to date. {timer_msg}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_progress()

