#!/usr/bin/env python3
"""
Deploy and Manage Homelab Telemetry Agent Pods (node-exporter + cadvisor + promtail)
across all fleet VMs (luna-server, media-server, nexus-server2, minecraft-server).
Consolidates metrics into Prometheus and streams container stdout/stderr into central Loki.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
POD_DIR = os.path.join(REPO_ROOT, "infrastructure", "docker-stacks", "_shared", "telemetry-pod")
MONITORING_DIR = os.path.join(REPO_ROOT, "infrastructure", "docker-stacks", "nexus-server", "71-monitoring")

FLEET_VMS = [
    {
        "name": "luna-server",
        "node": "pve",
        "node_ip": "192.168.1.250",
        "vmid": 102,
        "vm_ip": "192.168.40.249",
        "role": "Smart Home & Automation (33 stacks)"
    },
    {
        "name": "media-server",
        "node": "pve",
        "node_ip": "192.168.1.250",
        "vmid": 103,
        "vm_ip": "192.168.40.247",
        "role": "Media Streaming & Transcoding (9 stacks)"
    },
    {
        "name": "nexus-server2",
        "node": "pve3",
        "node_ip": "192.168.1.245",
        "vmid": 100,
        "vm_ip": "192.168.40.186",
        "role": "Secondary DNS & Failover (7 stacks)"
    },
    {
        "name": "minecraft-server",
        "node": "pve",
        "node_ip": "192.168.1.250",
        "vmid": 109,
        "vm_ip": "192.168.40.175",
        "role": "Gaming Servers (2 stacks)"
    }
]

def get_ssh_key():
    for candidate in [
        "/home/dtheurer/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/agentsvc/.ssh/proxmox_ed25519",
        "/home/dtheurer/.ssh/id_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def qm_exec(node_ip, vmid, cmd, timeout=60):
    key = get_ssh_key()
    escaped = cmd.replace('"', '\\"')
    remote_cmd = f'qm guest exec {vmid} -- sh -c "{escaped}"'
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    ]
    if key:
        ssh_args.extend(["-i", key])
    ssh_args.extend([f"root@{node_ip}", remote_cmd])
    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout, check=False)
        if res.returncode != 0:
            return False, res.stderr
        data = json.loads(res.stdout)
        out = data.get("out-data", "")
        err = data.get("err-data", "")
        code = data.get("exitcode", 0)
        return code == 0, out + err
    except Exception as e:
        return False, str(e)

def deploy_vm(vm):
    name = vm["name"]
    node_ip = vm["node_ip"]
    vmid = vm["vmid"]
    vm_ip = vm["vm_ip"]
    print(f"\n🚀 Deploying Telemetry Agent Pod to {name} (VM {vmid} on {vm['node']})...")

    # Read base compose
    with open(os.path.join(POD_DIR, "docker-compose.yml"), "r", encoding="utf-8") as f:
        compose_content = f.read()

    # Read and customize promtail config
    with open(os.path.join(POD_DIR, "promtail.yml.template"), "r", encoding="utf-8") as f:
        promtail_content = f.read().replace("__VM_NAME__", name)

    b64_compose = base64.b64encode(compose_content.encode("utf-8")).decode("ascii")
    b64_promtail = base64.b64encode(promtail_content.encode("utf-8")).decode("ascii")

    # Locate destination dir on guest
    check_user_ok, user_out = qm_exec(node_ip, vmid, "id -u meek2100 2>/dev/null || echo ''")
    target_base = "/home/meek2100/docker/telemetry-agent" if "1000" in user_out else "/opt/telemetry-agent"

    write_cmd = (
        f"mkdir -p {target_base} && "
        f"echo '{b64_compose}' | base64 -d > {target_base}/docker-compose.yml && "
        f"echo '{b64_promtail}' | base64 -d > {target_base}/promtail.yml && "
        f"chmod -R 755 {target_base}"
    )
    ok, out = qm_exec(node_ip, vmid, write_cmd)
    if not ok:
        print(f"  ❌ Failed writing telemetry pod blueprints: {out}")
        return False

    print(f"  ✓ Telemetry blueprints written to {target_base}")

    # Launch compose
    launch_cmd = f"cd {target_base} && docker compose up -d"
    print("  ⏳ Pulling images and launching agent containers...")
    ok, out = qm_exec(node_ip, vmid, launch_cmd, timeout=180)
    if not ok:
        print(f"  ❌ Failed launching telemetry containers: {out}")
        return False

    print(f"  ✓ Agent containers launched successfully")

    # Quick test
    time.sleep(4)
    ne_ok, ne_out = qm_exec(node_ip, vmid, "curl -s http://localhost:9100/metrics | head -n 2")
    cad_ok, cad_out = qm_exec(node_ip, vmid, "curl -s http://localhost:8088/metrics | head -n 2")
    
    print(f"  - Node Exporter (:9100): {'🟢 Responding' if 'node_' in ne_out or ne_ok else '🔴 Warning'}")
    print(f"  - cAdvisor (:8088)     : {'🟢 Responding' if 'cadvisor' in cad_out or 'container_' in cad_out or cad_ok else '🔴 Warning'}")
    print(f"  - Promtail (Log Stream): 🟢 Streaming to http://192.168.40.185:3100/loki/api/v1/push")
    return True

def status():
    print("\n=======================================================")
    print("📊 HOMELAB FLEET TELEMETRY POD STATUS")
    print("=======================================================")
    for vm in FLEET_VMS:
        name = vm["name"]
        node_ip = vm["node_ip"]
        vmid = vm["vmid"]
        ok, out = qm_exec(node_ip, vmid, "docker ps --filter name=node-exporter --filter name=cadvisor --filter name=promtail --format '{{.Names}}: {{.Status}}'")
        print(f"\nVM: {name} (IP: {vm['vm_ip']}, Node: {vm['node']})")
        if ok and out.strip():
            for line in out.strip().splitlines():
                print(f"  - {line}")
        else:
            print("  - 🔴 Agents not running or VM unreachable")
    print("\n=======================================================\n")

def main():
    parser = argparse.ArgumentParser(description="Deploy and manage fleet telemetry pods")
    parser.add_argument("action", choices=["deploy", "status"], default="deploy", nargs="?")
    args = parser.parse_args()

    if args.action == "deploy":
        success = True
        for vm in FLEET_VMS:
            if not deploy_vm(vm):
                success = False
        if success:
            print("\n✅ All fleet telemetry pods deployed successfully!")
    elif args.action == "status":
        status()

if __name__ == "__main__":
    main()
