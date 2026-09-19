#!/usr/bin/env python3
"""
Phase 1: Deep Container & Stack Breakdown Tool
Queries Docker Engine via QEMU Guest Agent inside all VMs to generate full, detailed breakdowns for:
- VM 100 (nexus-server) on pve
- VM 102 (luna-server) on pve
- VM 103 (media-server) on pve
- VM 109 (minecraft-docker) on pve
- VM 100 (discovery-server) on pve2
- VM 100 (nexus-server2) on pve3
"""

import subprocess
import json
import sys
import os

VMS = [
    {"node": "pve", "ip": "192.168.1.250", "vmid": 100, "name": "nexus-server"},
    {"node": "pve", "ip": "192.168.1.250", "vmid": 102, "name": "luna-server"},
    {"node": "pve", "ip": "192.168.1.250", "vmid": 103, "name": "media-server"},
    {"node": "pve", "ip": "192.168.1.250", "vmid": 109, "name": "minecraft-docker"},
    {"node": "pve2", "ip": "192.168.1.240", "vmid": 100, "name": "discovery-server"},
    {"node": "pve3", "ip": "192.168.1.245", "vmid": 100, "name": "nexus-server2"},
]

CONTAINER_INSPECT_CMD = """python3 -c "
import subprocess, json

def run(cmd):
    try: return subprocess.check_output(cmd, shell=True, text=True)
    except: return ''

ps_out = run('docker ps -a --format json')
containers = []
if ps_out:
    for line in ps_out.strip().split('\\n'):
        if line:
            try: containers.append(json.loads(line))
            except: pass

networks_out = run('docker network ls --format json')
networks = []
if networks_out:
    for line in networks_out.strip().split('\\n'):
        if line:
            try: networks.append(json.loads(line))
            except: pass

inspect_out = run('docker inspect ' + ' '.join([c.get('ID','') for c in containers if c.get('ID')]))
inspect_data = []
if inspect_out:
    try: inspect_data = json.loads(inspect_out)
    except: pass

print(json.dumps({'containers': containers, 'networks': networks, 'inspect': inspect_data}))
" """

def query_vm_docker(ip, vmid):
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=5",
        f"root@{ip}",
        f"qm guest exec {vmid} -- {CONTAINER_INSPECT_CMD.replace(chr(10), ' ')}"
    ]
    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=20)
        if res.returncode == 0:
            payload = json.loads(res.stdout)
            out_data = payload.get("out-data", "")
            if out_data:
                return json.loads(out_data)
    except Exception as e:
        print(f"Error querying VM {vmid} on {ip}: {e}", file=sys.stderr)
    return {}

def generate_vm_report(vm_target):
    node = vm_target["node"]
    ip = vm_target["ip"]
    vmid = vm_target["vmid"]
    name = vm_target["name"]
    
    print(f"\n============================================================")
    print(f"🖥️ Generating Deep Breakdown: {name} (VM {vmid} on {node} - {ip})")
    print(f"============================================================")
    
    data = query_vm_docker(ip, vmid)
    if not data:
        print(f"⚠️ Could not retrieve Docker details for VM {vmid}")
        return
        
    containers = data.get("containers", [])
    networks = data.get("networks", [])
    inspect_list = data.get("inspect", [])
    
    print(f"✓ Found {len(containers)} total containers and {len(networks)} networks.")
    
    report_file = f"nodes/{node}/vm-{vmid}-detailed-breakdown.md"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, "w") as f:
        f.write(f"# 🖥️ Detailed Container & Stack Breakdown: `{name}` (`{node}` VM {vmid})\n\n")
        f.write(f"* **Host Machine**: `{node}` (`{ip}`)\n")
        f.write(f"* **Target VM**: `VM {vmid}` (`{name}`)\n")
        f.write(f"* **Total Containers**: {len(containers)}\n\n")
        
        f.write("--- \n\n")
        f.write("## 🐳 Docker Containers Inventory\n\n")
        f.write("| Container Name | Status | Image | Stack / Compose Project | Internal IP | Published Ports |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        running_count = 0
        for c in inspect_list:
            c_name = c.get("Name", "").lstrip("/")
            state = c.get("State", {}).get("Status", "unknown")
            if state == "running": running_count += 1
            image = c.get("Config", {}).get("Image", "")
            
            labels = c.get("Config", {}).get("Labels") or {}
            stack = labels.get("com.docker.compose.project") or labels.get("com.portainer.stack.name") or "Unstacked / Standalone"
            
            # Network IPs
            net_settings = c.get("NetworkSettings", {}).get("Networks", {})
            ips = []
            for n_name, n_info in net_settings.items():
                ip_addr = n_info.get("IPAddress")
                if ip_addr: ips.append(f"{ip_addr} ({n_name})")
            ip_str = ", ".join(ips) if ips else "Host / None"
            
            # Ports
            ports_dict = c.get("NetworkSettings", {}).get("Ports", {}) or {}
            port_list = []
            for container_p, host_bindings in ports_dict.items():
                if host_bindings:
                    for b in host_bindings:
                        port_list.append(f"{b.get('HostPort')}:{container_p}")
                else:
                    port_list.append(container_p)
            ports_str = ", ".join(port_list) if port_list else "-"
            
            f.write(f"| **`{c_name}`** | `{state}` | `{image}` | `{stack}` | `{ip_str}` | `{ports_str}` |\n")
            
        f.write(f"\n* **Active Running Containers**: {running_count} / {len(containers)}\n\n")
        
        f.write("--- \n\n")
        f.write("## 🌐 Docker Networks\n\n")
        f.write("| Network Name | Driver | Scope | Subnet / Gateway |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for net in networks:
            net_name = net.get("Name", "")
            driver = net.get("Driver", "")
            scope = net.get("Scope", "")
            f.write(f"| **`{net_name}`** | `{driver}` | `{scope}` | - |\n")
            
    print(f"✅ Report written to {report_file}")

def main():
    for vm in VMS:
        generate_vm_report(vm)

if __name__ == "__main__":
    main()
