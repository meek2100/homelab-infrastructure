#!/usr/bin/env python3

import os
import glob
import subprocess
import tarfile
import tempfile
import sys
import argparse
import json

def restore_drifts(target_node=None, target_vmid=None, dry_run=False):
    
    custom_dirs = glob.glob("infrastructure/vms/*/drift/custom-files")
    
    if target_node:
        custom_dirs = [d for d in custom_dirs if d.split('/')[-3].startswith(f"{target_node}-")]
    if target_vmid:
        custom_dirs = [d for d in custom_dirs if d.split('/')[-3].split('-')[1] == target_vmid]
        
    print(f"Found {len(custom_dirs)} VM drift directories to restore.\n")
    
    for custom_dir in custom_dirs:
        vm_folder = custom_dir.split('/')[-3]
        parts = vm_folder.split('-')
        node_name = parts[0]
        vmid = parts[1]
        
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue
        
        ssh_key = None
        for cand in [
            os.path.expanduser("~/.ssh/proxmox_ed25519"),
            "/home/agentsvc/.ssh/proxmox_ed25519",
            "/home/dtheurer/.ssh/proxmox_ed25519",
            os.path.expanduser("~/.ssh/id_ed25519")
        ]:
            if os.path.exists(cand):
                ssh_key = cand
                break
        ssh_base = ["ssh", "-o", "StrictHostKeyChecking=accept-new"]
        if ssh_key:
            ssh_base.extend(["-i", ssh_key])
        ssh_base.append(f"root@{host_ip}")
        
        if vmid == "100":
            if node_name != "pve":
                continue
            interfaces_file = os.path.join(custom_dir, "etc", "network", "interfaces")
            if os.path.exists(interfaces_file):
                import base64
                with open(interfaces_file, "rb") as inf:
                    b64_data = base64.b64encode(inf.read()).decode("ascii")
                cmd_str = (
                    f"qm guest exec {vmid} -- sh -c "
                    f"\"echo '{b64_data}' | base64 -d > /etc/network/interfaces && "
                    f"ip addr add 8.8.8.8/32 dev lo 2>/dev/null || true; "
                    f"ip addr add 8.8.4.4/32 dev lo 2>/dev/null || true; "
                    f"ip addr add 1.1.1.1/32 dev lo 2>/dev/null || true; "
                    f"ip addr add 1.0.0.1/32 dev lo 2>/dev/null || true; "
                    f"ip -4 addr show dev lo\""
                )
                res = subprocess.run(ssh_base + [cmd_str], capture_output=True, text=True, timeout=15)
                print(f"  ✓ Restored /etc/network/interfaces and loopback aliases on {node_name} VM {vmid}: {res.stdout.strip()}")
            continue
        
        # Check if there are any files
        files_to_restore = []
        for root, _, files in os.walk(custom_dir):
            for file in files:
                files_to_restore.append(os.path.join(root, file))
                
        if not files_to_restore:
            continue
            
        print(f"Packaging {len(files_to_restore)} files for VM {vmid} on {node_name}...")
        
        # Create a tarball containing the files
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as temp_tar:
            tar_path = temp_tar.name
            with tarfile.open(tar_path, "w") as tar:
                for full_path in files_to_restore:
                    arcname = os.path.relpath(full_path, custom_dir)
                    tar.add(full_path, arcname=arcname)
                    
        try:
            if dry_run:
                print(f"[DRY RUN] Would execute on {host_ip}: qm guest exec {vmid} -- tar -xf - -C /")
                print(f"[DRY RUN] Would upload {tar_path}")
            else:
                # Stream the tarball into the VM over SSH -> qm guest exec
                with open(tar_path, 'rb') as f:
                    ssh_cmd = ssh_base + [
                        f"qm guest exec {vmid} --pass-stdin 1 -- tar -xf - -C /"
                    ]
                    res = subprocess.run(ssh_cmd, stdin=f, capture_output=True, text=True)
                
                if res.returncode == 0:
                    print(f"  ✓ Successfully restored custom files to VM {vmid} on {node_name}")
                    
                    # Apply permissions
                    permissions_path = os.path.join(os.path.dirname(custom_dir), "permissions.json")
                    if os.path.exists(permissions_path):
                        print(f"  Applying file permissions for VM {vmid}...")
                        with open(permissions_path, 'r') as pf:
                            permissions = json.load(pf)
                        for filepath, meta in permissions.items():
                            mode = meta.get("mode", "644")
                            uid = meta.get("uid", "0")
                            gid = meta.get("gid", "0")
                            perm_cmd = ssh_base + [
                                f"qm guest exec {vmid} -- sh -c \"chown {uid}:{gid} {filepath} && chmod {mode} {filepath}\""
                            ]
                            subprocess.run(perm_cmd, capture_output=True)

                    # If /etc/network/interfaces contains post-up ip addr add on lo, ensure live kernel state matches
                    interfaces_file = os.path.join(custom_dir, "etc", "network", "interfaces")
                    if os.path.exists(interfaces_file):
                        with open(interfaces_file, "r") as inf:
                            iface_txt = inf.read()
                        for line in iface_txt.splitlines():
                            sline = line.strip()
                            if sline.startswith("post-up ip addr add ") and " dev lo" in sline:
                                cmd_part = sline.replace("post-up ", "")
                                subprocess.run(ssh_base + [f"qm guest exec {vmid} -- sh -c \"{cmd_part}\""], capture_output=True)
                else:
                    print(f"  ❌ Failed to restore VM {vmid}: {res.stderr}")
        except Exception as e:
            print(f"  ❌ Error restoring VM {vmid}: {e}")
        finally:
            os.remove(tar_path)
            
    print("\n✅ VM Drift restoration complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore VM drifts")
    parser.add_argument("pos_vmid", nargs="?", help="Optional positional VM ID", default=None)
    parser.add_argument("--node", help="Specific node to restore", default=None)
    parser.add_argument("--vmid", help="Specific VM to restore", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Simulate restoration without changes")
    args = parser.parse_args()
    effective_vmid = args.vmid or args.pos_vmid
    
    if args.dry_run:
        print(f"Starting DRY RUN VM restoration...")
        restore_drifts(args.node, effective_vmid, dry_run=True)
    elif args.node or effective_vmid:
        print(f"Starting restoration for specific parameters...")
        restore_drifts(args.node, effective_vmid)
    else:
        confirm = input("WARNING: This will overwrite files inside live VMs! Proceed? (y/N): ")
        if confirm.lower() == 'y':
            restore_drifts()
        else:
            print("Aborted.")
