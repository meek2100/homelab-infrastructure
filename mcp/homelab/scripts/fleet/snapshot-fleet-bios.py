#!/usr/bin/env python3
"""
snapshot-fleet-bios.py
Pure Python Zero-Touch BIOS, Firmware, Power & Hardware Snapshot across Proxmox Hypervisors.
Extracts:
  1. OEM WMI Firmware Attributes (Dell SMBIOS / HP WMI)
  2. DMI Tables (BIOS, System, Processor, Memory)
  3. CPU Governors, Frequencies & C-States
  4. Virtualization & IOMMU / VT-d Hardware Flags
  5. ACPI Wakeup, Power Supply & Thermal Status
  6. UEFI NVRAM Boot Entries & Boot Order
Saves snapshots to: infrastructure/hosts/<node>/bios/
"""

import argparse
import glob
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

REMOTE_AUDIT_SCRIPT = '''
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

rm -f power/c-states.txt
for state in /sys/devices/system/cpu/cpu0/cpuidle/state*; do
    if [ -d "$state" ]; then
        sname=$(basename "$state")
        echo "[$sname] name=$(cat "$state/name" 2>/dev/null) desc=$(cat "$state/desc" 2>/dev/null) disable=$(cat "$state/disable" 2>/dev/null)" >> power/c-states.txt
    fi
done

# 4. Virtualization & IOMMU / VT-d Hardware Flags
mkdir -p virtualization
grep -E -o "(vmx|svm)" /proc/cpuinfo | sort -u > virtualization/cpu-flags.txt 2>/dev/null || true
dmesg | grep -E -i "iommu|dmar|vt-d" | head -n 50 > virtualization/dmesg-iommu.txt 2>/dev/null || true
if [ -d /sys/kernel/iommu_groups ]; then
    find /sys/kernel/iommu_groups/ -maxdepth 2 -print > virtualization/iommu-groups.txt 2>/dev/null || true
fi

# 5. ACPI Wakeup, Power Supply & Thermal
mkdir -p acpi
cat /proc/acpi/wakeup > acpi/wakeup-sources.txt 2>/dev/null || true
ls -la /sys/class/power_supply/ > acpi/power-supplies.txt 2>/dev/null || true
rm -f acpi/power-supplies-detail.txt
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

def audit_node(node: str, ip: str):
    dest_dir = os.path.join(REPO_ROOT, "infrastructure", "hosts", node, "bios")
    print("==================================================================")
    print(f"🔍 Starting BIOS & Firmware Audit: {node} ({ip})")
    print("==================================================================")

    os.makedirs(dest_dir, exist_ok=True)
    code, stdout, stderr = run_ssh_script(ip, REMOTE_AUDIT_SCRIPT)
    if code != 0:
        print(f"❌ Failed to run audit script on {node}: {stderr.strip()}")
        return False

    archive_path = os.path.join(dest_dir, "bios-snapshot.tar.gz")
    if not scp_fetch(ip, "/tmp/bios-snapshot.tar.gz", archive_path):
        print(f"❌ Failed to download bios-snapshot from {node}")
        return False

    subprocess.run(["tar", "-xzf", archive_path, "-C", dest_dir], check=False)
    if os.path.exists(archive_path):
        os.remove(archive_path)

    # Clean up remote archive
    key = get_ssh_key()
    ssh_clean = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes"]
    if key: ssh_clean.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    ssh_clean.extend([f"root@{ip}", "rm -f /tmp/bios-snapshot.tar.gz"])
    subprocess.run(ssh_clean, capture_output=True)

    print(f"✅ Completed audit for {node}. Files saved in:")
    print(f"   {os.path.relpath(dest_dir, REPO_ROOT)}/\n")
    return True

def main():
    parser = argparse.ArgumentParser(description="Snapshot Proxmox fleet BIOS, firmware and power settings")
    parser.add_argument("node", nargs="?", default="all", help="Target node (pve, pve2, pve3, or all)")
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

    target_nodes = nodes if args.node == "all" else {args.node: nodes[args.node]} if args.node in nodes else {}
    if not target_nodes:
        print(f"❌ Unknown target node: '{args.node}'. Must be one of: {list(nodes.keys())} or 'all'")
        sys.exit(1)

    for node, ip in target_nodes.items():
        audit_node(node, ip)

    print("==================================================================")
    print("🎉 Fleet BIOS & Firmware Snapshot Complete!")
    print("==================================================================")

if __name__ == "__main__":
    main()
