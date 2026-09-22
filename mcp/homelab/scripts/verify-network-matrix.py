#!/usr/bin/env python3
"""
Homelab Network Matrix Verification Tool
Tests ICMP ping and TCP socket reachability across all VLAN targets,
hypervisors, core switches, routers, DNS, and WireGuard.
"""

import argparse
import socket
import subprocess
import time

TARGETS = [
    # Proxmox Hypervisors (VLAN 1)
    {"name": "pve (Precision 5520)", "ip": "192.168.1.250", "tcp": [22, 8006], "category": "Hypervisor"},
    {"name": "pve2 (AK34Pro Mini PC)", "ip": "192.168.1.240", "tcp": [22, 8006], "category": "Hypervisor"},
    {"name": "pve3 (HP EliteDesk)", "ip": "192.168.1.245", "tcp": [22, 8006], "category": "Hypervisor"},

    # Core Network Hardware (VLAN 1)
    {"name": "Araknis 520 Core Router", "ip": "192.168.1.1", "tcp": [80, 443], "category": "Network Infrastructure"},
    {"name": "Araknis 920 Switch", "ip": "192.168.1.215", "tcp": [80, 443], "category": "Network Infrastructure"},
    {"name": "Araknis 830 AP 1 (Master)", "ip": "192.168.1.231", "tcp": [80, 443], "category": "Wireless Infrastructure"},
    {"name": "Araknis 830 AP 2 (Core)", "ip": "192.168.1.236", "tcp": [80, 443], "category": "Wireless Infrastructure"},
    {"name": "Araknis 830 AP 3 (Bridge)", "ip": "192.168.1.237", "tcp": [80, 443], "category": "Wireless Infrastructure"},
    {"name": "Netgear Office Switch", "ip": "192.168.1.220", "tcp": [80], "category": "Network Infrastructure"},

    # Office & WAN2 Routers
    {"name": "OpenWrt Belkin AX3200", "ip": "192.168.1.226", "tcp": [22], "category": "Edge Router"},
    {"name": "DD-WRT Aurora (WAN2 / SAN)", "ip": "10.25.25.1", "tcp": [22], "category": "Edge Router"},

    # Core DNS & Admin Services (VLAN 40)
    {"name": "AdGuard Home Primary (nexus)", "ip": "192.168.40.185", "tcp": [53, 80, 443], "category": "Core Admin Service"},
    {"name": "AdGuard Home Secondary (nexus2)", "ip": "192.168.40.186", "tcp": [53], "category": "Core Admin Service"},
    {"name": "luna-server (Smart Home VM 102)", "ip": "192.168.40.249", "tcp": [22, 8123, 8581], "category": "Smart Home Admin"},
    {"name": "media-server (Plex VM 103)", "ip": "192.168.40.247", "tcp": [22, 32400], "category": "Media Admin"},
    {"name": "minecraft-docker (VM 109)", "ip": "192.168.40.175", "tcp": [22], "category": "Gaming VM"},
    {"name": "OpenMediaVault Admin (VM 101)", "ip": "192.168.40.248", "tcp": [80, 443], "category": "Storage Admin"},

    # Private Storage Network & Automation Controller
    {"name": "OpenMediaVault Data (SAN)", "ip": "10.25.25.248", "tcp": [445], "category": "Private Storage Network"},
    {"name": "discovery-server (SAN)", "ip": "10.25.25.246", "tcp": [22], "category": "Private Storage Network"},
    {"name": "Control4 Core Controller (core5)", "ip": "192.168.10.200", "tcp": [80, 443], "category": "Automation Controller"},
]

def ping_host(ip, timeout=1):
    try:
        start = time.time()
        res = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            capture_output=True, text=True, check=False
        )
        latency = (time.time() - start) * 1000
        return res.returncode == 0, latency
    except Exception:
        return False, 0.0

def test_tcp_port(ip, port, timeout=1.5):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        s.close()
        return True
    except Exception:
        return False

def verify_network_matrix(profile="all"):
    results = []
    header = "| Target Device | IP Address | Category | ICMP Ping | TCP Ports Tested | Status |\n| :--- | :--- | :--- | :---: | :--- | :---: |"
    results.append(header)

    for item in TARGETS:
        is_alive, latency = ping_host(item["ip"])
        ping_str = f"🟢 {latency:.1f}ms" if is_alive else "🔴 Offline"

        tcp_status = []
        for port in item.get("tcp", []):
            open_port = test_tcp_port(item["ip"], port)
            icon = "🟢" if open_port else "🔴"
            tcp_status.append(f"{icon} :{port}")

        tcp_str = ", ".join(tcp_status) if tcp_status else "—"
        overall = "🟢 PASS" if (is_alive or any("🟢" in s for s in tcp_status)) else "🔴 FAIL"
        results.append(f"| **{item['name']}** | `{item['ip']}` | {item['category']} | {ping_str} | {tcp_str} | {overall} |")

    return "\n".join(results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Homelab Network Matrix.")
    parser.add_argument("--profile", default="all", help="Test profile")
    args = parser.parse_args()
    print(verify_network_matrix(profile=args.profile))
