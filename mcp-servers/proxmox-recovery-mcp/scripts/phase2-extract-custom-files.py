#!/usr/bin/env python3

import os
import glob
import subprocess
import re
import sys
import json
import base64

def extract_vm_files(target_node=None, target_vmid=None):
    manifests = glob.glob("infrastructure/vms/*/drift/unowned-user-files.txt")
    if target_node:
        manifests = [m for m in manifests if m.split('/')[-3].startswith(f"{target_node}-")]
    if target_vmid:
        manifests = [m for m in manifests if m.split('/')[-3].split('-')[1] == target_vmid]
        
    print(f"Found {len(manifests)} VM drift manifests to process.")
    
    for m in manifests:
        vm_folder = m.split('/')[-3]
        node_name = vm_folder.split('-')[0]
        vmid = vm_folder.split('-')[1]
        
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue
            
        print(f"\nProcessing VM {vmid} on node {node_name}...")
        custom_dir = os.path.join(os.path.dirname(m), "custom-files")
        os.makedirs(custom_dir, exist_ok=True)
        
        with open(m, 'r') as f:
            files = [line.strip() for line in f if line.strip()]
            
        modified_manifest = os.path.join(os.path.dirname(m), "modified-config-files.txt")
        if os.path.exists(modified_manifest):
            with open(modified_manifest, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('/'):
                        files.append(line)
                        
        files = list(set(files))
            
        permissions = {}
        
        for filepath in files:
            print(f"  Fetching: {filepath}")
            os.makedirs(os.path.dirname(os.path.join(custom_dir, filepath.lstrip('/'))), exist_ok=True)
            # Fetch file content and metadata in one command
            cmd = f"ssh -o StrictHostKeyChecking=accept-new root@{host_ip} 'qm guest exec {vmid} -- sh -c \"base64 -w 0 {filepath} && echo \\\"|STAT|\\\" && stat -c \\\"%a:%u:%g\\\" {filepath}\"'"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            try:
                data = json.loads(res.stdout)
                if data.get("exitcode") == 0:
                    out_str = data.get("out-data", "")
                    if "|STAT|\n" in out_str:
                        b64_str, stat_str = out_str.split("|STAT|\n", 1)
                        stat_str = stat_str.strip()
                        raw_bytes = base64.b64decode(b64_str.strip())
                        with open(f"{custom_dir}{filepath}", 'wb') as out_f:
                            out_f.write(raw_bytes)
                        # Parse stat e.g. "644:0:0"
                        if ":" in stat_str:
                            mode, uid, gid = stat_str.split(":")
                            permissions[filepath] = {"mode": mode, "uid": uid, "gid": gid}
                    else:
                        print(f"    Failed to parse stat delimiter for {filepath}")
                else:
                    print(f"    Failed to extract {filepath}: exitcode {data.get('exitcode')}")
            except Exception as e:
                print(f"    Error parsing output for {filepath}: {e}")
                
        # Write permissions to drift folder
        if permissions:
            with open(os.path.join(os.path.dirname(m), "permissions.json"), 'w') as pf:
                json.dump(permissions, pf, indent=2)

def extract_host_files(target_node=None):
    host_manifests = glob.glob("infrastructure/hosts/*/drift/unowned-user-files.txt")
    if target_node:
        host_manifests = [m for m in host_manifests if m.split('/')[-3] == target_node]
        
    print(f"\nFound {len(host_manifests)} Host drift manifests to process.")
    
    for m in host_manifests:
        node_name = m.split('/')[-3]
        host_ip = None
        meta_path = f"infrastructure/hosts/{node_name}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as mf:
                host_ip = json.load(mf).get("ip")
        if not host_ip:
            continue
            
        print(f"\nProcessing Host {node_name}...")
        custom_dir = os.path.join(os.path.dirname(m), "custom-files")
        os.makedirs(custom_dir, exist_ok=True)
        
        with open(m, 'r') as f:
            files = [line.strip() for line in f if line.strip()]
            
        modified_manifest = os.path.join(os.path.dirname(m), "modified-config-files.txt")
        if os.path.exists(modified_manifest):
            with open(modified_manifest, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('/'):
                        files.append(line)
                        
        files = list(set(files))
            
        permissions = {}
        
        for filepath in files:
            print(f"  Fetching: {filepath}")
            os.makedirs(os.path.dirname(os.path.join(custom_dir, filepath.lstrip('/'))), exist_ok=True)
            cmd = f"ssh -o StrictHostKeyChecking=accept-new root@{host_ip} 'sh -c \"base64 -w 0 {filepath} && echo \\\"|STAT|\\\" && stat -c \\\"%a:%u:%g\\\" {filepath}\"'"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                out_str = res.stdout
                if "|STAT|\n" in out_str:
                    b64_str, stat_str = out_str.split("|STAT|\n", 1)
                    stat_str = stat_str.strip()
                    try:
                        raw_bytes = base64.b64decode(b64_str.strip())
                        with open(f"{custom_dir}{filepath}", 'wb') as out_f:
                            out_f.write(raw_bytes)
                        if ":" in stat_str:
                            mode, uid, gid = stat_str.split(":")
                            permissions[filepath] = {"mode": mode, "uid": uid, "gid": gid}
                    except Exception as e:
                        print(f"    Error parsing {filepath}: {e}")
            else:
                print(f"    Failed to extract {filepath}")
                
        # Write permissions to drift folder
        if permissions:
            with open(os.path.join(os.path.dirname(m), "permissions.json"), 'w') as pf:
                json.dump(permissions, pf, indent=2)

if __name__ == "__main__":
    node_arg = sys.argv[1] if len(sys.argv) > 1 else None
    vmid_arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    if node_arg and vmid_arg:
        extract_vm_files(node_arg, vmid_arg)
    elif node_arg:
        extract_host_files(node_arg)
    else:
        extract_vm_files()
        extract_host_files()
