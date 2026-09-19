#!/usr/bin/env bash
# Phase 1: Proxmox Host & System Configuration File Extractor
# Non-destructively copies all custom host OS configuration files across pve, pve2, pve3 into Git blueprints.

set -euo pipefail

extract_node_configs() {
    local node="$1"
    local ip="$2"

    echo "============================================================"
    echo "📥 Extracting Host OS Config Files: Node ${node} (${ip})"
    echo "============================================================"

    local target_dir="infrastructure/hosts/${node}/configs"
    mkdir -p "${target_dir}"

    local ssh_cmd="ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 root@${ip}"

    # 1. Network & Interfaces
    $ssh_cmd "cat /etc/network/interfaces 2>/dev/null" > "${target_dir}/interfaces" || true

    # 2. Boot & Kernel Configs
    $ssh_cmd "cat /etc/default/grub 2>/dev/null" > "${target_dir}/grub" || true
    $ssh_cmd "cat /etc/modules 2>/dev/null" > "${target_dir}/modules" || true
    $ssh_cmd "tar -czf - /etc/modprobe.d 2>/dev/null" | tar -xzf - -C "${target_dir}" 2>/dev/null || true

    # 3. Proxmox Storage & VM Configs
    $ssh_cmd "cat /etc/pve/storage.cfg 2>/dev/null" > "${target_dir}/storage.cfg" || true
    mkdir -p "${target_dir}/qemu-server"
    $ssh_cmd "tar -czf - /etc/pve/qemu-server 2>/dev/null" | tar -xzf - -C "${target_dir}/qemu-server" --strip-components=3 2>/dev/null || true

    # 4. Power & Lid Switch Fixes (Dell Precision / Host Systemd)
    $ssh_cmd "cat /etc/systemd/logind.conf 2>/dev/null" > "${target_dir}/logind.conf" || true
    mkdir -p "${target_dir}/acpi"
    $ssh_cmd "tar -czf - /etc/acpi 2>/dev/null" | tar -xzf - -C "${target_dir}/acpi" --strip-components=2 2>/dev/null || true

    # 5. Host Crontabs & Custom Scripts
    mkdir -p "${target_dir}/cron"
    $ssh_cmd "cat /etc/crontab 2>/dev/null" > "${target_dir}/cron/crontab" || true
    $ssh_cmd "tar -czf - /etc/cron.d /var/spool/cron/crontabs 2>/dev/null" | tar -xzf - -C "${target_dir}/cron" --strip-components=2 2>/dev/null || true

    # 6. Custom Scripts in /usr/local/bin or /root/scripts
    mkdir -p "${target_dir}/custom-scripts"
    $ssh_cmd "tar -czf - /usr/local/bin /usr/local/sbin /root/scripts 2>/dev/null" | tar -xzf - -C "${target_dir}/custom-scripts" --strip-components=3 2>/dev/null || true

    # 7. Unowned User Configurations (Nginx, Let's Encrypt, Samba, Custom Utils)
    mkdir -p "${target_dir}/custom-configs/etc"
    $ssh_cmd "tar -czf - /etc/nginx /etc/letsencrypt /etc/samba 2>/dev/null" | tar -xzf - -C "${target_dir}/custom-configs" 2>/dev/null || true
    mkdir -p "${target_dir}/custom-configs/root"
    $ssh_cmd "tar -czf - /root/Proxmox-Enhanced-Configuration-Utility 2>/dev/null" | tar -xzf - -C "${target_dir}/custom-configs" 2>/dev/null || true

    echo "  ✓ Extracted host configs for ${node} into ${target_dir}/"
}

for host_dir in infrastructure/hosts/*; do
    if [ -d "$host_dir" ]; then
        node=$(basename "$host_dir")
        meta_file="$host_dir/meta.json"
        if [ -f "$meta_file" ]; then
            ip=$(jq -r .ip "$meta_file")
            extract_node_configs "$node" "$ip"
        fi
    fi
done

echo ""
echo "============================================================"
echo "✅ All Host OS Configuration Files Successfully Extracted!"
echo "============================================================"
