#!/usr/bin/env python3
import os
import glob
import subprocess
import argparse
import json

def restore_host_configs(target_node=None, dry_run=False):
    host_dirs = glob.glob("infrastructure/hosts/*")
    if target_node:
        host_dirs = [d for d in host_dirs if d.split('/')[-1] == target_node]
        
    for host_dir in host_dirs:
        node_name = host_dir.split('/')[-1]
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue

        print(f"\n============================================================")
        print(f"📥 Restoring Host Configs: {node_name} ({host_ip})")
        print(f"============================================================")
        
        config_dir = os.path.join(host_dir, "configs")
        if not os.path.exists(config_dir):
            print(f"  No configs directory found for {node_name}. Skipping.")
            continue
            
        # File Mappings: local_file -> remote_path
        file_mappings = {
            "interfaces": "/etc/network/interfaces",
            "grub": "/etc/default/grub",
            "modules": "/etc/modules",
            "storage.cfg": "/etc/pve/storage.cfg",
            "logind.conf": "/etc/systemd/logind.conf",
            "cron/crontab": "/etc/crontab",
        }
        
        for local_name, remote_path in file_mappings.items():
            local_path = os.path.join(config_dir, local_name)
            if os.path.exists(local_path):
                if dry_run:
                    print(f"  [DRY RUN] Would copy {local_path} -> {remote_path}")
                else:
                    print(f"  Copying {local_name} -> {remote_path}")
                    cmd = f"cat {local_path} | ssh -o StrictHostKeyChecking=accept-new root@{host_ip} 'cat > {remote_path}'"
                    subprocess.run(cmd, shell=True)

        # Directory Mappings: local_dir -> remote_parent_dir
        # We tar up the local_dir contents and extract them into remote_parent_dir
        dir_mappings = {
            "qemu-server": "/etc/pve/qemu-server",
            "lxc": "/etc/pve/lxc",
            "acpi": "/etc/acpi",
            "etc/modprobe.d": "/etc/modprobe.d",
            "custom-configs/etc": "/etc",
            "custom-configs/root": "/root",
            "custom-scripts": "/usr/local/bin" # Approximate fallback for scripts
        }

        for local_name, remote_path in dir_mappings.items():
            local_path = os.path.join(config_dir, local_name)
            if os.path.exists(local_path) and os.path.isdir(local_path):
                if dry_run:
                    print(f"  [DRY RUN] Would sync {local_path}/* -> {remote_path}/")
                else:
                    print(f"  Syncing {local_name}/* -> {remote_path}/")
                    cmd = f"ssh -o StrictHostKeyChecking=accept-new root@{host_ip} 'mkdir -p {remote_path}' && tar -czf - -C {local_path} . | ssh root@{host_ip} 'tar -xzf - -C {remote_path}'"
                    subprocess.run(cmd, shell=True)

        # Special handling for cron because of stripped components in extract script
        cron_dir = os.path.join(config_dir, "cron")
        if os.path.exists(cron_dir) and os.path.isdir(cron_dir):
            if dry_run:
                print(f"  [DRY RUN] Would restore cron configurations")
            else:
                print(f"  Restoring cron configurations")
                # e2scrub_all, vzdump, etc. go to /etc/cron.d
                cmd = f"ssh -o StrictHostKeyChecking=accept-new root@{host_ip} 'mkdir -p /etc/cron.d' && find {cron_dir} -maxdepth 1 -type f -not -name crontab -exec cat {{}} \\; | ssh root@{host_ip} 'cat > /etc/cron.d/restored_crons'"
                subprocess.run(cmd, shell=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", help="Specific node to restore", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Simulate restoration")
    args = parser.parse_args()
    
    restore_host_configs(args.node, args.dry_run)
