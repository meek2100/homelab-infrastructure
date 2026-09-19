#!/usr/bin/env python3

import os
import glob
import subprocess
import sys
import argparse
import json

def extract_vm_packages(target_node=None, target_vmid=None):
    vm_dirs = glob.glob("infrastructure/vms/*")
    
    if target_node:
        vm_dirs = [d for d in vm_dirs if d.split('/')[-1].startswith(f"{target_node}-")]
    if target_vmid:
        vm_dirs = [d for d in vm_dirs if d.split('/')[-1].split('-')[1] == target_vmid]
        
    print(f"Found {len(vm_dirs)} VMs to process.")
    
    for vm_dir in vm_dirs:
        vm_name = vm_dir.split('/')[-1]
        parts = vm_name.split('-')
        node_name = parts[0]
        vmid = parts[1]
        
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue
            
        print(f"\nExtracting APT packages for VM {vmid} on {node_name}...")
        
        config_dir = os.path.join(vm_dir, "configs")
        os.makedirs(config_dir, exist_ok=True)
        
        cmd = f"ssh root@{host_ip} 'qm guest exec {vmid} -- dpkg-query -f \\'${{binary:Package}}\\n\\' -W'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if res.returncode == 0 and res.stdout.strip():
            # The output of qm guest exec might have JSON wrapper if not carefully done, 
            # wait, `qm guest exec` without wrapper might just return stdout if we parse it,
            # but usually it returns JSON if not using a pipe or something.
            # Actually, in Phase 1 we did `qm guest exec ... -- sh -c "dpkg-query ..."`.
            # If `res.stdout` contains JSON, we need to extract "out-data".
            # To avoid JSON parsing, we can just pipe it inside the ssh command.
            pass
            
        # Use a list to avoid shell quoting hell
        cmd_extract = [
            "ssh", f"root@{host_ip}",
            f"qm guest exec {vmid} -- sh -c 'dpkg-query -f \"\\${{binary:Package}}\n\" -W > /tmp/apt-packages.txt'"
        ]
        subprocess.run(cmd_extract)
        
        cmd_fetch = [
            "ssh", f"root@{host_ip}",
            f"qm guest exec {vmid} -- cat /tmp/apt-packages.txt"
        ]
        res_fetch = subprocess.run(cmd_fetch, capture_output=True, text=True)
        
        # We know qm guest exec can still output JSON if we just use `cat`.
        # Wait, if we use `ssh root@host "qm guest exec 100 -- cat /etc/issue"`, it prints JSON:
        # {"exitcode": 0, "out-data": "Ubuntu..."}
        # We should parse JSON!
        import json
        try:
            data = json.loads(res_fetch.stdout)
            packages = data.get("out-data", "")
            if packages:
                with open(os.path.join(config_dir, "apt-packages.txt"), "w") as f:
                    f.write(packages)
                print(f"  ✓ Saved {len(packages.splitlines())} packages.")
        except json.JSONDecodeError:
            print(f"  ❌ Failed to parse output: {res_fetch.stdout}")

def extract_host_packages(target_node=None):
    host_dirs = glob.glob("infrastructure/hosts/*")
    
    if target_node:
        host_dirs = [d for d in host_dirs if d.split('/')[-1] == target_node]
        
    print(f"\nFound {len(host_dirs)} Hosts to process.")
    
    for host_dir in host_dirs:
        node_name = host_dir.split('/')[-1]
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue
            
        print(f"\nExtracting APT packages for Host {node_name}...")
        
        config_dir = os.path.join(host_dir, "configs")
        os.makedirs(config_dir, exist_ok=True)
        
        cmd = f"ssh root@{host_ip} 'dpkg-query -f \"\\${{binary:Package}}\\n\" -W'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if res.returncode == 0 and res.stdout.strip():
            with open(os.path.join(config_dir, "apt-packages.txt"), "w") as f:
                f.write(res.stdout)
            print(f"  ✓ Saved {len(res.stdout.splitlines())} packages.")
        else:
            print(f"  ❌ Failed: {res.stderr}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", help="Specific node to extract", default=None)
    parser.add_argument("--vmid", help="Specific VM to extract", default=None)
    args = parser.parse_args()
    
    if args.node and args.vmid:
        extract_vm_packages(args.node, args.vmid)
    elif args.node:
        extract_host_packages(args.node)
    else:
        extract_vm_packages()
        extract_host_packages()
