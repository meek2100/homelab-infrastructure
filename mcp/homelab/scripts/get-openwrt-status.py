#!/usr/bin/env python3
"""
OpenWrt Router Live Telemetry & Failover Status Tool
Queries OpenWrt router (192.168.1.226) over SSH to inspect system uptime,
interface link states, default route, and failover daemon status.
"""

import argparse
import os
import subprocess

def get_ssh_key():
    for candidate in [
        "/home/dtheurer/.ssh/pi_id_ed25519",
        os.path.expanduser("~/.ssh/pi_id_ed25519"),
        "/mnt/c/Users/dtheurer/.ssh/pi_id_ed25519",
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

def get_openwrt_status(ip="192.168.1.226", user="root"):
    query_cmd = """
echo "=== SYSTEM INFO ==="
cat /etc/openwrt_release 2>/dev/null | grep DISTRIB_DESCRIPTION
uptime

echo "=== DEFAULT ROUTING & GATEWAY ==="
ip route show default

echo "=== FAILOVER DAEMON STATE ==="
ps | grep -E "failover.sh|vxlan-nm" | grep -v grep || echo "No failover daemons currently running"

echo "=== NETWORK INTERFACES & IPS ==="
ip -br addr show

echo "=== VXLAN 150 & BRIDGE STATUS ==="
bridge vlan show dev wan 2>/dev/null
bridge vlan show dev vxlan150 2>/dev/null
"""




    code, out, err = run_ssh(ip, query_cmd, user=user)
    if code != 0:
        return f"❌ Error querying OpenWrt at {ip}: {err.strip()}"
    return out.strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query OpenWrt status.")
    parser.add_argument("--ip", default="192.168.1.226", help="OpenWrt IP")
    parser.add_argument("--user", default="root", help="SSH user")
    args = parser.parse_args()
    print(get_openwrt_status(ip=args.ip, user=args.user))
