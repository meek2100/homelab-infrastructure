#!/usr/bin/env python3

import os
import glob
import subprocess
import json
import argparse
import sys

def restore_vm_packages(target_node=None, target_vmid=None, dry_run=False):
    vm_dirs = glob.glob("infrastructure/vms/*")
    if target_node:
        vm_dirs = [d for d in vm_dirs if d.split('/')[-1].startswith(f"{target_node}-")]
    if target_vmid:
        vm_dirs = [d for d in vm_dirs if d.split('/')[-1].split('-')[1] == target_vmid]
        
    print(f"Found {len(vm_dirs)} VMs to process.")
    
    for vm_dir in vm_dirs:
        pkg_file = os.path.join(vm_dir, "configs", "apt-packages.txt")
        if not os.path.exists(pkg_file):
            continue
            
        with open(pkg_file, 'r') as f:
            target_pkgs = set(line.strip() for line in f if line.strip())
            
        vm_name = vm_dir.split('/')[-1]
        node_name = vm_name.split('-')[0]
        vmid = vm_name.split('-')[1]
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue
            
        print(f"\nChecking APT packages for VM {vmid} on {node_name}...")
        
        # Get current packages
        cmd_extract = f"ssh root@{host_ip} 'qm guest exec {vmid} -- sh -c \"dpkg-query -f \\'\\${{binary:Package}}\\n\\' -W > /tmp/current-apt.txt\"'"
        subprocess.run(cmd_extract, shell=True)
        
        cmd_fetch = f"ssh root@{host_ip} 'qm guest exec {vmid} -- cat /tmp/current-apt.txt'"
        res_fetch = subprocess.run(cmd_fetch, shell=True, capture_output=True, text=True)
        
        try:
            data = json.loads(res_fetch.stdout)
            current_pkgs = set(data.get("out-data", "").splitlines())
            
            missing_pkgs = target_pkgs - current_pkgs
            
            if not missing_pkgs:
                print("  ✓ All target packages are already installed.")
                continue
                
            missing_str = " ".join(missing_pkgs)
            if dry_run:
                print(f"  [DRY RUN] Would install {len(missing_pkgs)} missing packages: {missing_str[:100]}...")
            else:
                print(f"  Installing {len(missing_pkgs)} missing packages...")
                cmd_install = f"ssh root@{host_ip} 'qm guest exec {vmid} -- sh -c \"DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y {missing_str}\"'"
                res_install = subprocess.run(cmd_install, shell=True, capture_output=True, text=True)
                if res_install.returncode == 0:
                    print("  ✓ Successfully installed missing packages.")
                else:
                    print(f"  ❌ Failed to install packages: {res_install.stderr}")
        except json.JSONDecodeError:
            print(f"  ❌ Failed to parse output: {res_fetch.stdout}")

def restore_host_packages(target_node=None, dry_run=False):
    host_dirs = glob.glob("infrastructure/hosts/*")
    if target_node:
        host_dirs = [d for d in host_dirs if d.split('/')[-1] == target_node]
        
    print(f"\nFound {len(host_dirs)} Hosts to process.")
    
    for host_dir in host_dirs:
        pkg_file = os.path.join(host_dir, "configs", "apt-packages.txt")
        if not os.path.exists(pkg_file):
            continue
            
        with open(pkg_file, 'r') as f:
            target_pkgs = set(line.strip() for line in f if line.strip())
            
        node_name = host_dir.split('/')[-1]
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue
            
        print(f"\nChecking APT packages for Host {node_name}...")
        
        cmd = f"ssh root@{host_ip} 'dpkg-query -f \"\\${{binary:Package}}\\n\" -W'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if res.returncode == 0:
            current_pkgs = set(res.stdout.splitlines())
            missing_pkgs = target_pkgs - current_pkgs
            
            if not missing_pkgs:
                print("  ✓ All target packages are already installed.")
                continue
                
            missing_str = " ".join(missing_pkgs)
            if dry_run:
                print(f"  [DRY RUN] Would install {len(missing_pkgs)} missing packages: {missing_str[:100]}...")
            else:
                print(f"  Installing {len(missing_pkgs)} missing packages...")
                cmd_install = f"ssh root@{host_ip} 'DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y {missing_str}'"
                res_install = subprocess.run(cmd_install, shell=True, capture_output=True, text=True)
                if res_install.returncode == 0:
                    print("  ✓ Successfully installed missing packages.")
                else:
                    print(f"  ❌ Failed to install packages: {res_install.stderr}")
        else:
            print(f"  ❌ Failed to get current packages: {res.stderr}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", help="Specific node to restore", default=None)
    parser.add_argument("--vmid", help="Specific VM to restore", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Simulate restoration")
    args = parser.parse_args()
    
    if args.node and args.vmid:
        restore_vm_packages(args.node, args.vmid, args.dry_run)
    elif args.node:
        restore_host_packages(args.node, args.dry_run)
    else:
        restore_vm_packages(dry_run=args.dry_run)
        restore_host_packages(dry_run=args.dry_run)
