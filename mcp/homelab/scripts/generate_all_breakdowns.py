#!/usr/bin/env python3
"""
Phase 1: Deep Container Breakdown Generator
Generates comprehensive Markdown breakdown reports for all VMs on pve, pve2, pve3.
"""

import subprocess
import json
import os

VMS = [
    {"node": "pve", "ip": "192.168.1.250", "vmid": 100, "name": "nexus-server"},
    {"node": "pve", "ip": "192.168.1.250", "vmid": 102, "name": "luna-server"},
    {"node": "pve", "ip": "192.168.1.250", "vmid": 103, "name": "media-server"},
    {"node": "pve", "ip": "192.168.1.250", "vmid": 107, "name": "vxlan-server"},
    {"node": "pve", "ip": "192.168.1.250", "vmid": 109, "name": "minecraft-docker"},
    {"node": "pve2", "ip": "192.168.1.240", "vmid": 100, "name": "discovery-server"},
    {"node": "pve3", "ip": "192.168.1.245", "vmid": 100, "name": "nexus-server2"},
    {"node": "pve3", "ip": "192.168.1.245", "vmid": 101, "name": "nas-server"},
]

def run_vm(ip, vmid, cmd):
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=5",
        f"root@{ip}",
        f"qm guest exec {vmid} -- bash -c \"{cmd}\""
    ]
    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            payload = json.loads(res.stdout)
            return payload.get("out-data", "")
    except Exception:
        pass
    return ""

def process_vm(vm):
    node = vm["node"]
    ip = vm["ip"]
    vmid = vm["vmid"]
    name = vm["name"]
    
    print(f"\n============================================================")
    print(f"📊 Generating Breakdown for VM {vmid} ({name}) on {node} ({ip})")
    print(f"============================================================")
    
    # 1. Containers list
    ps_raw = run_vm(ip, vmid, "docker ps -a --format 'table {{.Names}}\\\\t{{.Status}}\\\\t{{.Image}}\\\\t{{.Ports}}'")
    
    # 2. Networks list
    net_raw = run_vm(ip, vmid, "docker network ls")
    
    # 3. Running Container IPs via inspect
    inspect_raw = run_vm(ip, vmid, "docker inspect $(docker ps -q) 2>/dev/null || true")
    
    inspect_ips = {}
    if inspect_raw:
        try:
            inspect_json = json.loads(inspect_raw)
            for item in inspect_json:
                c_name = item.get("Name", "").lstrip("/")
                nets = item.get("NetworkSettings", {}).get("Networks", {})
                ips = [f"{info.get('IPAddress')} ({net_n})" for net_n, info in nets.items() if info.get('IPAddress')]
                inspect_ips[c_name] = ", ".join(ips) if ips else "Host / None"
        except Exception:
            pass
            
    out_file = f"nodes/{node}/vm-{vmid}-breakdown.md"
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    
    with open(out_file, "w") as f:
        f.write(f"# 🖥️ Detailed Container & Service Breakdown: `{name}` (`{node}` VM {vmid})\n\n")
        f.write(f"* **Host Proxmox Node**: `{node}` (`{ip}`)\n")
        f.write(f"* **Target Virtual Machine**: `VM {vmid}` (`{name}`)\n\n")
        f.write("--- \n\n")
        f.write("## 🐳 Docker Containers & Services Matrix\n\n")
        f.write("```text\n")
        f.write(ps_raw if ps_raw else "No containers found or Docker engine offline.\n")
        f.write("```\n\n")
        
        if inspect_ips:
            f.write("### 📌 Container Internal IP Assignments\n\n")
            f.write("| Container Name | Assigned IP Address & Network |\n")
            f.write("| :--- | :--- |\n")
            for c_name, ip_info in inspect_ips.items():
                f.write(f"| **`{c_name}`** | `{ip_info}` |\n")
            f.write("\n")
            
        f.write("--- \n\n")
        f.write("## 🌐 Docker Networks\n\n")
        f.write("```text\n")
        f.write(net_raw if net_raw else "No networks found.\n")
        f.write("```\n")
        
    print(f"  ✓ Saved report to {out_file}")

def main():
    for vm in VMS:
        process_vm(vm)

if __name__ == "__main__":
    main()
