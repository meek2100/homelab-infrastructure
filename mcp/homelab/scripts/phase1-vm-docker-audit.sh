#!/usr/bin/env bash
# Phase 1: Deep Read-Only VM & Docker Stack Audit Script
# Executes non-destructive information gathering inside Virtual Machines via Proxmox QEMU Guest Agent.
# Usage: ./scripts/phase1-vm-docker-audit.sh <PROXMOX_NODE_IP> <VMID> <VM_NAME>

set -euo pipefail

NODE_IP="${1:-}"
VMID="${2:-}"
VM_NAME="${3:-}"

if [[ -z "$NODE_IP" || -z "$VMID" ]]; then
    echo "Usage: $0 <PROXMOX_NODE_IP> <VMID> [VM_NAME]"
    exit 1
fi

echo "============================================================"
echo "🔍 Deep VM Audit: VM ${VMID} (${VM_NAME}) on Host ${NODE_IP}"
echo "============================================================"

SSH_NODE="ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 root@${NODE_IP}"

run_vm_cmd() {
    local title="$1"
    local cmd="$2"
    echo ""
    echo "------------------------------------------------------------"
    echo "📌 ${title}"
    echo "------------------------------------------------------------"
    $SSH_NODE "qm guest exec ${VMID} -- bash -c \"${cmd}\"" 2>&1 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'out-data' in data:
        print(data['out-data'])
    elif 'err-data' in data:
        print(data['err-data'])
    else:
        print(json.dumps(data, indent=2))
except Exception as e:
    sys.stdout.write(sys.stdin.read())
" || echo "⚠️ QEMU Guest Agent unavailable or command failed on VM ${VMID}"
}

# 1. VM OS & System Environment
run_vm_cmd "VM OS Release & Hostname" "hostname && cat /etc/os-release 2>/dev/null || uname -a"
run_vm_cmd "VM Network Interfaces & IPs" "ip -brief a 2>/dev/null || ip a"
run_vm_cmd "VM Routing Table" "ip route"
run_vm_cmd "VM Mounts & /etc/fstab" "cat /etc/fstab; echo '--- Mounts ---'; mount | grep -E 'nfs|cifs|smb|ext4|xfs|overlay' || df -h"
run_vm_cmd "VM Active Systemd Services" "systemctl list-units --type=service --state=running 2>/dev/null || ps aux"
run_vm_cmd "VM Crontabs & Schedules" "crontab -l 2>/dev/null; cat /etc/crontab /etc/cron.d/* 2>/dev/null || true"

# 2. Docker Engine & Portainer Stacks
run_vm_cmd "Docker Version & Info" "docker version 2>/dev/null; docker info 2>/dev/null | grep -E 'Containers|Images|Server Version|Storage Driver'"
run_vm_cmd "All Containers (Active & Inactive)" "docker ps -a --format 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}' 2>/dev/null || true"
run_vm_cmd "Docker Networks" "docker network ls 2>/dev/null || true"
run_vm_cmd "Docker Volumes & Mount Paths" "docker volume ls 2>/dev/null || true"
run_vm_cmd "Portainer Stacks & Compose Directories" "ls -la /data/compose/ /var/lib/portainer/ /data/ 2>/dev/null || true"

# 3. Application Config Inspections (Read-Only)
run_vm_cmd "AdGuard Home Config Header" "head -n 40 /opt/adguardhome/conf/AdGuardHome.yaml /etc/adguardhome/AdGuardHome.yaml 2>/dev/null || true"
run_vm_cmd "Nginx Proxy Manager Proxy Hosts" "ls -la /data/nginx/proxy_host/ /data/nginx/redirection_host/ 2>/dev/null || true"
run_vm_cmd "Home Assistant / Homebridge Mounts" "ls -la /usr/share/hassio/ /var/lib/homebridge/ /root/.homebridge/ 2>/dev/null || true"

echo ""
echo "============================================================"
echo "✅ Deep VM Audit Complete for VM ${VMID} (${VM_NAME})"
echo "============================================================"
