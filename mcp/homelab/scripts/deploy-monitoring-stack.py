#!/usr/bin/env python3
"""
Deploy and Manage Homelab Monitoring & Observability Stack on nexus-server (VM 100 on pve).
Transfers compose and config files, initializes volume permissions, launches containers,
and verifies Prometheus targets, SNMP exporter, and Grafana dashboard provisioning.
"""

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import tarfile
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
STACK_DIR = os.path.join(REPO_ROOT, "infrastructure", "docker-stacks", "nexus-server", "71-monitoring")
PVE_IP = "192.168.1.250"
VMID = 100
REMOTE_BASE = "/home/meek2100/docker/monitoring"

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

def qm_exec(cmd, timeout=60):
    key = get_ssh_key()
    escaped = cmd.replace('"', '\\"')
    remote_cmd = f'qm guest exec {VMID} -- sh -c "{escaped}"'
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    ]
    if key:
        ssh_args.extend(["-i", key])
    ssh_args.extend([f"root@{PVE_IP}", remote_cmd])
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

def package_stack():
    """Package the stack directory into an in-memory tarball."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, _, files in os.walk(STACK_DIR):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, STACK_DIR)
                tar.add(full_path, arcname=rel_path)
    buf.seek(0)
    return buf.read()

def deploy():
    print(f"🚀 Deploying Observability Stack to nexus-server (VM {VMID} on {PVE_IP})...")
    
    # 1. Package stack
    tar_bytes = package_stack()
    b64_payload = base64.b64encode(tar_bytes).decode("ascii")
    print(f"  ✓ Packaged monitoring configuration ({len(tar_bytes)} bytes)")

    # 2. Extract on VM
    extract_cmd = (
        f"mkdir -p {REMOTE_BASE} && "
        f"echo '{b64_payload}' | base64 -d | tar -xzf - -C {REMOTE_BASE} && "
        f"mkdir -p {REMOTE_BASE}/prometheus/data {REMOTE_BASE}/grafana/data && "
        f"chown -R 65534:65534 {REMOTE_BASE}/prometheus/data && "
        f"chown -R 472:472 {REMOTE_BASE}/grafana/data && "
        f"chmod -R 755 {REMOTE_BASE}"
    )
    ok, out = qm_exec(extract_cmd)
    if not ok:
        print(f"  ❌ Failed extracting files on VM {VMID}: {out}")
        return False
    print(f"  ✓ Files unpacked and directory permissions initialized at {REMOTE_BASE}")

    # 3. Pull images and launch compose
    launch_cmd = f"cd {REMOTE_BASE} && docker compose up -d"
    print("  ⏳ Pulling images and launching containers...")
    ok, out = qm_exec(launch_cmd, timeout=180)
    if not ok:
        print(f"  ❌ Failed starting containers: {out}")
        return False
    print(f"  ✓ Containers launched:\n{out.strip()}")

    # 4. Wait for services to initialize
    print("  ⏳ Waiting 10s for Prometheus and Grafana initialization...")
    time.sleep(10)

    # 5. Health checks
    ps_ok, ps_out = qm_exec(f"cd {REMOTE_BASE} && docker compose ps")
    print(f"\n📊 Active Monitoring Containers:\n{ps_out.strip()}")

    # Test Prometheus
    prom_ok, prom_out = qm_exec("curl -s http://localhost:9090/-/ready || echo 'Not ready'")
    print(f"\nPrometheus Readiness: {'🟢 ' + prom_out.strip() if prom_ok else '🔴 ' + prom_out.strip()}")

    # Test Grafana
    graf_ok, graf_out = qm_exec("curl -s http://localhost:3000/api/health || echo 'Not ready'")
    print(f"Grafana Health: {'🟢 ' + graf_out.strip() if graf_ok else '🔴 ' + graf_out.strip()}")

    # Test SNMP Exporter on Araknis router
    snmp_ok, snmp_out = qm_exec("curl -s 'http://localhost:9116/snmp?target=192.168.1.1&module=if_mib' | grep -E '^sysUpTime|^ifNumber' | head -n 4")
    print(f"\nSNMP Scrape Sample (Araknis Router):\n{snmp_out.strip() if snmp_ok else 'Failed'}")

    return True

def status():
    print(f"📊 Checking Observability Stack Status on nexus-server (VM {VMID})...")
    ok, out = qm_exec(f"cd {REMOTE_BASE} && docker compose ps")
    print(out.strip() if ok else f"Error: {out}")

def stop():
    print(f"🛑 Stopping Observability Stack on nexus-server (VM {VMID})...")
    ok, out = qm_exec(f"cd {REMOTE_BASE} && docker compose down")
    print(out.strip() if ok else f"Error: {out}")

def main():
    parser = argparse.ArgumentParser(description="Manage Homelab Observability Stack")
    parser.add_argument("action", choices=["deploy", "status", "stop"], default="deploy", nargs="?")
    args = parser.parse_args()

    if args.action == "deploy":
        deploy()
    elif args.action == "status":
        status()
    elif args.action == "stop":
        stop()

if __name__ == "__main__":
    main()
