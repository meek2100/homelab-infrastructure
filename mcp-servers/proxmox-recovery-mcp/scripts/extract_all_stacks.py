#!/usr/bin/env python3
"""
Phase 1: Deep Portainer Stack Extractor
Finds and extracts the highest versioned docker-compose.yml and stack.env for every stack across all VMs.
"""

import subprocess
import json
import sys
import os
import re

VMS_TO_AUDIT = [
    {"node": "pve", "ip": "192.168.1.250", "vms": [100, 102, 103, 107, 109]},
    {"node": "pve2", "ip": "192.168.1.240", "vms": [100]},
    {"node": "pve3", "ip": "192.168.1.245", "vms": [100, 101]}
]

def run_ssh_vm(host_ip, vmid, cmd):
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=5",
        f"root@{host_ip}",
        f"qm guest exec {vmid} -- {cmd}"
    ]
    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            payload = json.loads(res.stdout)
            return payload.get("out-data", "")
    except Exception as e:
        pass
    return ""

def process_vm_stacks(node_name, host_ip, vmid):
    print(f"\n🔍 Audit Stacks: VM {vmid} on Node {node_name} ({host_ip})")
    
    # Find all docker-compose.yml paths
    find_cmd = "find /var/lib/docker/volumes/portainer_data/_data/compose/ -name docker-compose.yml"
    output = run_ssh_vm(host_ip, vmid, find_cmd)
    
    if not output:
        print(f"  - No Portainer volume or stacks found.")
        return
        
    lines = [line.strip() for line in output.split("\n") if line.strip().endswith("docker-compose.yml")]
    
    # Group by stack_id -> latest version
    stacks = {}
    pattern = re.compile(r"/compose/(\d+)/(?:(v\d+)/)?docker-compose\.yml")
    
    for line in lines:
        match = pattern.search(line)
        if match:
            stack_id = match.group(1)
            version_str = match.group(2) or "v1"
            ver_num = int(version_str.lstrip("v")) if version_str.startswith("v") else 1
            
            if stack_id not in stacks or ver_num > stacks[stack_id]["ver_num"]:
                stacks[stack_id] = {
                    "ver_num": ver_num,
                    "ver_str": version_str,
                    "yml_path": line,
                    "env_path": line.replace("docker-compose.yml", "stack.env")
                }
                
    print(f"  ✓ Found {len(stacks)} unique Portainer stacks. Reading latest versions...")
    
    out_file = f"nodes/{node_name}/portainer-stacks-vm{vmid}.log"
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    
    with open(out_file, "w") as f:
        f.write(f"# Empirical Portainer Stacks Backup: Node {node_name} | VM {vmid}\n")
        f.write(f"# Total Unique Stacks Discovered: {len(stacks)}\n\n")
        
        for stack_id, info in sorted(stacks.items(), key=lambda x: int(x[0])):
            yml_path = info["yml_path"]
            env_path = info["env_path"]
            ver_str = info["ver_str"]
            
            f.write(f"============================================================\n")
            f.write(f"📦 Stack ID: {stack_id} | Version: {ver_str} | Path: {yml_path}\n")
            f.write(f"============================================================\n\n")
            
            yml_content = run_ssh_vm(host_ip, vmid, f"cat {yml_path}")
            if yml_content:
                f.write("--- docker-compose.yml ---\n")
                f.write(yml_content)
                f.write("\n\n")
                
            env_content = run_ssh_vm(host_ip, vmid, f"cat {env_path}")
            if env_content:
                f.write("--- stack.env ---\n")
                f.write(env_content)
                f.write("\n\n")
                
            print(f"    - Extracted Stack {stack_id} ({ver_str})")
            
    print(f"  ✅ Saved stack backup to {out_file}")

def main():
    for target in VMS_TO_AUDIT:
        for vmid in target["vms"]:
            process_vm_stacks(target["node"], target["ip"], vmid)

if __name__ == "__main__":
    main()
