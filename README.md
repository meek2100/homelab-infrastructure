# 🛠️ Central Homelab Inventory & Control Tower

This repository holds the absolute source of truth for our three isolated standalone Proxmox VE hosts (`pve`, `pve2`, `pve3`). The hosts are deliberately not clustered to prevent network cascading failures if a node reboots or enters a restricted VPN state.

---

## 🛜 Network Subnet & Routing Topology Map

Full empirical topology map generated in [`docs/network-topology-map.md`](file:///home/agentsvc/repos/homelab-infrastructure/docs/network-topology-map.md):

* **1. Primary Management & Service LAN (`192.168.1.0/24`)**:
  - `pve`: `192.168.1.250` (`vmbr0`)
  - `pve2`: `192.168.1.240` (`vmbr0`)
  - `pve3`: `192.168.1.245` (`vmbr0`)
  - `nexus-server` (`VM 100` on `pve`): `192.168.1.185` (Primary Ingress / NPM / Cloudflare / WireGuard)
  - `nexus-server2` (`VM 100` on `pve3`): `192.168.1.186` (Primary Network DNS / AdGuard Home)
  - `vxlan-server` (`VM 107` on `pve`): `192.168.1.150` (`vxlan-nm.service` bridging interface `vxlan150`)

* **2. Dedicated Private High-Speed NAS Storage LAN (`10.25.25.0/24`)**:
  - `pve`: `10.25.25.250/24` (`vmbr1`)
  - `pve2`: `10.25.25.240/24` (`vmbr1`)
  - `pve3`: `10.25.25.245/24` (`vmbr1`)
  - **`nas-server` (`VM 101` on `pve3`)**: **`10.25.25.248/24`** (`ens19` — OpenMediaVault Core NAS Array)
  - **`discovery-server` (`VM 100` on `pve2`)**: **`10.25.25.246/24`** (`ens18` — VPN Download Gateway with direct NAS storage interface)

* **3. Smart Home & Management VLANs (`192.168.40.0/24` & `192.168.50.0/24`)**:
  - `pve2`: `192.168.40.240` (`vmbr0.40`), `192.168.50.240` (`vmbr0.50`)
  - `nas-server` (`VM 101` on `pve3`): `192.168.40.248` (`ens18` — VLAN 40 Management Interface)
  - `luna-server` (`VM 102` on `pve`): `vlan40_network` macvlan binding for Home Assistant / Homebridge

---

## 🔬 Mathematical System Drift & Unowned Files Audit Matrix (Hosts & VMs)

Using `debsums -ce` (Debian package config validation) and `dpkg` vs actual filesystem set-differencing (`comm -23 actual packaged`), 100% of system configuration changes and user-added files since base OS installation have been audited across Proxmox hosts and Virtual Machines:

### 1. Physical Proxmox Host OS Drift Audit
| Node | Installation Marker | Package Config Drift (`debsums -ce`) | Unowned User Artifacts Discovered | System Drift Audit Log |
| :--- | :--- | :--- | :--- | :--- |
| **`pve`** | Debian 12 / PVE 8 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | `/root/setup_gpu_passthrough.sh`, `/root/generate_nginx_configs.sh`, `/root/.secrets/certbot/`, `/etc/nginx/conf.d/*.conf` (30+ Nginx proxy hosts), `/usr/local/bin/mount-backup-drive.sh`, `/usr/local/bin/sysprep.sh`, Proxmox Config Utility | [`nodes/pve/system-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve/system-drift/) |
| **`pve2`** | Debian 12 / PVE 8 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | Proxmox storage definitions & Portainer CE volumes | [`nodes/pve2/system-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve2/system-drift/) |
| **`pve3`** | Debian 12 / PVE 8 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | `/etc/modprobe.d/zfs.conf`, `/etc/systemd/system/mnt-pve-backup.mount` | [`nodes/pve3/system-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve3/system-drift/) |

### 2. Virtual Machine OS Drift Audit
| Target VM | Proxmox Node | Discovered Custom VM System Artifacts | VM Drift Audit Directory |
| :--- | :--- | :--- | :--- |
| **`nexus-server` (`VM 100`)** | `pve` | Sudoers permissions (`/etc/sudoers.d/meek2100`), Docker keyrings | [`nodes/pve/vm-100-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve/vm-100-drift/) |
| **`luna-server` (`VM 102`)** | `pve` | `/etc/sysctl.d/99-adguard-udp-buffer.conf` (kernel UDP buffer tweak), `/etc/systemd/system/host-shim.service`, `/root/.ssh/gitwatch_ed25519` | [`nodes/pve/vm-102-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve/vm-102-drift/) |
| **`media-server` (`VM 103`)** | `pve` | `/etc/netplan/50-cloud-init.yaml`, QuickSync iGPU permissions | [`nodes/pve/vm-103-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve/vm-103-drift/) |
| **`vxlan-server` (`VM 107`)** | `pve` | `vxlan-nm.service` daemon, interface `vxlan150`, IP `192.168.1.150` | [`nodes/pve/vm-107-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve/vm-107-drift/) |
| **`minecraft-docker` (`VM 109`)** | `pve` | Bedrock network port mappings | [`nodes/pve/vm-109-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve/vm-109-drift/) |
| **`discovery-server` (`VM 100`)** | `pve2` | Dedicated `10.25.25.246` storage interface, VPN restarter scripts & Gluetun network rules | [`nodes/pve2/vm-100-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve2/vm-100-drift/) |
| **`nexus-server2` (`VM 100`)** | `pve3` | Certbot DNS Cloudflare renewal tokens | [`nodes/pve3/vm-100-drift/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve3/vm-100-drift/) |
| **`nas-server` (`VM 101`)** | `pve3` | OpenMediaVault NAS configuration, `10.25.25.248` NAS interface (`ens19`), `192.168.40.248` management interface (`ens18`) | [`nodes/pve3/vm-101-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve3/vm-101-breakdown.md) |

---

## 📦 Master Portainer Stacks & Host Config Backup Inventory

| Node | Hostname | IP | Host Config Blueprint Directory | Portainer Stacks Backup | Detailed VM Breakdown |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`pve`** | Dell Precision 5520 | `192.168.1.250` | [`nodes/pve/host-configs/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve/host-configs/) | **51 Stacks** across VMs 100, 102, 103, 109 | [`nodes/pve/vm-102-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve/vm-102-breakdown.md) |
| **`pve2`** | Awow AK34Pro | `192.168.1.240` | [`nodes/pve2/host-configs/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve2/host-configs/) | **24 Stacks** across VM 100 | [`nodes/pve2/vm-100-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve2/vm-100-breakdown.md) |
| **`pve3`** | HP EliteDesk | `192.168.1.245` | [`nodes/pve3/host-configs/`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve3/host-configs/) | **7 Stacks** across VM 100 | [`vm-100-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve3/vm-100-breakdown.md), [`vm-101-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/nodes/pve3/vm-101-breakdown.md) |
| **Total** | | | | **82 Stacks** | |

---

## 📁 Repository Directory Structure

```text
homelab-infrastructure/
├── README.md                       # Master network topology, IP map & 82-stack inventory
├── .gitignore                      # Security rules (ignoring .db, .env, data dirs)
├── .agents/
│   ├── AGENTS.md                   # Permanent workspace rules & empirical host matrix
│   ├── mcp.json                    # Workspace MCP server configuration
│   └── paste.md                    # Full historical chat log reference
├── scripts/
│   ├── phase1-readonly-audit.sh    # Non-destructive SSH host discovery tool
│   ├── phase1-vm-docker-audit.sh   # Deep VM OS discovery tool
│   ├── phase1-system-drift-audit.sh# debsums & dpkg host unowned file diff tool
│   ├── phase1-vm-drift-audit.sh    # debsums & dpkg VM unowned file diff tool
│   ├── audit_network_topology.py   # Full network interface & subnet (10.25.25.0/24) audit tool
│   ├── extract_all_stacks.py       # Version-aware Portainer volume stack extractor
│   ├── extract_host_configs.sh     # Host OS configuration file extractor
│   └── generate_all_breakdowns.py  # Container breakdown report generator
├── docs/
│   ├── network-topology-map.md     # Complete multi-subnet (192.168.1.x, 10.25.25.x) network map
│   └── security-backup-guide.md    # SOPS + age single-key secret encryption guide
├── nodes/
│   ├── pve/                        # Dell Precision 5520 Laptop Node (192.168.1.250)
│   │   ├── host-configs/           # grub, interfaces, storage.cfg, qemu-server/, custom-scripts/, setup_gpu_passthrough.sh, nginx/
│   │   ├── system-drift/           # debsums modified-config-files.txt & unowned-user-files.txt
│   │   ├── vm-100-drift/           # VM 100 system drift & unowned files
│   │   ├── vm-102-drift/           # VM 102 system drift & unowned files (host-shim.service, sysctl udp)
│   │   ├── vm-103-drift/           # VM 103 system drift & unowned files
│   │   ├── vm-107-deep-audit.log   # VM 107 vxlan-server audit log & vxlan-nm.service
│   │   ├── vm-107-drift/           # VM 107 system drift & unowned files
│   │   ├── vm-109-drift/           # VM 109 system drift & unowned files
│   │   ├── vm-100-breakdown.md     # VM 100 detailed container report
│   │   ├── vm-102-breakdown.md     # VM 102 detailed container report
│   │   ├── vm-103-breakdown.md     # VM 103 detailed container report
│   │   ├── vm-109-breakdown.md     # VM 109 detailed container report
│   │   ├── portainer-stacks-vm100.log # 8 Portainer stacks backup
│   │   ├── portainer-stacks-vm102.log # 32 Portainer stacks backup
│   │   ├── portainer-stacks-vm103.log # 9 Portainer stacks backup
│   │   └── portainer-stacks-vm109.log # 2 Portainer stacks backup
│   ├── pve2/                       # Awow AK34Pro Mini PC Node (192.168.1.240)
│   │   ├── host-configs/           # grub, interfaces, storage.cfg, qemu-server/
│   │   ├── system-drift/           # debsums modified-config-files.txt & unowned-user-files.txt
│   │   ├── vm-100-drift/           # VM 100 system drift & unowned files
│   │   ├── vm-100-breakdown.md     # VM 100 detailed container report
│   │   └── portainer-stacks-vm100.log # 24 Portainer stacks backup
│   └── pve3/                       # HP EliteDesk Node (192.168.1.245)
│       ├── host-configs/           # grub, interfaces, storage.cfg, qemu-server/
│       ├── system-drift/           # debsums modified-config-files.txt & unowned-user-files.txt
│       ├── vm-100-drift/           # VM 100 system drift & unowned files
│       ├── vm-100-breakdown.md     # VM 100 detailed container report
│       ├── vm-101-deep-audit.log   # VM 101 OMV NAS audit log
│       └── portainer-stacks-vm100.log # 7 Portainer stacks backup
└── .phase2-stash/                  # Stashed Phase 2 draft configurations & notes
```
