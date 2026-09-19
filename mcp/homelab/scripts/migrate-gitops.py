#!/usr/bin/env python3

import os
import shutil
import json
import glob

def main():
    # Mapping based on the user's matrix
    vm_names = {
        "pve-100": "nexus-server",
        "pve-102": "luna-server",
        "pve-103": "media-server",
        "pve-107": "vxlan-server",
        "pve-109": "minecraft-docker",
        "pve2-100": "discovery-server",
        "pve3-100": "nexus-server2",
        "pve3-101": "nas-server"
    }

    # Create root directories
    os.makedirs("infrastructure/hosts", exist_ok=True)
    os.makedirs("infrastructure/vms", exist_ok=True)
    os.makedirs("apps", exist_ok=True)

    print("Migrating Hosts...")
    # 1. Migrate Hosts
    for node in ["pve", "pve2", "pve3"]:
        node_dir = f"nodes/{node}"
        if not os.path.exists(node_dir):
            continue
            
        host_target = f"infrastructure/hosts/{node}"
        os.makedirs(host_target, exist_ok=True)
        
        # Move host-configs
        if os.path.exists(f"{node_dir}/host-configs"):
            shutil.move(f"{node_dir}/host-configs", f"{host_target}/configs")
            print(f"  Moved {node} configs")
            
        # Move system-drift
        if os.path.exists(f"{node_dir}/system-drift"):
            shutil.move(f"{node_dir}/system-drift", f"{host_target}/drift")
            print(f"  Moved {node} drift")

    print("\nMigrating VMs...")
    # 2. Migrate VMs
    for node in ["pve", "pve2", "pve3"]:
        node_dir = f"nodes/{node}"
        if not os.path.exists(node_dir):
            continue
            
        for vm_drift in glob.glob(f"{node_dir}/vm-*-drift"):
            vmid = vm_drift.split('/')[-1].split('-')[1]
            key = f"{node}-{vmid}"
            name = vm_names.get(key, f"vm-{vmid}")
            
            target_vm_dir = f"infrastructure/vms/{node}-{vmid}-{name}"
            os.makedirs(target_vm_dir, exist_ok=True)
            
            shutil.move(vm_drift, f"{target_vm_dir}/drift")
            print(f"  Moved VM {vmid} drift to {target_vm_dir}/drift")

    print("\nMigrating Apps (Docker Stacks)...")
    # 3. Migrate Stacks
    for node in ["pve", "pve2", "pve3"]:
        node_dir = f"nodes/{node}"
        if not os.path.exists(node_dir):
            continue
            
        for vm_stacks in glob.glob(f"{node_dir}/vm-*-stacks"):
            vmid = vm_stacks.split('/')[-1].split('-')[1]
            key = f"{node}-{vmid}"
            name = vm_names.get(key, f"vm-{vmid}")
            
            app_group_dir = f"infrastructure/docker-stacks/{name}"
            os.makedirs(app_group_dir, exist_ok=True)
            
            for stack_dir in glob.glob(f"{vm_stacks}/stack-*"):
                stack_name = stack_dir.split('/')[-1].replace("stack-", "")
                target_stack_dir = f"{app_group_dir}/{stack_name}"
                
                shutil.move(stack_dir, target_stack_dir)
                
                # Write deploy.json
                deploy_info = {
                    "node": node,
                    "vmid": vmid
                }
                with open(f"{target_stack_dir}/deploy.json", "w") as f:
                    json.dump(deploy_info, f, indent=2)
                    
                print(f"  Moved {stack_name} to {target_stack_dir}")

    # 4. Clean up any other files in nodes (like deep-audit logs)
    # Let's move the deep-audit logs and breakdown MDs to infrastructure/vms/
    print("\nMigrating audit logs...")
    for node in ["pve", "pve2", "pve3"]:
        node_dir = f"nodes/{node}"
        if not os.path.exists(node_dir):
            continue
            
        for file in glob.glob(f"{node_dir}/vm-*"):
            if "breakdown.md" in file or "audit.log" in file:
                vmid = file.split('/')[-1].split('-')[1]
                key = f"{node}-{vmid}"
                name = vm_names.get(key, f"vm-{vmid}")
                target_vm_dir = f"infrastructure/vms/{node}-{vmid}-{name}"
                os.makedirs(target_vm_dir, exist_ok=True)
                shutil.move(file, target_vm_dir)
                
        # Move host audit logs
        if os.path.exists(f"{node_dir}/audit-{node}.log"):
            shutil.move(f"{node_dir}/audit-{node}.log", f"infrastructure/hosts/{node}/audit.log")

    print("\nDeleting legacy nodes/ directory...")
    if os.path.exists("nodes"):
        shutil.rmtree("nodes")
        
    print("Migration complete!")

if __name__ == "__main__":
    main()
