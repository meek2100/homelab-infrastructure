#!/usr/bin/env python3
"""
backup-apt-packages.py
Captures the installed APT package manifests across all Proxmox hosts, QEMU VMs, and LXC containers.
Saves manifests to:
  - infrastructure/hosts/<node>/configs/apt-packages.txt
  - infrastructure/vms/<node>-<vmid>-<name>/configs/apt-packages.txt
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

def run_ssh_cmd(host_ip: str, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key and os.path.exists(key):
        ssh_args.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    ssh_args.extend([f"root@{host_ip}", cmd])
    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"SSH connection to {host_ip} timed out"
    except Exception as e:
        return 1, "", str(e)

def get_nodes():
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
    return nodes

def backup_host_packages(node: str, ip: str):
    print(f"📦 Backing up APT packages for Proxmox Host: {node} ({ip})...")
    cmd = "dpkg-query -f '${binary:Package}\n' -W"
    code, stdout, stderr = run_ssh_cmd(ip, cmd)
    if code != 0:
        print(f"  ❌ Error fetching packages for host {node}: {stderr.strip()}")
        return False
    
    lines = sorted(list(set(l.strip() for l in stdout.splitlines() if l.strip())))
    out_dir = os.path.join(REPO_ROOT, "infrastructure", "hosts", node, "configs")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "apt-packages.txt")
    with open(out_file, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  ✓ Saved {len(lines)} packages to {os.path.relpath(out_file, REPO_ROOT)}")
    return True

def backup_vm_packages(node: str, ip: str, vmid: str, name: str):
    print(f"  ↳ VM {vmid} ({name})...")
    cmd = f"qm guest exec {vmid} -- dpkg-query -f '${{binary:Package}}\\n' -W"
    code, stdout, stderr = run_ssh_cmd(ip, cmd, timeout=30)
    if code != 0:
        print(f"    ⚠️ Failed to query QGA for VM {vmid}: {stderr.strip()}")
        return False
    try:
        data = json.loads(stdout)
        pkg_output = data.get("out-data", "")
        if not pkg_output:
            print(f"    ⚠️ No package data returned from QGA for VM {vmid}")
            return False
        lines = sorted(list(set(l.strip() for l in pkg_output.splitlines() if l.strip())))
        target_dir = os.path.join(REPO_ROOT, "infrastructure", "vms", f"{node}-{vmid}-{name}", "configs")
        os.makedirs(target_dir, exist_ok=True)
        out_file = os.path.join(target_dir, "apt-packages.txt")
        with open(out_file, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"    ✓ Saved {len(lines)} packages to {os.path.relpath(out_file, REPO_ROOT)}")
        return True
    except Exception as e:
        print(f"    ❌ Error parsing QGA response for VM {vmid}: {e}")
        return False

def backup_lxc_packages(node: str, ip: str, vmid: str, name: str):
    print(f"  ↳ LXC Container {vmid} ({name})...")
    cmd = f"pct exec {vmid} -- dpkg-query -f '${{binary:Package}}\\n' -W"
    code, stdout, stderr = run_ssh_cmd(ip, cmd, timeout=30)
    if code != 0:
        print(f"    ⚠️ Failed to query LXC {vmid}: {stderr.strip()}")
        return False
    lines = sorted(list(set(l.strip() for l in stdout.splitlines() if l.strip())))
    target_dir = os.path.join(REPO_ROOT, "infrastructure", "vms", f"{node}-{vmid}-{name}", "configs")
    os.makedirs(target_dir, exist_ok=True)
    out_file = os.path.join(target_dir, "apt-packages.txt")
    with open(out_file, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"    ✓ Saved {len(lines)} packages to {os.path.relpath(out_file, REPO_ROOT)}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Backup APT packages across Proxmox fleet")
    parser.add_argument("--node", help="Specific node to backup (default: all)")
    args = parser.parse_args()

    nodes = get_nodes()
    if args.node:
        if args.node not in nodes:
            print(f"❌ Unknown node: {args.node}. Configured nodes: {list(nodes.keys())}")
            sys.exit(1)
        nodes = {args.node: nodes[args.node]}

    print("============================================================")
    print("📦 FLEET APT PACKAGE INVENTORY BACKUP")
    print("============================================================")

    for node, ip in nodes.items():
        backup_host_packages(node, ip)

        code, stdout, _ = run_ssh_cmd(ip, "qm list")
        if code == 0:
            for line in stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    vmid, name, status = parts[0], parts[1], parts[2]
                    if status == "running":
                        backup_vm_packages(node, ip, vmid, name)

        code, stdout, _ = run_ssh_cmd(ip, "pct list 2>/dev/null || true")
        if code == 0:
            for line in stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    vmid, status, name = parts[0], parts[1], parts[-1]
                    if status == "running":
                        backup_lxc_packages(node, ip, vmid, name)

    print("\n============================================================")
    print("✅ Fleet APT Package Inventory Backup Complete!")
    print("============================================================")

if __name__ == "__main__":
    main()
