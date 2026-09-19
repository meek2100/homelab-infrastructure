#!/usr/bin/env python3

import os
import sys
import glob
import subprocess
import tarfile
import tempfile
import re
import json
import argparse

def restore_stacks(target_node=None, target_vmid=None, dry_run=False):
    
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    master_key = os.path.join(repo_root, "homelab-infrastructure.key")
    if not os.path.exists(master_key):
        master_key = os.path.join(repo_root, "master-age-key.txt")
    if not os.path.exists(master_key):
        print(f"Error: Master key not found at {master_key} or homelab-infrastructure.key")
        sys.exit(1)
        
    sops_env = os.environ.copy()
    sops_env["SOPS_AGE_KEY_FILE"] = master_key
    
    stack_dirs = glob.glob("infrastructure/docker-stacks/*/*")
    
    valid_stack_dirs = []
    for stack_dir in stack_dirs:
        if os.path.exists(os.path.join(stack_dir, "deploy.json")):
            valid_stack_dirs.append(stack_dir)
            
    print(f"Found {len(valid_stack_dirs)} Docker stacks to restore.\n")
    
    for stack_dir in valid_stack_dirs:
        with open(os.path.join(stack_dir, "deploy.json"), 'r') as f:
            deploy_info = json.load(f)
            
        node_name = deploy_info.get("node")
        vmid = deploy_info.get("vmid")
        
        if target_node and node_name != target_node:
            continue
        if target_vmid and vmid != target_vmid:
            continue
            
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue
            
        stack_id = os.path.basename(stack_dir)
        
        compose_path = os.path.join(stack_dir, "docker-compose.yml")
        secrets_path = os.path.join(stack_dir, "secrets.enc.yaml")
        
        if not os.path.exists(compose_path):
            continue
            
        print(f"Deploying Stack {stack_id} to VM {vmid} on {node_name}...")
        
        decrypted_env = ""
        if os.path.exists(secrets_path):
            try:
                res = subprocess.run(
                    ["sops", "-d", secrets_path],
                    env=sops_env,
                    capture_output=True,
                    text=True,
                    check=True
                )
                import yaml
                data = yaml.safe_load(res.stdout)
                for k, v in data.items():
                    decrypted_env += f"{k}={v}\n"
            except Exception as e:
                print(f"  ❌ Failed to decrypt secrets for stack {stack_id}: {e}")
                continue
                
        # Send files to the VM
        with open(compose_path, 'r') as f:
            compose_content = f.read()
            
        target_compose_dir = f"/var/lib/docker/volumes/portainer_data/_data/compose/{stack_id}"
        
        if dry_run:
            print(f"  [DRY RUN] Would create dir {target_compose_dir} on VM {vmid}")
            print(f"  [DRY RUN] Would write docker-compose.yml and stack.env")
            print(f"  [DRY RUN] Would run docker compose up -d")
            continue
            
        # 1. Create directory
        cmd_mkdir = f"ssh root@{host_ip} 'qm guest exec {vmid} -- mkdir -p {target_compose_dir}'"
        subprocess.run(cmd_mkdir, shell=True)
        
        # 2. Write docker-compose.yml
        cmd_write_compose = f"ssh root@{host_ip} 'qm guest exec {vmid} --pass-stdin 1 -- sh -c \"cat > {target_compose_dir}/docker-compose.yml\"'"
        subprocess.run(cmd_write_compose, shell=True, input=compose_content, text=True)
        
        # 3. Write stack.env if exists
        if decrypted_env:
            cmd_write_env = f"ssh root@{host_ip} 'qm guest exec {vmid} --pass-stdin 1 -- sh -c \"cat > {target_compose_dir}/stack.env\"'"
            subprocess.run(cmd_write_env, shell=True, input=decrypted_env, text=True)
            
        # 4. Spin up stack
        cmd_up = f"ssh root@{host_ip} 'qm guest exec {vmid} -- sh -c \"cd {target_compose_dir} && docker compose --env-file stack.env up -d\"'"
        if not decrypted_env:
            cmd_up = f"ssh root@{host_ip} 'qm guest exec {vmid} -- sh -c \"cd {target_compose_dir} && docker compose up -d\"'"
            
        res = subprocess.run(cmd_up, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  ✓ Stack {stack_id} deployed successfully.")
        else:
            print(f"  ❌ Error deploying Stack {stack_id}:\n{res.stderr}")
            
    print("\n✅ Docker stack deployment complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore Docker stacks")
    parser.add_argument("--node", help="Specific node to restore", default=None)
    parser.add_argument("--vmid", help="Specific VM to restore", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Simulate restoration without changes")
    args = parser.parse_args()
    
    if args.dry_run:
        print(f"Starting DRY RUN stack restoration...")
        restore_stacks(args.node, args.vmid, dry_run=True)
    elif args.node or args.vmid:
        print(f"Starting stack restoration for specific parameters...")
        restore_stacks(args.node, args.vmid)
    else:
        confirm = input("WARNING: This will automatically decrypt secrets and spin up Docker containers on the VMs! Proceed? (y/N): ")
        if confirm.lower() == 'y':
            restore_stacks()
        else:
            print("Aborted.")
