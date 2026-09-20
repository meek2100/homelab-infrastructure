#!/usr/bin/env python3
"""
DD-WRT Router Live Telemetry & PIA VPN Watchdog Status Tool
Queries DD-WRT router (aurora: 10.25.25.1) over SSH to inspect system uptime,
active WAN and VPN IP, and PIA watchdog status.
"""

import argparse
import os
import subprocess

def get_ssh_key():
    for candidate in [
        "/home/dtheurer/.ssh/ddwrt_id_ed25519",
        os.path.expanduser("~/.ssh/ddwrt_id_ed25519"),
        "/mnt/c/Users/dtheurer/.ssh/ddwrt_id_ed25519",
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh(ip, cmd, user="root", timeout=15):
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
    ]
    if key: ssh_args.extend(["-i", key])
    ssh_args.extend([f"{user}@{ip}", cmd])
    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)

def get_ddwrt_status(ip="10.25.25.1", user="root"):
    query_cmd = """
echo "=== SYSTEM INFO ==="
uname -a
nvram get os_version 2>/dev/null
uptime

echo "=== WAN & DEFAULT ROUTE ==="
nvram get wan_ipaddr 2>/dev/null
ip route show default

echo "=== PIA WATCHDOG & DAEMONS ==="
ps | grep -E "pia-watchdog|openvpn" | grep -v grep || echo "No PIA watchdog or openvpn processes found"

echo "=== CRON JOBS ==="
nvram get cron_jobs 2>/dev/null

echo "=== OPT STORAGE & DISK ==="
df -h /opt 2>/dev/null
"""
    code, out, err = run_ssh(ip, query_cmd, user=user)
    if code != 0:
        return f"❌ Error querying DD-WRT router at {ip}: {err.strip()}"
    return out.strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query DD-WRT router status.")
    parser.add_argument("--ip", default="10.25.25.1", help="DD-WRT IP")
    parser.add_argument("--user", default="root", help="SSH user")
    args = parser.parse_args()
    print(get_ddwrt_status(ip=args.ip, user=args.user))
