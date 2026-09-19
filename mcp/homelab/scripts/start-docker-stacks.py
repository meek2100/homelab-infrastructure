#!/usr/bin/env python3
import os
import glob
import subprocess
import argparse
import json

def start_docker_stacks(target_node=None, target_vmid=None, dry_run=False):
    vm_dirs = glob.glob("infrastructure/vms/*")
    if target_node:
        vm_dirs = [d for d in vm_dirs if d.split('/')[-1].startswith(f"{target_node}-")]
    if target_vmid:
        vm_dirs = [d for d in vm_dirs if d.split('/')[-1].split('-')[1] == target_vmid]
        
    for vm_dir in vm_dirs:
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

        print(f"\n============================================================")
        print(f"🚀 Starting Docker Stacks: VM {vmid} on {node_name}")
        print(f"============================================================")
        
        # We find all compose directories on the VM and run docker compose up -d
        find_cmd = f"ssh -o StrictHostKeyChecking=accept-new root@{host_ip} 'qm guest exec {vmid} -- sh -c \"find /var/lib/docker/volumes/portainer_data/_data/compose -name docker-compose.yml -o -name docker-compose.yaml\"'"
        res = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
        
        try:
            data = json.loads(res.stdout)
            compose_files = data.get("out-data", "").splitlines()
            if not compose_files:
                print("  No compose files found on this VM.")
                continue
                
            for compose_file in compose_files:
                compose_dir = os.path.dirname(compose_file)
                if dry_run:
                    print(f"  [DRY RUN] Would start stack at {compose_dir}")
                else:
                    print(f"  Starting stack at {compose_dir}...")
                    up_cmd = f"ssh -o StrictHostKeyChecking=accept-new root@{host_ip} 'qm guest exec {vmid} -- sh -c \"cd {compose_dir} && docker compose up -d\"'"
                    subprocess.run(up_cmd, shell=True)
        except Exception as e:
            print(f"  ❌ Failed to discover stacks or qemu-guest-agent not running: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", help="Specific node", default=None)
    parser.add_argument("--vmid", help="Specific VM", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Simulate ignition")
    args = parser.parse_args()
    
    start_docker_stacks(args.node, args.vmid, args.dry_run)
