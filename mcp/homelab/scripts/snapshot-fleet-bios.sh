#!/usr/bin/env bash
# ==============================================================================
# snapshot-fleet-bios.sh
# ------------------------------------------------------------------------------
# Zero-touch BIOS & Firmware Settings Audit across Proxmox Hypervisors
# Extracts:
#   1. OEM WMI Firmware Attributes (Dell SMBIOS / HP WMI if exposed)
#   2. DMI Tables (BIOS version/release date, system board, CPU, memory)
#   3. CPU Frequency Governors & Available Governors
#   4. Hardware C-States / Idle Power States
#   5. Hardware Virtualization (VT-x / AMD-V) & IOMMU / VT-d Initialization
#   6. ACPI Wakeup Triggers & Power Supply / Battery Subsystems
#   7. UEFI NVRAM Boot Entries & Boot Order
#
# Copies snapshots back to:
#   infrastructure/hosts/<node>/bios/
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

SSH_KEY=""
for key_candidate in \
    "${HOME}/.ssh/proxmox_ed25519" \
    "/home/agentsvc/.ssh/proxmox_ed25519" \
    "/home/dtheurer/.ssh/proxmox_ed25519" \
    "${HOME}/.ssh/id_ed25519" \
    "/home/dtheurer/.ssh/id_ed25519"; do
    if [[ -f "${key_candidate}" ]]; then
        SSH_KEY="${key_candidate}"
        break
    fi
done

SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=8)
if [[ -n "${SSH_KEY}" ]]; then
    SSH_OPTS+=(-i "${SSH_KEY}")
fi

declare -A NODES=(
    ["pve"]="192.168.1.250"
    ["pve2"]="192.168.1.240"
    ["pve3"]="192.168.1.245"
)

audit_node() {
    local node="$1"
    local ip="$2"
    local dest_dir="${REPO_ROOT}/infrastructure/hosts/${node}/bios"

    echo "=================================================================="
    echo "🔍 Starting BIOS & Firmware Audit: ${node} (${ip})"
    echo "=================================================================="

    mkdir -p "${dest_dir}"

    local remote_script='
set -euo pipefail
TMP_DIR=$(mktemp -d /tmp/bios-audit-XXXXXX)
cd "${TMP_DIR}"

# 1. OEM Firmware Attributes (Dell SMBIOS / HP WMI)
mkdir -p firmware-attributes
modprobe dell-smbios-wmi 2>/dev/null || true
modprobe hp-wmi 2>/dev/null || true

if [ -d /sys/class/firmware-attributes ]; then
    find /sys/class/firmware-attributes -type f | while read -r f; do
        rel="${f#/sys/class/firmware-attributes/}"
        mkdir -p "firmware-attributes/$(dirname "$rel")"
        cat "$f" > "firmware-attributes/$rel" 2>/dev/null || true
    done
fi

# 2. DMI System, BIOS, CPU, Memory
dmidecode -t bios > dmi-bios.txt 2>&1 || true
dmidecode -t system > dmi-system.txt 2>&1 || true
dmidecode -t processor > dmi-processor.txt 2>&1 || true
dmidecode -t memory > dmi-memory.txt 2>&1 || true

# 3. CPU Governors, Frequencies & C-States
mkdir -p power
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor > power/current-governor.txt 2>/dev/null || true
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors > power/available-governors.txt 2>/dev/null || true
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver > power/scaling-driver.txt 2>/dev/null || true

for state in /sys/devices/system/cpu/cpu0/cpuidle/state*; do
    if [ -d "$state" ]; then
        sname=$(basename "$state")
        echo "[$sname] name=$(cat "$state/name" 2>/dev/null) desc=$(cat "$state/desc" 2>/dev/null) disable=$(cat "$state/disable" 2>/dev/null)" >> power/c-states.txt
    fi
done

# 4. Virtualization & IOMMU / VT-d Hardware Flags
mkdir -p virtualization
egrep -o "(vmx|svm)" /proc/cpuinfo | sort -u > virtualization/cpu-flags.txt || true
dmesg | grep -E -i "iommu|dmar|vt-d" | head -n 50 > virtualization/dmesg-iommu.txt || true
if [ -d /sys/kernel/iommu_groups ]; then
    find /sys/kernel/iommu_groups/ -maxdepth 2 -print > virtualization/iommu-groups.txt 2>/dev/null || true
fi

# 5. ACPI Wakeup, Power Supply & Thermal
mkdir -p acpi
cat /proc/acpi/wakeup > acpi/wakeup-sources.txt 2>/dev/null || true
ls -la /sys/class/power_supply/ > acpi/power-supplies.txt 2>/dev/null || true
for ps in /sys/class/power_supply/*; do
    if [ -d "$ps" ]; then
        echo "=== $(basename "$ps") ===" >> acpi/power-supplies-detail.txt
        head -n 20 "$ps"/* >> acpi/power-supplies-detail.txt 2>/dev/null || true
    fi
done

# 6. UEFI Boot Configuration
efibootmgr -v > efibootmgr.txt 2>&1 || true

# 7. Package and output archive
tar -czf /tmp/bios-snapshot.tar.gz -C "${TMP_DIR}" .
rm -rf "${TMP_DIR}"
echo "SNAPSHOT_COMPLETE"
'

    echo "📡 Running remote inspection on ${node}..."
    ssh "${SSH_OPTS[@]}" "root@${ip}" "${remote_script}"

    echo "📥 Downloading snapshot archive from ${node}..."
    scp "${SSH_OPTS[@]}" "root@${ip}:/tmp/bios-snapshot.tar.gz" "${dest_dir}/bios-snapshot.tar.gz"

    echo "📦 Extracting files into ${dest_dir}..."
    tar -xzf "${dest_dir}/bios-snapshot.tar.gz" -C "${dest_dir}/"
    rm -f "${dest_dir}/bios-snapshot.tar.gz"

    # Clean up remote temp archive
    ssh "${SSH_OPTS[@]}" "root@${ip}" "rm -f /tmp/bios-snapshot.tar.gz"

    echo "✅ Completed audit for ${node}. Files saved in:"
    echo "   ${dest_dir}"
    echo ""
}

TARGET_NODE="${1:-all}"

if [[ "${TARGET_NODE}" == "all" ]]; then
    for node in "pve" "pve2" "pve3"; do
        audit_node "${node}" "${NODES[${node}]}"
    done
else
    if [[ -n "${NODES[${TARGET_NODE}]+x}" ]]; then
        audit_node "${TARGET_NODE}" "${NODES[${TARGET_NODE}]}"
    else
        echo "❌ Unknown target node: '${TARGET_NODE}'. Must be one of: pve, pve2, pve3, all"
        exit 1
    fi
fi

echo "=================================================================="
echo "🎉 Fleet BIOS & Firmware Snapshot Complete!"
echo "=================================================================="
