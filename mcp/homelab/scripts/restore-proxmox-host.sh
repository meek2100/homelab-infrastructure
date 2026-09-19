#!/usr/bin/env bash
#
# restore-proxmox-host.sh
# Safely restores host-level configurations for a given Proxmox node.
# Run this directly on the target Proxmox host.

NODE=$1
if [ -z "$NODE" ]; then
    echo "Usage: ./restore-proxmox-host.sh <node_name> (e.g. pve, pve2, pve3)"
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

BASE_DIR="$(pwd)/nodes/$NODE/host-configs"
if [ ! -d "$BASE_DIR" ]; then
    echo "Error: Directory $BASE_DIR does not exist. Are you in the repo root?"
    exit 1
fi

echo "WARNING: This will overwrite critical /etc and /etc/pve configurations on this host!"
read -p "Are you sure you want to restore host configs for node '$NODE'? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

echo "[*] Restoring Network Interfaces..."
if [ -f "$BASE_DIR/interfaces" ]; then
    cp "$BASE_DIR/interfaces" /etc/network/interfaces
fi

echo "[*] Restoring Storage Configuration..."
if [ -f "$BASE_DIR/storage.cfg" ]; then
    cp "$BASE_DIR/storage.cfg" /etc/pve/storage.cfg
fi

echo "[*] Restoring VM Hardware Definitions (qemu-server)..."
if [ -d "$BASE_DIR/qemu-server" ]; then
    mkdir -p /etc/pve/qemu-server
    cp "$BASE_DIR/qemu-server/"*.conf /etc/pve/qemu-server/ 2>/dev/null || true
fi

echo "[*] Restoring System Configurations (grub, modules, logind.conf)..."
if [ -f "$BASE_DIR/grub" ]; then cp "$BASE_DIR/grub" /etc/default/grub; fi
if [ -f "$BASE_DIR/modules" ]; then cp "$BASE_DIR/modules" /etc/modules; fi
if [ -f "$BASE_DIR/logind.conf" ]; then cp "$BASE_DIR/logind.conf" /systemd/logind.conf 2>/dev/null || cp "$BASE_DIR/logind.conf" /etc/systemd/logind.conf; fi

echo "[*] Restoring custom etc directories (nginx, cron, acpi)..."
if [ -d "$BASE_DIR/nginx" ]; then cp -r "$BASE_DIR/nginx" /etc/; fi
if [ -d "$BASE_DIR/cron" ]; then cp -r "$BASE_DIR/cron/"* /etc/cron.d/ 2>/dev/null || true; fi
if [ -d "$BASE_DIR/acpi" ]; then cp -r "$BASE_DIR/acpi" /etc/; fi

echo ""
echo "✅ Host restoration complete for $NODE!"
echo "NOTE: You MUST reboot this node to safely apply the network, storage, and grub changes."
echo "If grub was changed, remember to run 'update-grub' and 'update-initramfs -u'."
