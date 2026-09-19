#!/usr/bin/env python3

import os
import glob
import re

def process_log_file(log_path):
    print(f"Processing {log_path}...")
    
    # Example filename: nodes/pve/portainer-stacks-vm102.log
    filename = os.path.basename(log_path)
    match = re.match(r'portainer-stacks-vm(\d+)\.log', filename)
    if not match:
        return
    
    vmid = match.group(1)
    node_dir = os.path.dirname(log_path)
    
    out_dir = os.path.join(node_dir, f"vm-{vmid}-stacks")
    os.makedirs(out_dir, exist_ok=True)
    
    with open(log_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Split by the stack header
    # ============================================================
    # 📦 Stack ID: 46 | Version: v1 | Path: ...
    # ============================================================
    
    # We will use regex to find all stack blocks
    stack_blocks = re.split(r'={60}\n📦 Stack ID: (\d+) \| Version: ([^\|]+) \| Path: [^\n]+\n={60}\n', content)
    
    # stack_blocks[0] is the prefix before the first stack
    for i in range(1, len(stack_blocks), 3):
        stack_id = stack_blocks[i]
        version = stack_blocks[i+1].strip()
        block_content = stack_blocks[i+2]
        
        stack_dir = os.path.join(out_dir, f"stack-{stack_id}")
        os.makedirs(stack_dir, exist_ok=True)
        
        # Split block_content into docker-compose.yml and stack.env
        dc_match = re.search(r'--- docker-compose\.yml ---\n(.*?)(?=\n--- stack\.env ---|\Z)', block_content, re.DOTALL)
        env_match = re.search(r'--- stack\.env ---\n(.*?)(?=\Z)', block_content, re.DOTALL)
        
        if dc_match:
            dc_content = dc_match.group(1).strip()
            with open(os.path.join(stack_dir, "docker-compose.yml"), 'w') as dc_file:
                dc_file.write(dc_content + "\n")
                
        if env_match:
            env_content = env_match.group(1).strip()
            if env_content:
                with open(os.path.join(stack_dir, "stack.env"), 'w') as env_file:
                    env_file.write(env_content + "\n")
                    
        print(f"  ✓ Extracted Stack {stack_id} to {stack_dir}")
        
    print(f"✅ Finished parsing {filename}\n")
    
    # Optionally remove or rename the log file to avoid keeping plaintext around
    os.remove(log_path)
    print(f"🗑️ Deleted original {filename}")

if __name__ == "__main__":
    log_files = glob.glob("nodes/*/portainer-stacks-vm*.log")
    for log_file in log_files:
        process_log_file(log_file)
