#!/usr/bin/env bash
# Phase 1: Mathematical System Drift & Unowned Files Audit for Virtual Machines
# Runs debsums and dpkg set-differencing inside VMs via Proxmox QEMU Guest Agent.

set -euo pipefail

# Dynamically populate TARGET_VMS from infrastructure/vms folder
TARGET_VMS=()
for vm_dir in infrastructure/vms/*; do
    if [ -d "$vm_dir" ]; then
        vm_folder=$(basename "$vm_dir")
        # Extract node and vmid using string manipulation (bash safe)
        node="${vm_folder%%-*}"
        rest="${vm_folder#*-}"
        vmid="${rest%%-*}"
        name="${rest#*-}"
        
        meta_file="infrastructure/hosts/$node/meta.json"
        if [ -f "$meta_file" ]; then
            ip=$(jq -r .ip "$meta_file")
            TARGET_VMS+=("$node:$ip:$vmid:$name")
        fi
    fi
done

audit_vm_drift() {
    local node="$1"
    local ip="$2"
    local vmid="$3"
    local vm_name="$4"

    echo "============================================================"
    echo "🔬 VM System Drift Audit: VM ${vmid} (${vm_name}) on ${node}"
    echo "============================================================"

    local target_dir="infrastructure/vms/${node}-${vmid}-${vm_name}/drift"
    mkdir -p "${target_dir}"

    local ssh_cmd="ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 root@${ip}"

    # 1. VM Installation Marker
    echo "--> 1. Detecting VM OS Install Date..."
    $ssh_cmd "qm guest exec ${vmid} -- bash -c 'stat / | grep Birth || ls -lact --full-time /etc | tail -1'" 2>&1 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('out-data', ''))
except Exception:
    pass
" > "${target_dir}/os-install-date.txt" || true
    echo "  ✓ Saved VM install date marker to ${target_dir}/os-install-date.txt"

    # 2. debsums Package Config Validation inside VM
    echo "--> 2. Running debsums system configuration audit inside VM ${vmid}..."
    local debsums_cmd="which debsums >/dev/null || (apt-get update -qq && apt-get install -y -qq debsums); debsums -ce 2>/dev/null || true"
    $ssh_cmd "qm guest exec ${vmid} -- bash -c \"${debsums_cmd}\"" 2>&1 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('out-data', ''))
except Exception:
    pass
" > "${target_dir}/modified-config-files.txt" || true
    echo "  ✓ Saved modified VM system configs report to ${target_dir}/modified-config-files.txt"

    # 3. dpkg vs Actual Filesystem Diff inside VM
    echo "--> 3. Running dpkg unowned file diff inside VM ${vmid} (/etc, /usr/local, /opt, /root)..."
    local unowned_cmd="cat /var/lib/dpkg/info/*.list 2>/dev/null | sort | uniq > /tmp/pkg.txt; find /etc /usr/local /opt /root /var/spool/cron/crontabs \\( -type d -name '.rustup' -prune -o -type d -name '.cargo' -prune -o -type d -name '.npm' -prune -o -type d -name '.cache' -prune -o -type d -name 'node_modules' -prune -o -type d -name 'venv' -prune -o -type d -name '.venv' -prune \\) -o -type f -print 2>/dev/null | sort > /tmp/act.txt; comm -23 /tmp/act.txt /tmp/pkg.txt 2>/dev/null; rm -f /tmp/pkg.txt /tmp/act.txt"
    $ssh_cmd "qm guest exec ${vmid} -- bash -c \"${unowned_cmd}\"" 2>&1 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('out-data', ''))
except Exception:
    pass
" > "${target_dir}/unowned-user-files.txt" || true
    echo "  ✓ Saved unowned VM user files report to ${target_dir}/unowned-user-files.txt"

    echo ""
    echo "============================================================"
    echo "✅ VM System Drift Audit Complete for VM ${vmid} (${vm_name})"
    echo "============================================================"
}

for item in "${TARGET_VMS[@]}"; do
    IFS=":" read -r node ip vmid vm_name <<< "$item"
    audit_vm_drift "$node" "$ip" "$vmid" "$vm_name"
done

echo ""
echo "============================================================"
echo "🎉 All Active Virtual Machine System Drift Audits Complete!"
echo "============================================================"
