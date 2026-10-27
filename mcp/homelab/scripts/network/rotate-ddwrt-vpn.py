#!/usr/bin/env python3
"""
DD-WRT Aurora Router PIA VPN Rotation Trigger Tool
Connects to Aurora (10.25.25.1) over Dropbear SSH and triggers /opt/sbin/pia-rotate.
"""

import argparse
import os
import subprocess

def get_ssh_key():
    for candidate in [
        os.path.expanduser("~/.ssh/ddwrt_id_ed25519"),
        "/home/dtheurer/.ssh/ddwrt_id_ed25519",
        "/mnt/c/Users/dtheurer/.ssh/ddwrt_id_ed25519",
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh(ip, cmd, user="root", timeout=60):
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    ]
    if key: ssh_args.extend(["-i", key])
    ssh_args.extend([f"{user}@{ip}", cmd])
    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "SSH command timed out after 60s"
    except Exception as e:
        return 1, "", str(e)

def rotate_vpn(ip="10.25.25.1", user="root"):
    print(f"🔄 Triggering PIA WireGuard rotation on Aurora ({ip})...")
    code, out, err = run_ssh(ip, "/opt/sbin/pia-rotate", user=user, timeout=60)
    if code != 0 and not out:
        return f"❌ Failed to trigger rotation on {ip}: {err.strip()}"
    output = out.strip()
    if err and "Broken pipe" not in err:
        output += f"\n[stderr: {err.strip()}]"
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger PIA rotation on DD-WRT Aurora.")
    parser.add_argument("--ip", default="10.25.25.1", help="Aurora IP")
    parser.add_argument("--user", default="root", help="SSH user")
    args = parser.parse_args()
    print(rotate_vpn(ip=args.ip, user=args.user))
