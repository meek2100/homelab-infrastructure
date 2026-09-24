#!/usr/bin/env python3
"""
Phase 1: Full Network & Storage Subnet Topology Discovery Tool
Deeply inspects network bridges, interfaces, IP bindings, and routes across:
- Host pve (192.168.1.250)
- Host pve2 (192.168.1.240 & 10.25.25.240)
- Host pve3 (192.168.1.245 & 10.25.25.245)
- VM 101 nas-server on pve3 (OMV NAS on 10.25.25.x / 192.168.1.x)
- VM 100 discovery-server on pve2 (VPN & 10.25.25.x storage network)
- All other VMs
"""

import subprocess
import json
import os

NODES = [
    {"node": "pve", "ip": "192.168.1.250"},
    {"node": "pve2", "ip": "192.168.1.240"},
    {"node": "pve3", "ip": "192.168.1.245"},
]

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

def run_ssh(ip, cmd):
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=5",
        f"root@{ip}", cmd
    ]
    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
        return res.stdout.strip()
    except Exception:
        return ""

def run_vm_cmd(node_ip, vmid, cmd):
    qemu_cmd = f"qm guest exec {vmid} -- bash -c \"{cmd}\""
    out_raw = run_ssh(node_ip, qemu_cmd)
    if out_raw:
        try:
            payload = json.loads(out_raw)
            return payload.get("out-data", "")
        except Exception:
            pass
    return ""

def main():
    print("============================================================")
    print("🌐 Auditing Full Network Topology & Subnets (192.168.1.0/24 & 10.25.25.0/24)")
    print("============================================================")

    topology_report = []
    topology_report.append("# 🌐 Comprehensive Network Topology & Subnet Map\n")
    topology_report.append("This document outlines all physical host bridges, VLANs, static IP assignments, and private storage networks across `pve`, `pve2`, `pve3`, and all virtual machines.\n")

    topology_report.append("--- \n\n")
    topology_report.append("## 🛜 Subnet Breakdown\n\n")
    topology_report.append("1. **Primary Management & Service LAN (`192.168.1.0/24`)**:\n")
    topology_report.append("   - Primary home network subnet used for Proxmox GUI management, DNS (`AdGuard`), WireGuard, Cloudflare Tunnel, Web applications, and default VM egress.\n")
    topology_report.append("2. **Private High-Speed NAS Storage LAN (`10.25.25.0/24`)**:\n")
    topology_report.append("   - Isolated, dedicated storage network linking `pve3` (`nas-server` OpenMediaVault), `pve2` (`discovery-server`), and storage clients for direct NFS/SMB/iSCSI backup and download traffic without saturating the primary management LAN.\n")
    topology_report.append("3. **VLAN 40 (`Smart Home / IoT`) & VLAN 50 (`Isolated Security`)**:\n")
    topology_report.append("   - Virtual local area networks defined on `pve2` (`vmbr0.40` & `vmbr0.50`) and passed to `luna-server` via `macvlan`.\n\n")

    topology_report.append("--- \n\n")
    topology_report.append("## 🖥️ Physical Proxmox Host Network Interfaces & Routing Table\n\n")

    for node in NODES:
        n_name = node["node"]
        ip = node["ip"]
        print(f"--> Auditing Host {n_name} ({ip})...")
        
        if_raw = run_ssh(ip, "ip -4 addr show")
        route_raw = run_ssh(ip, "ip route")
        
        topology_report.append(f"### Proxmox Host: `{n_name}` (`{ip}`)\n\n")
        topology_report.append("#### Network Interfaces & IPs\n```text\n")
        topology_report.append(if_raw if if_raw else "Could not retrieve interfaces.\n")
        topology_report.append("```\n\n")
        
        topology_report.append("#### Routing Table\n```text\n")
        topology_report.append(route_raw if route_raw else "Could not retrieve routes.\n")
        topology_report.append("```\n\n")

    topology_report.append("--- \n\n")
    topology_report.append("## 📦 Virtual Machines Network Interfaces & Routing Table\n\n")

    for vm in VMS:
        n_name = vm["node"]
        n_ip = vm["ip"]
        vmid = vm["vmid"]
        vname = vm["name"]
        print(f"--> Auditing VM {vmid} ({vname}) on {n_name}...")
        
        vm_if = run_vm_cmd(n_ip, vmid, "ip -4 addr show")
        vm_route = run_vm_cmd(n_ip, vmid, "ip route")
        
        topology_report.append(f"### Virtual Machine: `{vname}` (`{n_name}` VM {vmid})\n\n")
        topology_report.append("#### Interfaces & IPs\n```text\n")
        topology_report.append(vm_if if vm_if else "Could not retrieve VM interfaces.\n")
        topology_report.append("```\n\n")
        
        topology_report.append("#### Routing Table\n```text\n")
        topology_report.append(vm_route if vm_route else "Could not retrieve VM routes.\n")
        topology_report.append("```\n\n")

    out_path = "docs/architecture/network-interfaces-map.md"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(topology_report))

    print(f"✅ Full Network Topology & Subnet Map saved to {out_path}")

if __name__ == "__main__":
    main()
