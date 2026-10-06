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

ROUTERS = {
    "aurora": "10.25.25.1",
    "luna": "10.20.20.1",
}

def get_single_ddwrt_status(ip: str, name: str = "", user="root"):
    query_cmd = """
echo "=== SYSTEM INFO ==="
echo "Model: $(nvram get DD_BOARD 2>/dev/null)"
echo "Firmware: DD-WRT $(nvram get dist_type 2>/dev/null) build $(nvram get os_version 2>/dev/null)"
uname -a
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
    header = f"=== DD-WRT ROUTER: {name.upper() if name else ip} ({ip}) ==="
    if code != 0:
        return f"{header}\n❌ Error querying DD-WRT router at {ip}: {err.strip()}"
    return f"{header}\n{out.strip()}"

def get_ddwrt_status(router="all", ip=None, user="root"):
    if ip:
        return get_single_ddwrt_status(ip=ip, user=user)
    
    router = router.lower().strip()
    if router in ROUTERS:
        return get_single_ddwrt_status(ip=ROUTERS[router], name=router, user=user)
    elif router == "all":
        results = []
        for r_name, r_ip in ROUTERS.items():
            results.append(get_single_ddwrt_status(ip=r_ip, name=r_name, user=user))
        return "\n\n".join(results)
    return f"Unknown router: '{router}'. Valid options: aurora, luna, all."

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query DD-WRT router status.")
    parser.add_argument("--router", default="all", choices=["aurora", "luna", "all"], help="Target DD-WRT router")
    parser.add_argument("--ip", default=None, help="DD-WRT IP override")
    parser.add_argument("--user", default="root", help="SSH user")
    args = parser.parse_args()
    print(get_ddwrt_status(router=args.router, ip=args.ip, user=args.user))
