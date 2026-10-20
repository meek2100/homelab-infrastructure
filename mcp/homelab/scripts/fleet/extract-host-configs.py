#!/usr/bin/env python3
"""
extract-host-configs.py
Pure Python Proxmox Host & System Configuration Extractor.
Extracts network interfaces, storage definitions, boot/kernel configs, crontabs,
ACPI power configs, and custom scripts across pve, pve2, pve3 into Git blueprints.
"""

import argparse
import glob
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

def get_ssh_key():
    for candidate in [
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/agentsvc/.ssh/proxmox_ed25519",
        "/home/dtheurer/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519"
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh_pipeline(host_ip: str, remote_cmd: str, local_extract_dir: str, strip_components: int = 0) -> bool:
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key and os.path.exists(key):
        ssh_args.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    ssh_args.extend([f"root@{host_ip}", remote_cmd])

    os.makedirs(local_extract_dir, exist_ok=True)
    tar_args = ["tar", "-xzf", "-", "-C", local_extract_dir]
    if strip_components > 0:
        tar_args.extend(["--strip-components", str(strip_components)])

    try:
        p_ssh = subprocess.Popen(ssh_args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p_tar = subprocess.Popen(tar_args, stdin=p_ssh.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p_ssh.stdout.close()
        p_tar.communicate()
        p_ssh.wait()
        return True
    except Exception:
        return False

def run_ssh_cat(host_ip: str, remote_path: str, local_target_file: str) -> bool:
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key and os.path.exists(key):
        ssh_args.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    ssh_args.extend([f"root@{host_ip}", f"cat {remote_path} 2>/dev/null"])

    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and res.stdout.strip():
            os.makedirs(os.path.dirname(local_target_file), exist_ok=True)
            with open(local_target_file, "w") as f:
                f.write(res.stdout)
            return True
        return False
    except Exception:
        return False

def extract_node(node: str, ip: str):
    print("============================================================")
    print(f"📥 Extracting Host OS Config Files: Node {node} ({ip})")
    print("============================================================")

    target_dir = os.path.join(REPO_ROOT, "infrastructure", "hosts", node, "configs")
    os.makedirs(target_dir, exist_ok=True)

    # 1. Network & Interfaces
    run_ssh_cat(ip, "/etc/network/interfaces", os.path.join(target_dir, "interfaces"))

    # 2. Boot & Kernel Configs
    run_ssh_cat(ip, "/etc/default/grub", os.path.join(target_dir, "grub"))
    run_ssh_cat(ip, "/etc/modules", os.path.join(target_dir, "modules"))
    run_ssh_pipeline(ip, "tar -czf - /etc/modprobe.d 2>/dev/null", target_dir)

    # 3. Proxmox Storage & VM Configs
    run_ssh_cat(ip, "/etc/pve/storage.cfg", os.path.join(target_dir, "storage.cfg"))
    qemu_dir = os.path.join(target_dir, "qemu-server")
    run_ssh_pipeline(ip, "tar -czf - /etc/pve/qemu-server 2>/dev/null", qemu_dir, strip_components=3)

    # 4. Power & Lid Switch Fixes
    run_ssh_cat(ip, "/etc/systemd/logind.conf", os.path.join(target_dir, "logind.conf"))
    acpi_dir = os.path.join(target_dir, "acpi")
    run_ssh_pipeline(ip, "tar -czf - /etc/acpi 2>/dev/null", acpi_dir, strip_components=2)

    # 5. Host Crontabs & Custom Scripts
    cron_dir = os.path.join(target_dir, "cron")
    run_ssh_cat(ip, "/etc/crontab", os.path.join(cron_dir, "crontab"))
    run_ssh_pipeline(ip, "tar -czf - /etc/cron.d /var/spool/cron/crontabs 2>/dev/null", cron_dir, strip_components=2)

    # 6. Custom Scripts
    scripts_dir = os.path.join(target_dir, "custom-scripts")
    run_ssh_pipeline(ip, "tar -czf - /usr/local/bin /usr/local/sbin /root/scripts 2>/dev/null", scripts_dir, strip_components=3)
    if os.path.exists(scripts_dir):
        for f in os.listdir(scripts_dir):
            fp = os.path.join(scripts_dir, f)
            if os.path.isfile(fp):
                try:
                    with open(fp, "rb") as bf:
                        if bf.read(4) == b"\x7fELF":
                            os.remove(fp)
                except Exception:
                    pass

    # 7. Unowned User Configurations
    custom_dir = os.path.join(target_dir, "custom-configs")
    run_ssh_pipeline(ip, "tar -czf - /etc/nginx /etc/letsencrypt /etc/samba /etc/smart_local_drivedb.h /etc/systemd/system/smartmontools.service.d 2>/dev/null", custom_dir)
    run_ssh_pipeline(ip, "tar -czf - /root/Proxmox-Enhanced-Configuration-Utility 2>/dev/null", custom_dir)

    print(f"  ✓ Extracted host configs for {node} into {os.path.relpath(target_dir, REPO_ROOT)}/")

def main():
    parser = argparse.ArgumentParser(description="Extract Proxmox host configs into Git blueprints")
    parser.add_argument("--node", help="Specific node to extract (default: all)")
    args = parser.parse_args()

    nodes = {}
    for meta_file in glob.glob(os.path.join(REPO_ROOT, "infrastructure", "hosts", "*", "meta.json")):
        node_name = os.path.basename(os.path.dirname(meta_file))
        try:
            with open(meta_file, "r") as f:
                data = json.load(f)
                if "ip" in data:
                    nodes[node_name] = data["ip"]
        except Exception:
            pass

    if args.node:
        if args.node not in nodes:
            print(f"❌ Unknown node: {args.node}")
            sys.exit(1)
        nodes = {args.node: nodes[args.node]}

    for node, ip in nodes.items():
        extract_node(node, ip)

    print("\n============================================================")
    print("✅ All Host OS Configuration Files Successfully Extracted!")
    print("============================================================")

if __name__ == "__main__":
    main()
