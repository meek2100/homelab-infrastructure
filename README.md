# 🛠️ Central Homelab Inventory & Control Tower

This repository holds the absolute source of truth for our three isolated standalone Proxmox VE hosts (`pve`, `pve2`, `pve3`). The hosts are deliberately not clustered to prevent network cascading failures if a node reboots or enters a restricted VPN state.

---

## 🛜 Network Subnet & Routing Topology Map

Full empirical topology map generated in [`docs/architecture/network-interfaces-map.md`](file:///home/agentsvc/repos/homelab-infrastructure/docs/architecture/network-interfaces-map.md) and architectural blueprint in [`docs/architecture/network-topology.md`](file:///home/agentsvc/repos/homelab-infrastructure/docs/architecture/network-topology.md):

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
| Node | Installation Marker | Package Config Drift (`debsums -ce`) | Unowned User Artifacts Discovered | System Drift Directory |
| :--- | :--- | :--- | :--- | :--- |
| **`pve`** | Debian 12 / PVE 8 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | `/root/setup_gpu_passthrough.sh`, `/root/generate_nginx_configs.sh`, `/root/.secrets/certbot/`, `/etc/nginx/conf.d/*.conf` (30+ Nginx proxy hosts), `/usr/local/bin/mount-backup-drive.sh`, `/usr/local/bin/sysprep.sh` | [`infrastructure/hosts/pve/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/hosts/pve/drift/) |
| **`pve2`** | Debian 12 / PVE 8 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | Proxmox storage definitions & Portainer CE volumes | [`infrastructure/hosts/pve2/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/hosts/pve2/drift/) |
| **`pve3`** | Debian 12 / PVE 8 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | `/etc/modprobe.d/zfs.conf`, `/etc/systemd/system/mnt-pve-backup.mount` | [`infrastructure/hosts/pve3/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/hosts/pve3/drift/) |

### 2. Virtual Machine OS Drift Audit
| Target VM | Proxmox Node | Discovered Custom VM System Artifacts | VM Drift Directory | Breakdown Report |
| :--- | :--- | :--- | :--- | :--- |
| **`nexus-server` (`VM 100`)** | `pve` | Sudoers permissions (`/etc/sudoers.d/meek2100`), Docker keyrings | [`infrastructure/vms/pve-100-nexus-server/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-100-nexus-server/drift/) | [`vm-100-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-100-nexus-server/vm-100-breakdown.md) |
| **`luna-server` (`VM 102`)** | `pve` | `/etc/sysctl.d/99-adguard-udp-buffer.conf` (kernel UDP buffer tweak), `/etc/systemd/system/host-shim.service`, `/root/.ssh/gitwatch_ed25519` | [`infrastructure/vms/pve-102-luna-server/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-102-luna-server/drift/) | [`vm-102-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-102-luna-server/vm-102-breakdown.md) |
| **`media-server` (`VM 103`)** | `pve` | `/etc/netplan/50-cloud-init.yaml`, QuickSync iGPU permissions | [`infrastructure/vms/pve-103-media-server/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-103-media-server/drift/) | [`vm-103-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-103-media-server/vm-103-breakdown.md) |
| **`vxlan-server` (`VM 107`)** | `pve` | `vxlan-nm.service` daemon, interface `vxlan150`, IP `192.168.1.150` | [`infrastructure/vms/pve-107-vxlan-server/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-107-vxlan-server/drift/) | [`vm-107-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-107-vxlan-server/vm-107-breakdown.md) |
| **`minecraft-docker` (`VM 109`)** | `pve` | Bedrock network port mappings | [`infrastructure/vms/pve-109-minecraft-docker/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-109-minecraft-docker/drift/) | [`vm-109-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-109-minecraft-docker/vm-109-breakdown.md) |
| **`discovery-server` (`VM 100`)** | `pve2` | Dedicated `10.25.25.246` storage interface, VPN restarter scripts & Gluetun network rules | [`infrastructure/vms/pve2-100-discovery-server/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve2-100-discovery-server/drift/) | [`vm-100-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve2-100-discovery-server/vm-100-breakdown.md) |
| **`nexus-server2` (`VM 100`)** | `pve3` | Certbot DNS Cloudflare renewal tokens | [`infrastructure/vms/pve3-100-nexus-server2/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve3-100-nexus-server2/drift/) | [`vm-100-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve3-100-nexus-server2/vm-100-breakdown.md) |
| **`nas-server` (`VM 101`)** | `pve3` | OpenMediaVault NAS configuration, `10.25.25.248` NAS interface (`ens19`), `192.168.40.248` management interface (`ens18`) | [`infrastructure/vms/pve3-101-nas-server/drift/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve3-101-nas-server/drift/) | [`vm-101-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve3-101-nas-server/vm-101-breakdown.md) |

---

## 📦 Master Portainer Stacks & Host Config Backup Inventory

Full service catalog and container port mapping available in [`infrastructure/docker-stacks/STACK-INDEX.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/STACK-INDEX.md):

| Node | Hostname | IP | Host Config Directory | Portainer Stacks Backup | Detailed Breakdown |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`pve`** | Dell Precision 5520 | `192.168.1.250` | [`infrastructure/hosts/pve/configs/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/hosts/pve/configs/) | **52 Stacks** ([`luna`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/luna-server/): 32, [`media`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/media-server/): 9, [`nexus`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/): 9, [`mc`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/minecraft-docker/): 2) | [`vm-102-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve-102-luna-server/vm-102-breakdown.md) |
| **`pve2`** | Awow AK34Pro | `192.168.1.240` | [`infrastructure/hosts/pve2/configs/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/hosts/pve2/configs/) | **24 Stacks** ([`discovery-server`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/discovery-server/): 24) | [`vm-100-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve2-100-discovery-server/vm-100-breakdown.md) |
| **`pve3`** | HP EliteDesk | `192.168.1.245` | [`infrastructure/hosts/pve3/configs/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/hosts/pve3/configs/) | **7 Stacks** ([`nexus-server2`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server2/): 7) | [`vm-100-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve3-100-nexus-server2/vm-100-breakdown.md), [`vm-101-breakdown.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/vms/pve3-101-nas-server/vm-101-breakdown.md) |
| **Total** | | | | **83 Stacks** | See [`STACK-INDEX.md`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/STACK-INDEX.md) |

---

## 📁 Repository Directory Structure

```text
homelab-infrastructure/
├── README.md                       # Master network topology, IP map & 83-stack inventory
├── AGENTS.md                       # Permanent workspace rules & empirical host matrix
├── .gitignore                      # Security rules (ignoring .key, .venv, .agents, .db)
├── .sops.yaml                      # SOPS single master age public key encryption rules
├── docs/                           # Master documentation library (architecture, runbooks, specs, roadmaps)
│   ├── README.md                   # Master documentation catalog & navigation index
│   ├── architecture/               # Network topology, 8-VLAN matrix, interface maps
│   ├── runbooks/                   # Network automation (NSDP/Wireshark), bare-metal recovery, secrets
│   ├── specifications/             # Netgear GS108Ev2 NSDP protocol specification
│   └── roadmaps/                   # Network implementation plan & status tracking
├── infrastructure/
│   ├── docker-stacks/              # 83 versioned Portainer stacks & deploy metadata
│   │   ├── STACK-INDEX.md          # Master catalog mapping stack IDs to services & ports
│   │   ├── discovery-server/       # 24 stacks (VPN download gateway, autoheal, qbittorrent)
│   │   ├── luna-server/            # 32 stacks (Home Assistant, Homebridge, Syncthing)
│   │   ├── media-server/           # 9 stacks (Plex, Overseerr, Audiobookshelf, Calibre)
│   │   ├── minecraft-docker/       # 2 stacks (Bedrock connect & proxy)
│   │   ├── nexus-server/           # 9 stacks (Nginx Proxy Manager, Cloudflared, WireGuard, Tailscale)
│   │   └── nexus-server2/          # 7 stacks (AdGuard Home primary DNS, Cloudflare DDNS)
│   ├── hosts/                      # Physical Proxmox host configurations and system drift
│   │   ├── pve/                    # Dell Precision 5520 Node (192.168.1.250)
│   │   ├── pve2/                   # Awow AK34Pro Mini PC Node (192.168.1.240)
│   │   └── pve3/                   # HP EliteDesk Node (192.168.1.245)
│   └── vms/                        # Virtual Machine hardware definitions and drift audits
│       ├── pve-100-nexus-server/
│       ├── pve-102-luna-server/
│       ├── pve-103-media-server/
│       ├── pve-107-vxlan-server/
│       ├── pve-109-minecraft-docker/
│       ├── pve2-100-discovery-server/
│       ├── pve3-100-nexus-server2/
│       └── pve3-101-nas-server/
├── mcp/
│   └── homelab/                    # Homelab infrastructure & recovery FastMCP server
│       ├── server.py               # Recovery, discovery & sync tools (sync_fleet, backup, restore)
│       └── scripts/                # Automated audit, extraction, sync, and restore tools

└── .agents/                        # Local working directory (untracked in Git)
    └── docs/
        ├── session-state.md        # Live project session & master TODO tracker
        └── history.md              # Historical context archive
```
