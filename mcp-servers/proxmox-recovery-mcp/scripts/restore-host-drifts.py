#!/usr/bin/env python3

import os
import glob
import subprocess
import tarfile
import sys
import argparse
import json
import tempfile

def restore_host_drifts(target_node=None, dry_run=False):
    
    custom_dirs = glob.glob("infrastructure/hosts/*/drift/custom-files")
    
    if target_node:
        custom_dirs = [d for d in custom_dirs if d.split('/')[-3] == target_node]
        
    print(f"Found {len(custom_dirs)} host drift directories to restore.\n")
    
    for custom_dir in custom_dirs:
        node_name = custom_dir.split('/')[-3]
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        
        if not host_ip:
            continue
            
        # Check if there are any files
        files_to_restore = []
        for root, _, files in os.walk(custom_dir):
            for file in files:
                files_to_restore.append(os.path.join(root, file))
                
        if not files_to_restore:
            print(f"--- Skipping host {node_name} (No custom files) ---")
            continue
            
        print(f"--- Restoring {len(files_to_restore)} files to host {node_name} ---")
        
        # Create a temporary tar archive of the custom files
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp_tar:
            tar_path = tmp_tar.name
            
        with tarfile.open(tar_path, "w") as tar:
            for root, _, files in os.walk(custom_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, custom_dir)
                    tar.add(full_path, arcname=arcname)
                    
        # Stream the tarball into the Host over SSH
        try:
            if dry_run:
                print(f"[DRY RUN] Would execute on {host_ip}: tar -xf - -C /")
                print(f"[DRY RUN] Would upload {tar_path}")
            else:
                # Transfer the tarball to the Proxmox host and extract it directly into /
                with open(tar_path, 'rb') as f:
                    ssh_cmd = [
                        "ssh", "-o", "StrictHostKeyChecking=accept-new", f"root@{host_ip}",
                        "tar -xf - -C /"
                    ]
                    res = subprocess.run(ssh_cmd, stdin=f, capture_output=True, text=True)
                
                if res.returncode == 0:
                    print(f"  ✓ Successfully restored custom files to {node_name}")
                    
                    # Apply permissions
                    permissions_path = os.path.join(os.path.dirname(custom_dir), "permissions.json")
                    if os.path.exists(permissions_path):
                        print(f"  Applying file permissions for host {node_name}...")
                        with open(permissions_path, 'r') as pf:
                            permissions = json.load(pf)
                        for filepath, meta in permissions.items():
                            mode = meta.get("mode", "644")
                            uid = meta.get("uid", "0")
                            gid = meta.get("gid", "0")
                            perm_cmd = [
                                "ssh", "-o", "StrictHostKeyChecking=accept-new", f"root@{host_ip}",
                                f"chown {uid}:{gid} {filepath} && chmod {mode} {filepath}"
                            ]
                            subprocess.run(perm_cmd, capture_output=True)
                else:
                    print(f"  ❌ Failed to restore {node_name}: {res.stderr}")
        except Exception as e:
            print(f"  ❌ Error restoring {node_name}: {e}")
        finally:
            os.remove(tar_path)
            
    print("\n✅ Host Drift restoration complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore host drifts")
    parser.add_argument("--node", help="Specific node to restore", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Simulate restoration without changes")
    args = parser.parse_args()
    
    if args.dry_run:
        print("Starting DRY RUN host restoration...")
        restore_host_drifts(args.node, dry_run=True)
    elif args.node:
        print(f"Starting restoration for specific host: {args.node}")
        restore_host_drifts(args.node)
    else:
        confirm = input("WARNING: This will overwrite files directly on all live Proxmox hosts! Proceed? (y/N): ")
        if confirm.lower() == 'y':
            restore_host_drifts()
        else:
            print("Aborted.")
