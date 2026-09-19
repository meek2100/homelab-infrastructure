#!/usr/bin/env bash
# Phase 1: Mathematically Rigorous Proxmox System Drift & Unowned Files Audit
# Implements debsums package checksum validation and dpkg unowned file diffing across all 3 nodes.
# Usage: ./scripts/phase1-system-drift-audit.sh <NODE_IP> <NODE_NAME>

set -euo pipefail

NODE_IP="${1:-}"
NODE_NAME="${2:-}"

audit_host_drift() {
    local NODE_IP="$1"
    local NODE_NAME="$2"

    echo "============================================================"
    echo "🔬 System Drift & Unowned Files Audit: ${NODE_NAME} (${NODE_IP})"
    echo "============================================================"

    SSH_NODE="ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 root@${NODE_IP}"
    TARGET_DIR="infrastructure/hosts/${NODE_NAME}/drift"
    mkdir -p "${TARGET_DIR}"

    # Step 1: Detect Host Installation Date & Birth Time
    echo "--> 1. Detecting OS Format / Install Date..."
    INSTALL_DATE=$($SSH_NODE "stat / | grep 'Birth' || ls -lact --full-time /etc | tail -1 || true")
    echo "${INSTALL_DATE}" > "${TARGET_DIR}/os-install-date.txt"
    echo "  ✓ Saved install date marker to ${TARGET_DIR}/os-install-date.txt"

    # Step 2: Run debsums for Modified System Configurations
    echo "--> 2. Running debsums system configuration audit..."
    DEBSUMS_OUT=$($SSH_NODE "which debsums >/dev/null || (apt-get update -qq && apt-get install -y -qq debsums); debsums -ce 2>/dev/null || true")
    echo "${DEBSUMS_OUT}" > "${TARGET_DIR}/modified-config-files.txt"
    echo "  ✓ Saved modified system configs report to ${TARGET_DIR}/modified-config-files.txt"

    # Step 3: Unowned / User-Created Files Diff (dpkg vs actual files)
    echo "--> 3. Running dpkg unowned file diff (/etc, /usr/local, /opt, /root)..."
    UNOWNED_SCRIPT='
cat /var/lib/dpkg/info/*.list 2>/dev/null | sort | uniq > /tmp/packaged-files.txt
find /etc /usr/local /opt /root /var/spool/cron/crontabs \( -type d -name ".rustup" -prune -o -type d -name ".cargo" -prune -o -type d -name ".npm" -prune -o -type d -name ".cache" -prune -o -type d -name "node_modules" -prune -o -type d -name "venv" -prune -o -type d -name ".venv" -prune \) -o -type f -print 2>/dev/null | sort > /tmp/actual-files.txt
comm -23 /tmp/actual-files.txt /tmp/packaged-files.txt 2>/dev/null || true
rm -f /tmp/packaged-files.txt /tmp/actual-files.txt
'
    UNOWNED_OUT=$($SSH_NODE "bash -c '${UNOWNED_SCRIPT}'")
    echo "${UNOWNED_OUT}" > "${TARGET_DIR}/unowned-user-files.txt"
    echo "  ✓ Saved unowned user files report to ${TARGET_DIR}/unowned-user-files.txt"

    # Step 4: Full Proxmox Cluster / FUSE State (/etc/pve)
    echo "--> 4. Exporting Proxmox /etc/pve configuration tree..."
    PVE_STATE=$($SSH_NODE "find /etc/pve -type f -exec ls -la {} + 2>/dev/null || true")
    echo "${PVE_STATE}" > "${TARGET_DIR}/pve-cluster-state.txt"
    echo "  ✓ Saved /etc/pve cluster state to ${TARGET_DIR}/pve-cluster-state.txt"

    echo ""
    echo "============================================================"
    echo "✅ System Drift & Unowned Files Audit Complete for ${NODE_NAME}"
    echo "============================================================"
}

if [[ -n "$NODE_IP" && -n "$NODE_NAME" ]]; then
    audit_host_drift "$NODE_IP" "$NODE_NAME"
else
    # Auto-discover all hosts
    for host_dir in infrastructure/hosts/*; do
        if [ -d "$host_dir" ]; then
            node=$(basename "$host_dir")
            meta_file="$host_dir/meta.json"
            if [ -f "$meta_file" ]; then
                ip=$(jq -r .ip "$meta_file")
                audit_host_drift "$ip" "$node"
            fi
        fi
    done
fi
