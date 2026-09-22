# 🔒 Known-Good State: VXLAN Failover System
## Captured: 2026-09-22 (pre-RSTP-redesign)

> **DO NOT OVERWRITE or DELETE** this directory until the vxlan-server RSTP redesign
> (Part 4 of the network implementation plan) is verified working end-to-end.
> Fleet syncs (`sync_fleet`) must NOT clobber this directory.

---

## What Is Preserved Here

### `vxlan-server-vm107/` — VM 107 (pve) Known-Good Files
The complete `/etc` and `usr/local/bin/` snapshot of `vxlan-server` at the time the
3-priority failover system was verified working. Key files:

| File | Role |
| :--- | :--- |
| `etc/network/vxlan-nm.conf` | VXLAN tunnel config: endpoint IPs, VNI, MTU, interface names |
| `etc/network/interfaces` | Linux bridge + VXLAN network interface definitions |
| `etc/systemd/system/vxlan-nm.service` | Systemd unit that starts the VXLAN tunnel daemon on boot |
| `etc/logrotate.d/vxlan-nm` | Log rotation for vxlan-nm daemon output |
| `usr/local/bin/vxlan-nm` | The VXLAN tunnel manager daemon binary/script |
| `107.conf` | Proxmox QEMU hardware config (NICs, CPU, RAM, disk) |

### `openwrt/` — OpenWrt (Belkin AX3200, `192.168.1.226`) Known-Good Configs
The complete UCI configuration, failover daemon scripts, and VXLAN client config.
Key files:

| File | Role |
| :--- | :--- |
| `configs/network` | OpenWrt network interfaces — VXLAN150 client endpoint definition |
| `custom/etc_vxlan-nm.conf` | OpenWrt-side VXLAN config (mirrors vxlan-server's config) |
| `scripts/failover.sh` | 3-priority failover daemon (Wire > VXLAN150 > Wi-Fi repeater) |
| `scripts/failover-tester.py` | Failover testing and validation script |
| `configs/firewall` | OpenWrt firewall rules (permits VXLAN UDP:4789) |
| `opkg.installed` | Full package manifest for restoration |

---

## Proxmox VM Snapshot

A hard snapshot named `known-good-vxlan-pre-redesign` was taken on **pve VM 107** on 2026-09-22.

To roll back the entire VM disk (run manually on pve host — do not automate):
```bash
qm rollback 107 known-good-vxlan-pre-redesign
qm start 107
```

To verify snapshot still exists:
```bash
qm listsnapshot 107
```

---

## OpenWrt Config Restore

If OpenWrt side needs restoring from these files:
```bash
SOPS_AGE_KEY_FILE=homelab-infrastructure.key python3 mcp/homelab/scripts/restore-openwrt-config.py
```

---

## When to Delete This Directory

Only remove after ALL of the following are verified:
1. [ ] VM 107 RSTP bridge path costs configured and tested
2. [ ] Failover from AP bridge → VXLAN confirmed < 5 seconds
3. [ ] Zero MAC_MOVE events on Araknis 920 during switchover
4. [ ] Fresh fleet sync committed to `infrastructure/vms/pve-107-vxlan-server/`
5. [ ] Proxmox snapshot `known-good-vxlan-pre-redesign` deleted after success

Until all 5 are checked, this directory and the Proxmox snapshot are the
only reliable revert points for the 3-priority failover system.
