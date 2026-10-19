#!/usr/bin/env python3
"""
Wireshark Live Packet Sniffer & Storage Status Tool
Queries luna-server (VM 102 on pve) via QEMU Guest Agent to inspect ens19
SPAN mirror packet counters, active Wireshark container state, and capture archives.
"""

import argparse
import base64
import json
import os
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def get_ssh_key():
    for candidate in [
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/dtheurer/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519",
        os.path.expanduser("~/.ssh/pi_id_ed25519"),
        "/home/dtheurer/.ssh/pi_id_ed25519",
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh(host_ip, cmd, user="root", timeout=30):
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    ]
    if key: ssh_args.extend(["-i", key])
    ssh_args.extend([f"{user}@{host_ip}", cmd])
    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)

def get_wireshark_status(node_ip="192.168.1.250", vmid=102):
    # Remote script on pve executing inside VM 102 via QGA
    script = """import subprocess, json

def qm_exec(cmd):
    res = subprocess.run(["qm", "guest", "exec", \"""" + str(vmid) + """\", "--", "sh", "-c", cmd], capture_output=True, text=True)
    if res.returncode == 0:
        try:
            data = json.loads(res.stdout)
            return data.get("out-data", "")
        except Exception:
            return res.stdout
    return ""

print("=== 1. ens19 SPAN Capture Interface Status ===")
print(qm_exec("ip -s link show ens19 2>/dev/null || echo ens19 not found"))

print("=== 2. Wireshark Docker Container State ===")
print(qm_exec("docker ps -a --filter name=wireshark 2>/dev/null || docker ps"))

print("=== 3. Recent PCAP Capture Files on NAS ===")
print(qm_exec("docker exec wireshark ls -lh /nas-storage/ 2>/dev/null | tail -n 10 || echo 'No captures found'"))

print("=== 4. Active In-Flight Chunks in tmpfs /captures ===")
print(qm_exec("docker exec wireshark ls -lh /captures/ 2>/dev/null || echo 'No active tmpfs captures'"))

print("=== 5. In-Flight & Recent Capture Analysis ===")
latest_pcap = qm_exec("ls -t /mnt/media/wireshark-captures/*.pcapng 2>/dev/null | head -1").strip()
if latest_pcap:
    print(f"Analyzing {latest_pcap}...")
    print("--- Top ARP Requests (Rate & Targets) ---")
    print(qm_exec("head -c 15M " + latest_pcap + " | tcpdump -c 200 -nn -e -r - 'arp' 2>/dev/null | awk '{print $NF}' | sort | uniq -c | sort -nr | head -n 6"))
    print("--- STP Topology / Spanning Tree Activity ---")
    print(qm_exec("head -c 15M " + latest_pcap + " | tcpdump -c 20 -nn -r - 'stp' 2>/dev/null | head -n 4"))
    print("--- ICMP Traffic (Ping Probes & Gateways) ---")
    print(qm_exec("head -c 15M " + latest_pcap + " | tcpdump -c 100 -nn -r - 'icmp' 2>/dev/null | awk '{print $3, $4, $5}' | sort | uniq -c | sort -nr | head -n 6"))
"""

    b64_payload = base64.b64encode(script.encode("utf-8")).decode("ascii")


    remote_cmd = f"echo '{b64_payload}' | base64 -d | python3"

    code, out, err = run_ssh(node_ip, remote_cmd)
    if code != 0:
        return f"❌ Error querying Wireshark status on {node_ip} (VM {vmid}): {err.strip()}"
    return out.strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query live Wireshark sniffer status.")
    parser.add_argument("--node-ip", default="192.168.1.250", help="Proxmox host IP running VM 102")
    parser.add_argument("--vmid", type=int, default=102, help="VM ID of luna-server")
    args = parser.parse_args()
    print(get_wireshark_status(node_ip=args.node_ip, vmid=args.vmid))

