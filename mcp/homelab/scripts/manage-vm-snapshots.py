#!/usr/bin/env python3
"""
Proxmox Hypervisor VM Snapshot & Backup Tool
Provides programmatic snapshot creation, listing, rollback, deletion, and vzdump backups.
"""

import os
import sys
import json
import subprocess
import argparse

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

DEFAULT_NODE_IPS = {
    "pve": "192.168.1.250",
    "pve2": "192.168.1.240",
    "pve3": "192.168.1.245"
}

def get_node_ip(node_name):
    meta_path = os.path.join(REPO_ROOT, "infrastructure", "hosts", node_name, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f).get("ip")
        except Exception:
            pass
    return DEFAULT_NODE_IPS.get(node_name)

def get_ssh_key():
    for candidate in [
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/dtheurer/.ssh/proxmox_ed25519",
        "/home/agentsvc/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519"
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh(host_ip, cmd, timeout=300):
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=8",
    ]
    if key:
        ssh_args.extend(["-i", key])
    ssh_args.extend([f"root@{host_ip}", cmd])

    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)

def get_guest_tool(ip, vmid):
    """Detects whether target is a QEMU VM (qm) or LXC Container (pct)."""
    check_cmd = f"test -f /etc/pve/qemu-server/{vmid}.conf && echo qm || (test -f /etc/pve/lxc/{vmid}.conf && echo pct || echo qm)"
    code, stdout, _ = run_ssh(ip, check_cmd, timeout=10)
    if code == 0 and stdout.strip() in ["qm", "pct"]:
        return stdout.strip()
    return "qm"

def create_snapshot(node, vmid, snap_name, description="", include_ram=False):
    ip = get_node_ip(node)
    if not ip:
        return f"Error: Node {node} IP not found."

    tool = get_guest_tool(ip, vmid)
    label = "VM" if tool == "qm" else "LXC"

    cmd = f"{tool} snapshot {vmid} '{snap_name}'"
    if description:
        cmd += f" --description '{description}'"
    if include_ram and tool == "qm":
        cmd += " --vmstate 1"

    print(f"📸 Creating snapshot '{snap_name}' for {label} {vmid} on {node} ({ip})...")
    code, stdout, stderr = run_ssh(ip, cmd, timeout=120)
    if code == 0:
        return f"✅ Snapshot '{snap_name}' successfully created for {label} {vmid} on {node}.\n{stdout.strip()}"
    return f"❌ Failed to create snapshot for {label} {vmid} on {node} (exit code {code}):\n{stderr.strip()}\n{stdout.strip()}"

def list_snapshots(node, vmid):
    ip = get_node_ip(node)
    if not ip:
        return f"Error: Node {node} IP not found."

    tool = get_guest_tool(ip, vmid)
    label = "VM" if tool == "qm" else "LXC"

    cmd = f"{tool} listsnapshot {vmid}"
    code, stdout, stderr = run_ssh(ip, cmd, timeout=30)
    if code == 0:
        return stdout.strip() or f"No snapshots found for {label} {vmid} on {node}."
    return f"❌ Failed to list snapshots for {label} {vmid} on {node}:\n{stderr.strip()}"

def rollback_snapshot(node, vmid, snap_name):
    ip = get_node_ip(node)
    if not ip:
        return f"Error: Node {node} IP not found."

    tool = get_guest_tool(ip, vmid)
    label = "VM" if tool == "qm" else "LXC"

    cmd = f"{tool} rollback {vmid} '{snap_name}'"
    print(f"🔄 Rolling back {label} {vmid} on {node} to snapshot '{snap_name}'...")
    code, stdout, stderr = run_ssh(ip, cmd, timeout=120)
    if code == 0:
        return f"✅ Successfully rolled back {label} {vmid} on {node} to snapshot '{snap_name}'.\n{stdout.strip()}"
    return f"❌ Rollback failed for {label} {vmid} on {node}:\n{stderr.strip()}\n{stdout.strip()}"

def delete_snapshot(node, vmid, snap_name):
    ip = get_node_ip(node)
    if not ip:
        return f"Error: Node {node} IP not found."

    tool = get_guest_tool(ip, vmid)
    label = "VM" if tool == "qm" else "LXC"

    cmd = f"{tool} delsnapshot {vmid} '{snap_name}'"
    print(f"🗑️ Deleting snapshot '{snap_name}' from {label} {vmid} on {node}...")
    code, stdout, stderr = run_ssh(ip, cmd, timeout=180)
    if code == 0:
        return f"✅ Successfully deleted snapshot '{snap_name}' from {label} {vmid} on {node}.\n{stdout.strip()}"
    return f"❌ Failed to delete snapshot '{snap_name}' from {label} {vmid} on {node}:\n{stderr.strip()}\n{stdout.strip()}"

def vzdump_backup(node, vmid, storage=None, mode="snapshot"):
    ip = get_node_ip(node)
    if not ip:
        return f"Error: Node {node} IP not found."

    cmd = f"vzdump {vmid} --mode {mode} --compress zstd"
    if storage:
        cmd += f" --storage '{storage}'"

    print(f"💾 Starting full vzdump backup for VM {vmid} on {node} (this may take a few minutes)...")
    code, stdout, stderr = run_ssh(ip, cmd, timeout=600)
    if code == 0:
        return f"✅ Full vzdump backup successfully completed for VM {vmid} on {node}.\n{stdout.strip()}"
    return f"❌ vzdump backup failed for VM {vmid} on {node}:\n{stderr.strip()}\n{stdout.strip()}"

def main():
    parser = argparse.ArgumentParser(description="Proxmox Hypervisor VM Snapshot & Backup Tool")
    parser.add_argument("--node", required=True, help="Node name (pve, pve2, pve3)")
    parser.add_argument("--vmid", type=int, required=True, help="Target VM ID")
    parser.add_argument("--action", required=True, choices=["create", "list", "rollback", "delete", "vzdump"], help="Snapshot action")
    parser.add_argument("--name", help="Snapshot name (required for create, rollback, delete)")
    parser.add_argument("--desc", default="", help="Description for snapshot")
    parser.add_argument("--include-ram", action="store_true", help="Include RAM in snapshot (--vmstate 1)")
    parser.add_argument("--storage", help="Target Proxmox storage for vzdump backup")
    args = parser.parse_args()

    if args.action in ["create", "rollback", "delete"] and not args.name:
        print(f"Error: --name is required for action '{args.action}'.")
        sys.exit(1)

    if args.action == "create":
        res = create_snapshot(args.node, args.vmid, args.name, description=args.desc, include_ram=args.include_ram)
    elif args.action == "list":
        res = list_snapshots(args.node, args.vmid)
    elif args.action == "rollback":
        res = rollback_snapshot(args.node, args.vmid, args.name)
    elif args.action == "delete":
        res = delete_snapshot(args.node, args.vmid, args.name)
    elif args.action == "vzdump":
        res = vzdump_backup(args.node, args.vmid, storage=args.storage)
    else:
        res = f"Invalid action {args.action}"

    print(res)

if __name__ == "__main__":
    main()
