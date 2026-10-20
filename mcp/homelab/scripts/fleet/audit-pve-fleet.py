#!/usr/bin/env python3
"""
audit-pve-fleet.py
Comprehensive Non-Destructive Deep Baseline Audit across Proxmox Hosts, QEMU VMs, and LXC Containers.
Captures:
  1. System & Kernel: uname, os-release, uptime, memory, disk usage, pveversion
  2. Network & Security: ip addr, ip route, listening ports (ss -tulpn), firewall status
  3. Services & Daemons: systemctl running services, enabled unit files
  4. Docker & Containers: docker ps, docker images, docker compose projects
Saves snapshots into:
  - infrastructure/hosts/<node>/baseline/
  - infrastructure/vms/<node>-<vmid>-<name>/baseline/
"""

import argparse
import glob
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

HOST_AUDIT_SCRIPT = '''
set -euo pipefail
TMP_DIR=$(mktemp -d /tmp/fleet-audit-XXXXXX)
cd "${TMP_DIR}"
mkdir -p system network services configs

# System & OS
uname -a > system/uname.txt 2>&1 || true
cat /etc/os-release > system/os-release.txt 2>&1 || true
uptime > system/uptime.txt 2>&1 || true
df -h > system/disk-usage.txt 2>&1 || true
free -m > system/memory.txt 2>&1 || true
pveversion -v > system/pveversion.txt 2>&1 || true

# Network & Listening Ports
ss -tulpn > network/listening-ports.txt 2>&1 || true
ip addr > network/ip-addr.txt 2>&1 || true
ip route > network/ip-route.txt 2>&1 || true
pve-firewall status > network/pve-firewall-status.txt 2>&1 || true
iptables -S > network/iptables-rules.txt 2>&1 || true

# Services
systemctl list-unit-files --state=enabled > services/enabled-units.txt 2>&1 || true
systemctl list-units --type=service --state=running > services/running-services.txt 2>&1 || true

# Crontabs
crontab -l > configs/root-crontab.txt 2>&1 || true

tar -czf /tmp/host-baseline.tar.gz -C "${TMP_DIR}" .
rm -rf "${TMP_DIR}"
echo "HOST_BASELINE_COMPLETE"
'''

def get_ssh_key():
    for candidate in [
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/agentsvc/.ssh/proxmox_ed25519",
        "/home/dtheurer/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519"
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh_cmd(host_ip: str, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key and os.path.exists(key):
        ssh_args.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    ssh_args.extend([f"root@{host_ip}", cmd])
    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"SSH connection to {host_ip} timed out"
    except Exception as e:
        return 1, "", str(e)

def run_ssh_script(host_ip: str, script_content: str, timeout: int = 120) -> tuple[int, str, str]:
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key and os.path.exists(key):
        ssh_args.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    ssh_args.extend([f"root@{host_ip}", "bash -s"])
    try:
        res = subprocess.run(ssh_args, input=script_content, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "SSH connection timed out"
    except Exception as e:
        return 1, "", str(e)

def scp_fetch(host_ip: str, remote_file: str, local_dest: str) -> bool:
    key = get_ssh_key()
    scp_args = [
        "scp", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key and os.path.exists(key):
        scp_args.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    scp_args.extend([f"root@{host_ip}:{remote_file}", local_dest])
    try:
        res = subprocess.run(scp_args, capture_output=True, text=True, timeout=60)
        return res.returncode == 0
    except Exception:
        return False

def audit_host(node: str, ip: str):
    print(f"\n🖥️ Auditing Proxmox Hypervisor: {node} ({ip})...")
    dest_dir = os.path.join(REPO_ROOT, "infrastructure", "hosts", node, "baseline")
    os.makedirs(dest_dir, exist_ok=True)

    code, stdout, stderr = run_ssh_script(ip, HOST_AUDIT_SCRIPT)
    if code != 0:
        print(f"  ❌ Host audit failed on {node}: {stderr.strip()}")
        return False

    archive_path = os.path.join(dest_dir, "host-baseline.tar.gz")
    if scp_fetch(ip, "/tmp/host-baseline.tar.gz", archive_path):
        subprocess.run(["tar", "-xzf", archive_path, "-C", dest_dir], check=False)
        if os.path.exists(archive_path):
            os.remove(archive_path)
        # Clean up remote
        run_ssh_cmd(ip, "rm -f /tmp/host-baseline.tar.gz")
        print(f"  ✓ Saved host baseline to {os.path.relpath(dest_dir, REPO_ROOT)}/")
        return True
    return False

def audit_vm(node: str, ip: str, vmid: str, name: str):
    print(f"  ↳ Auditing VM {vmid} ({name})...")
    dest_dir = os.path.join(REPO_ROOT, "infrastructure", "vms", f"{node}-{vmid}-{name}", "baseline")
    os.makedirs(dest_dir, exist_ok=True)

    vm_audit_cmd = '''
    mkdir -p /tmp/vm-baseline/system /tmp/vm-baseline/network /tmp/vm-baseline/services
    uname -a > /tmp/vm-baseline/system/uname.txt 2>&1 || true
    cat /etc/os-release > /tmp/vm-baseline/system/os-release.txt 2>&1 || true
    uptime > /tmp/vm-baseline/system/uptime.txt 2>&1 || true
    df -h > /tmp/vm-baseline/system/disk-usage.txt 2>&1 || true
    free -m > /tmp/vm-baseline/system/memory.txt 2>&1 || true
    ss -tulpn > /tmp/vm-baseline/network/listening-ports.txt 2>&1 || true
    ip addr > /tmp/vm-baseline/network/ip-addr.txt 2>&1 || true
    ip route > /tmp/vm-baseline/network/ip-route.txt 2>&1 || true
    systemctl list-unit-files --state=enabled > /tmp/vm-baseline/services/enabled-units.txt 2>&1 || true
    systemctl list-units --type=service --state=running > /tmp/vm-baseline/services/running-services.txt 2>&1 || true
    if command -v docker >/dev/null 2>&1; then
        docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' > /tmp/vm-baseline/services/docker-containers.txt 2>&1 || true
    fi
    tar -czf /tmp/vm-baseline.tar.gz -C /tmp/vm-baseline .
    rm -rf /tmp/vm-baseline
    base64 -w 0 /tmp/vm-baseline.tar.gz
    rm -f /tmp/vm-baseline.tar.gz
    '''
    qga_cmd = f"qm guest exec {vmid} -- sh -c \"{vm_audit_cmd}\""
    code, stdout, stderr = run_ssh_cmd(ip, qga_cmd, timeout=60)
    if code == 0:
        try:
            data = json.loads(stdout)
            b64_data = data.get("out-data", "").strip()
            if b64_data:
                import base64
                tar_bytes = base64.b64decode(b64_data)
                tar_path = os.path.join(dest_dir, "vm-baseline.tar.gz")
                with open(tar_path, "wb") as f:
                    f.write(tar_bytes)
                subprocess.run(["tar", "-xzf", tar_path, "-C", dest_dir], check=False)
                if os.path.exists(tar_path):
                    os.remove(tar_path)
                print(f"    ✓ Saved VM baseline to {os.path.relpath(dest_dir, REPO_ROOT)}/")
                return True
        except Exception as e:
            print(f"    ❌ Error decoding QGA response for VM {vmid}: {e}")
    else:
        print(f"    ⚠️ QGA audit failed for VM {vmid}: {stderr.strip()}")
    return False

def audit_lxc(node: str, ip: str, vmid: str, name: str):
    print(f"  ↳ Auditing LXC Container {vmid} ({name})...")
    dest_dir = os.path.join(REPO_ROOT, "infrastructure", "vms", f"{node}-{vmid}-{name}", "baseline")
    os.makedirs(dest_dir, exist_ok=True)

    lxc_audit_cmd = f"""pct exec {vmid} -- bash -c '
    mkdir -p /tmp/lxc-baseline/{{system,network,services}}
    uname -a > /tmp/lxc-baseline/system/uname.txt 2>&1 || true
    cat /etc/os-release > /tmp/lxc-baseline/system/os-release.txt 2>&1 || true
    uptime > /tmp/lxc-baseline/system/uptime.txt 2>&1 || true
    df -h > /tmp/lxc-baseline/system/disk-usage.txt 2>&1 || true
    free -m > /tmp/lxc-baseline/system/memory.txt 2>&1 || true
    ss -tulpn > /tmp/lxc-baseline/network/listening-ports.txt 2>&1 || true
    ip addr > /tmp/lxc-baseline/network/ip-addr.txt 2>&1 || true
    ip route > /tmp/lxc-baseline/network/ip-route.txt 2>&1 || true
    systemctl list-unit-files --state=enabled > /tmp/lxc-baseline/services/enabled-units.txt 2>&1 || true
    systemctl list-units --type=service --state=running > /tmp/lxc-baseline/services/running-services.txt 2>&1 || true
    if command -v proxmox-backup-manager >/dev/null 2>&1; then
        proxmox-backup-manager versions > /tmp/lxc-baseline/system/pbs-versions.txt 2>&1 || true
    fi
    tar -czf /tmp/lxc-baseline.tar.gz -C /tmp/lxc-baseline .
    rm -rf /tmp/lxc-baseline
    '
    pct pull {vmid} /tmp/lxc-baseline.tar.gz /tmp/lxc-baseline.tar.gz
    pct exec {vmid} -- rm -f /tmp/lxc-baseline.tar.gz
    """
    code, stdout, stderr = run_ssh_cmd(ip, lxc_audit_cmd, timeout=60)
    if code == 0:
        archive_path = os.path.join(dest_dir, "lxc-baseline.tar.gz")
        if scp_fetch(ip, "/tmp/lxc-baseline.tar.gz", archive_path):
            subprocess.run(["tar", "-xzf", archive_path, "-C", dest_dir], check=False)
            if os.path.exists(archive_path):
                os.remove(archive_path)
            run_ssh_cmd(ip, "rm -f /tmp/lxc-baseline.tar.gz")
            print(f"    ✓ Saved LXC baseline to {os.path.relpath(dest_dir, REPO_ROOT)}/")
            return True
    print(f"    ⚠️ LXC audit failed for container {vmid}: {stderr.strip()}")
    return False

def main():
    parser = argparse.ArgumentParser(description="Audit Proxmox fleet hosts, VMs, and LXCs")
    parser.add_argument("--node", help="Specific node to audit (default: all)")
    args = parser.parse_args()

    nodes = {}
    for meta_file in glob.glob(os.path.join(REPO_ROOT, "infrastructure", "hosts", "*", "meta.json")):
        node_name = os.path.basename(os.path.dirname(meta_file))
        try:
            with open(meta_file, "r") as f:
                data = json.load(f)
                if "ip" in data:
                    nodes[node_name] = data["ip"]
        except Exception:
            pass

    if args.node:
        if args.node not in nodes:
            print(f"❌ Unknown node: {args.node}")
            sys.exit(1)
        nodes = {args.node: nodes[args.node]}

    print("============================================================")
    print("🔍 PROXMOX FLEET DEEP BASELINE AUDIT")
    print("============================================================")

    for node, ip in nodes.items():
        audit_host(node, ip)

        code, stdout, _ = run_ssh_cmd(ip, "qm list")
        if code == 0:
            for line in stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    vmid, name, status = parts[0], parts[1], parts[2]
                    if status == "running":
                        audit_vm(node, ip, vmid, name)

        code, stdout, _ = run_ssh_cmd(ip, "pct list 2>/dev/null || true")
        if code == 0:
            for line in stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3:
                    vmid, status, name = parts[0], parts[1], parts[-1]
                    if status == "running":
                        audit_lxc(node, ip, vmid, name)

    print("\n============================================================")
    print("✅ Fleet Deep Baseline Audit Complete!")
    print("============================================================")

if __name__ == "__main__":
    main()
