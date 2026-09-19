#!/usr/bin/env bash
# Phase 1: Read-Only Homelab Node Audit Script
# Executes 100% non-destructive information gathering over SSH.
# Usage: ./scripts/phase1-readonly-audit.sh <NODE_IP_OR_HOSTNAME> [SSH_USER]

set -euo pipefail

TARGET_HOST="${1:-}"
SSH_USER="${2:-root}"

if [[ -z "$TARGET_HOST" ]]; then
    echo "Usage: $0 <NODE_IP_OR_HOSTNAME> [SSH_USER]"
    echo "Example: $0 192.168.1.100 root"
    exit 1
fi

echo "============================================================"
echo "🔍 Starting Read-Only Audit for Node: ${SSH_USER}@${TARGET_HOST}"
echo "============================================================"

SSH_CMD="ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 ${SSH_USER}@${TARGET_HOST}"

run_remote() {
    local title="$1"
    local cmd="$2"
    echo ""
    echo "------------------------------------------------------------"
    echo "📌 ${title}"
    echo "------------------------------------------------------------"
    $SSH_CMD "$cmd" 2>&1 || echo "⚠️ Command failed or restricted on ${TARGET_HOST}"
}

# 1. System & Hardware Specs
run_remote "System Model & Hostname" "hostnamectl 2>/dev/null || hostname; dmidecode -s system-product-name 2>/dev/null || true"
run_remote "CPU Info" "lscpu | grep -E 'Model name|Core\(s\)|Thread\(s\)|Socket\(s\)'"
run_remote "RAM Allocation" "free -h"
run_remote "Storage Disks & Controllers" "lsblk -o NAME,SIZE,TYPE,MODEL,FSTYPE,MOUNTPOINT | grep -v 'loop'"
run_remote "PCI Graphics / GPUs" "lspci -nn | grep -E -i 'vga|3d|display|nvidia|amd|intel'"

# 2. Kernel & Proxmox Boot Configs
run_remote "GRUB Configuration (/etc/default/grub)" "cat /etc/default/grub"
run_remote "Modprobe Blacklist & VFIO Configs" "cat /etc/modprobe.d/*.conf 2>/dev/null || true"
run_remote "Kernel Version & Modules" "uname -a; lsmod | grep -E 'vfio|nvidia|nouveau|kvm'"

# 3. Power, Lid & Systemd Settings
run_remote "Systemd Logind Config" "cat /etc/systemd/logind.conf"
run_remote "ACPI Event Configurations" "ls -la /etc/acpi/events/ /etc/acpi/ 2>/dev/null || true"

# 4. Network Status & Routing
run_remote "IP Addresses & Interfaces" "ip -brief a"
run_remote "Routing Table" "ip route"
run_remote "Active Network Ports" "ss -tulpn"

# 5. Proxmox VE Storage & Virtual Machines
run_remote "Proxmox Storage Config (/etc/pve/storage.cfg)" "cat /etc/pve/storage.cfg 2>/dev/null || true"
run_remote "Proxmox VM List" "qm list 2>/dev/null || true"
run_remote "Proxmox LXC Container List" "pct list 2>/dev/null || true"
run_remote "Proxmox VM Configurations" "cat /etc/pve/qemu-server/*.conf 2>/dev/null || true"
run_remote "Proxmox LXC Configurations" "cat /etc/pve/lxc/*.conf 2>/dev/null || true"
run_remote "Proxmox Cron & Backup Schedules" "cat /etc/pve/vzdump.cron /etc/crontab 2>/dev/null || true"

echo ""
echo "============================================================"
echo "✅ Read-Only Audit Complete for ${TARGET_HOST}"
echo "============================================================"
