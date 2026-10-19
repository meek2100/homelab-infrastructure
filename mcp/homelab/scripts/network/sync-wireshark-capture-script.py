#!/usr/bin/env python3
"""
Sync Wireshark Headless Capture Daemon Script from luna-server (VM 102)
Pulls custom-services.d scripts and documentation via QEMU Guest Agent base64 streaming
and archives them into infrastructure/docker-stacks/luna-server/48/
"""

import base64
import json
import os
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PVE_HOST_IP = "192.168.1.250"
LUNA_VMID = 102
TARGET_STACK_DIR = os.path.join(REPO_ROOT, "infrastructure", "docker-stacks", "luna-server", "48")

def get_ssh_key():
    for candidate in [
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/dtheurer/.ssh/proxmox_ed25519",
        "/home/agentsvc/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519",
        "/home/agentsvc/.ssh/id_ed25519",
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh(ip, cmd, timeout=30):
    key = get_ssh_key()
    ssh_args = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=8",
    ]
    if key and os.path.exists(key):
        ssh_args.extend(["-i", key])
    ssh_args.extend([f"root@{ip}", cmd])

    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "SSH connection timed out"
    except Exception as e:
        return 1, "", str(e)

def run_qga_b64(host_ip, vmid, file_path):
    cmd = f"qm guest exec {vmid} -- base64 -w 0 '{file_path}'"
    code, stdout, _ = run_ssh(host_ip, cmd, timeout=30)
    if code != 0 or not stdout:
        return None
    try:
        payload = json.loads(stdout)
        b64_data = payload.get("out-data", "").strip()
        if not b64_data:
            return None
        return base64.b64decode(b64_data).decode("utf-8", errors="replace")
    except Exception:
        return None

def run_qga_cmd(host_ip, vmid, inner_cmd):
    cmd = f"qm guest exec {vmid} -- {inner_cmd}"
    code, stdout, _ = run_ssh(host_ip, cmd, timeout=30)
    if code != 0 or not stdout:
        return None
    try:
        payload = json.loads(stdout)
        return payload.get("out-data", "")
    except Exception:
        return None

def sync_wireshark_capture():
    print(f"📡 Querying VM {LUNA_VMID} (luna-server) on {PVE_HOST_IP} for Wireshark capture scripts...")
    
    # 1. Discover custom-services.d and GUI_MANUAL_CAPTURE.md specifically
    list_out = run_qga_cmd(
        PVE_HOST_IP,
        LUNA_VMID,
        "find /home/meek2100/docker/wireshark/custom-services.d/ /home/meek2100/docker/wireshark/GUI_MANUAL_CAPTURE.md -type f 2>/dev/null"
    )
    if not list_out or not list_out.strip():
        # Fallback to search explicitly for those specific items
        list_out = run_qga_cmd(
            PVE_HOST_IP,
            LUNA_VMID,
            "find /home/meek2100/docker/wireshark/ -name 'GUI_MANUAL_CAPTURE.md' -o -path '*/custom-services.d/*' 2>/dev/null"
        )

    if not list_out or not list_out.strip():
        print(f"⚠️  Could not locate Wireshark custom scripts or guides on VM {LUNA_VMID}.")
        return "No Wireshark custom scripts found on VM 102."

    found_files = [f.strip() for f in list_out.strip().splitlines() if f.strip() and not f.strip().endswith(('.cache', '.tdb', '.key', '.pem', '.lock'))]
    print(f"✓ Discovered {len(found_files)} files: {found_files}")

    dest_services_dir = os.path.join(TARGET_STACK_DIR, "custom-services.d")
    os.makedirs(dest_services_dir, exist_ok=True)

    synced = []
    for remote_f in found_files:
        content = run_qga_b64(PVE_HOST_IP, LUNA_VMID, remote_f)
        if not content:
            continue
        base_name = os.path.basename(remote_f)
        if "custom-services.d" in remote_f:
            dest_f = os.path.join(dest_services_dir, base_name)
        else:
            dest_f = os.path.join(TARGET_STACK_DIR, base_name)

        with open(dest_f, "w", encoding="utf-8") as out_f:
            out_f.write(content)
        synced.append(f"{base_name} ({len(content)} bytes)")

    summary = f"✅ Successfully synced {len(synced)} Wireshark scripts into {TARGET_STACK_DIR}: {', '.join(synced)}"
    print(summary)
    return summary

if __name__ == "__main__":
    sync_wireshark_capture()
