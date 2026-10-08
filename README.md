# 🛠️ Central Homelab Inventory & Control Tower

This repository holds the absolute source of truth for our three isolated standalone Proxmox VE 9.1.1 hosts (`pve`, `pve2`, `pve3`). The hosts are deliberately not clustered to eliminate quorum cascading failure risks if a node reboots or enters a restricted VPN state.

---

## 🛜 Network Subnet & Routing Topology Map

Full empirical topology map generated in [`docs/architecture/network-interfaces-map.md`](docs/architecture/network-interfaces-map.md) and architectural blueprint in [`docs/architecture/network-topology.md`](docs/architecture/network-topology.md):

* **1. Primary Management & Service LAN (`192.168.1.0/24` — VLAN 1)**:
  - `pve`: `192.168.1.250` (`vmbr0` on `lan0` / Dell DBQBCBC064)
  - `pve2`: `192.168.1.240` (`vmbr0` on `enp1s0`)
  - `pve3`: `192.168.1.245` (`vmbr0`)
  - `nexus-server` (`VM 100` on `pve`): `192.168.1.185` (Primary Ingress / NPM / Cloudflare / WireGuard)
  - `nexus-server2` (`VM 100` on `pve3`): `192.168.1.186` (Primary DNS / AdGuard Home)
  - `vxlan-server` (`VM 107` on `pve`): `192.168.1.150` (`vxlan-nm.service` bridging interface `vxlan150`)
  - `pbs-server` (`LXC 105` on `pve3`): `192.168.1.244` (`vmbr0` — Proxmox Backup Server)

* **2. Dedicated Private High-Speed NAS Storage LAN (`10.25.25.0/24`)**:
  - `pve`: `10.25.25.250/24` (`vmbr1`)
  - `pve2`: `10.25.25.240/24` (`vmbr1` on `enp2s0`)
  - `pve3`: `10.25.25.245/24` (`vmbr1`)
  - **`nas-server` (`VM 101` on `pve3`)**: **`10.25.25.248/24`** (`ens19` — OpenMediaVault Core NAS Array)
  - **`discovery-server` (`VM 100` on `pve2`)**: **`10.25.25.246/24`** (`ens18` — VPN Download Gateway with direct NAS storage interface)
  - **`pbs-server` (`LXC 105` on `pve3`)**: **`10.25.25.244/24`** (`eth1` on `vmbr1` — High-speed deduplicated backup datastore)

* **3. Server & Infrastructure Management VLAN (`192.168.40.0/24` — VLAN 40)**:
  - `nexus-server` (`VM 100` on `pve`): `192.168.40.185` (AdGuard Secondary DNS & Ingress Management)
  - `nexus-server2` (`VM 100` on `pve3`): `192.168.40.186` (AdGuard Primary DNS Management)
  - `luna-server` (`VM 102` on `pve`): `192.168.40.249` (`ens18` — Home Automation Controller)
  - `nas-server` (`VM 101` on `pve3`): `192.168.40.248` (`ens18` — OMV Web & Management Interface)
  - *(Note: `pve2` operates on untagged VLAN 1 only with no VLAN sub-interfaces; legacy VLAN 50 was abolished during the network reorganization).*

---

## 🔬 System Drift & Unowned Files Audit Matrix (Hosts & Guests)

Using `debsums -ce` and `dpkg` set-differencing (`comm -23 actual packaged`), 100% of system configuration changes and user-added files since base OS installation have been audited across Proxmox hosts, Virtual Machines, and Containers:

### 1. Physical Proxmox Host OS Drift Audit
| Node | Installation Marker | Package Config Drift (`debsums -ce`) | Unowned User Artifacts Discovered | System Drift Directory |
| :--- | :--- | :--- | :--- | :--- |
| **`pve`** | Debian 13 / PVE 9.1.1 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | `/root/setup_gpu_passthrough.sh`, `/root/generate_nginx_configs.sh`, `/root/.secrets/certbot/`, `/etc/nginx/conf.d/*.conf`, `/usr/local/bin/mount-backup-drive.sh`, `/usr/local/bin/sysprep.sh` | [`infrastructure/hosts/pve/drift/`](infrastructure/hosts/pve/drift/) |
| **`pve2`** | Debian 13 / PVE 9.1.1 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | Proxmox storage definitions & Portainer CE volumes | [`infrastructure/hosts/pve2/drift/`](infrastructure/hosts/pve2/drift/) |
| **`pve3`** | Debian 13 / PVE 9.1.1 | `/etc/issue`, `/etc/lvm/lvm.conf`, `/etc/apt/sources.list.d/pve-enterprise.sources` | `/etc/modprobe.d/zfs.conf`, `/etc/systemd/system/mnt-pve-backup.mount` | [`infrastructure/hosts/pve3/drift/`](infrastructure/hosts/pve3/drift/) |

### 2. Guest OS (VM & Container) Drift Audit
| Target Guest | Node | Type | Discovered Custom System Artifacts | Guest Drift Directory |
| :--- | :--- | :--- | :--- | :--- |
| **`nexus-server` (`VM 100`)** | `pve` | QEMU VM | Sudoers permissions (`/etc/sudoers.d/meek2100`), Docker keyrings | [`infrastructure/vms/pve-100-nexus-server/drift/`](infrastructure/vms/pve-100-nexus-server/drift/) |
| **`luna-server` (`VM 102`)** | `pve` | QEMU VM | `/etc/sysctl.d/99-adguard-udp-buffer.conf`, `/etc/systemd/system/host-shim.service`, `/root/.ssh/gitwatch_ed25519` | [`infrastructure/vms/pve-102-luna-server/drift/`](infrastructure/vms/pve-102-luna-server/drift/) |
| **`media-server` (`VM 103`)** | `pve` | QEMU VM | `/etc/netplan/50-cloud-init.yaml`, QuickSync iGPU permissions (`00:02.0`) | [`infrastructure/vms/pve-103-media-server/drift/`](infrastructure/vms/pve-103-media-server/drift/) |
| **`vxlan-server` (`VM 107`)** | `pve` | QEMU VM | `vxlan-nm.service` daemon, interface `vxlan150`, IP `192.168.1.150` | [`infrastructure/vms/pve-107-vxlan-server/drift/`](infrastructure/vms/pve-107-vxlan-server/drift/) |
| **`minecraft-server` (`VM 109`)**| `pve` | QEMU VM | Bedrock network port mappings | [`infrastructure/vms/pve-109-minecraft-server/drift/`](infrastructure/vms/pve-109-minecraft-server/drift/) |
| **`discovery-server` (`VM 100`)**| `pve2` | QEMU VM | Dedicated `10.25.25.246` storage interface, VPN restarter scripts & Gluetun rules | [`infrastructure/vms/pve2-100-discovery-server/drift/`](infrastructure/vms/pve2-100-discovery-server/drift/) |
| **`nexus-server2` (`VM 100`)** | `pve3` | QEMU VM | Certbot DNS Cloudflare renewal tokens | [`infrastructure/vms/pve3-100-nexus-server2/drift/`](infrastructure/vms/pve3-100-nexus-server2/drift/) |
| **`nas-server` (`VM 101`)** | `pve3` | QEMU VM | OpenMediaVault NAS configuration, `10.25.25.248` NAS interface (`ens19`), `192.168.40.248` (`ens18`) | [`infrastructure/vms/pve3-101-nas-server/drift/`](infrastructure/vms/pve3-101-nas-server/drift/) |
| **`pbs-server` (`LXC 105`)** | `pve3` | LXC Container | Proxmox Backup Server datastore, SAN interface `10.25.25.244`, LAN `192.168.1.244` | [`infrastructure/vms/pve3-105-pbs-server/`](infrastructure/vms/pve3-105-pbs-server/) |

---

## 📦 Master Portainer Stacks & Host Config Backup Inventory

Full service catalog and container port mapping available in [`infrastructure/docker-stacks/STACK-INDEX.md`](infrastructure/docker-stacks/STACK-INDEX.md):

| Node | Hostname | IP | Host Config Directory | Portainer Stacks Backup | Detailed Breakdown |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`pve`** | Dell Precision 5520 | `192.168.1.250` | [`infrastructure/hosts/pve/configs/`](infrastructure/hosts/pve/configs/) | **59 Stacks** ([`luna`](infrastructure/docker-stacks/luna-server/): 34, [`media`](infrastructure/docker-stacks/media-server/): 10, [`nexus`](infrastructure/docker-stacks/nexus-server/): 12, [`mc`](infrastructure/docker-stacks/minecraft-server/): 3) | [`vm-102-breakdown.md`](infrastructure/vms/pve-102-luna-server/vm-102-breakdown.md) |
| **`pve2`** | Awow AK34Pro | `192.168.1.240` | [`infrastructure/hosts/pve2/configs/`](infrastructure/hosts/pve2/configs/) | **24 Stacks** ([`discovery-server`](infrastructure/docker-stacks/discovery-server/): 24) | [`vm-100-breakdown.md`](infrastructure/vms/pve2-100-discovery-server/vm-100-breakdown.md) |
| **`pve3`** | HP EliteDesk | `192.168.1.245` | [`infrastructure/hosts/pve3/configs/`](infrastructure/hosts/pve3/configs/) | **8 Stacks** ([`nexus-server2`](infrastructure/docker-stacks/nexus-server2/): 8) | [`vm-100-breakdown.md`](infrastructure/vms/pve3-100-nexus-server2/vm-100-breakdown.md), [`vm-101-breakdown.md`](infrastructure/vms/pve3-101-nas-server/vm-101-breakdown.md) |
| **Total** | | | | **91 Stacks (188 Services)** | See [`STACK-INDEX.md`](infrastructure/docker-stacks/STACK-INDEX.md) |

---

## 📁 Repository Directory Structure

```text
homelab-infrastructure/
├── README.md                       # Master network topology, IP map & 91-stack inventory
├── AGENTS.md                       # Concise workspace rules, boundaries & verified commands
├── .gitignore                      # Security rules (ignoring .key, .venv, .agents, .db)
├── .sops.yaml                      # SOPS single master age public key encryption rules
├── docs/                           # Master documentation library (architecture, runbooks, specs, roadmaps)
│   ├── README.md                   # Master documentation catalog & navigation index
│   ├── architecture/               # Network topology, 8-VLAN matrix, interface maps
│   ├── runbooks/                   # Network automation (NSDP/Wireshark), recovery, secrets, PBS
│   ├── specifications/             # Netgear GS108Ev2 NSDP protocol specification
│   └── roadmaps/                   # Network implementation plan, PCAP remediations & checkpoints
├── infrastructure/
│   ├── docker-stacks/              # 91 versioned Portainer stacks & deploy metadata (188 services)
│   │   ├── STACK-INDEX.md          # Master catalog mapping stack IDs to services, ports & secrets
│   │   ├── discovery-server/       # 24 stacks (VPN download gateway, autoheal, qbittorrent)
│   │   ├── luna-server/            # 34 stacks (Home Assistant, Homebridge, Syncthing, Wireshark)
│   │   ├── media-server/           # 9 stacks (Plex, Overseerr, Audiobookshelf, Calibre)
│   │   ├── minecraft-server/       # 2 stacks (Bedrock connect & proxy)
│   │   ├── nexus-server/           # 9 stacks (Nginx Proxy Manager, Cloudflared, WireGuard, Observability)
│   │   └── nexus-server2/          # 13 stacks (AdGuard Home primary DNS, Cloudflare DDNS)
│   ├── hosts/                      # Physical Proxmox host configurations and system drift
│   │   ├── pve/                    # Dell Precision 5520 Node (192.168.1.250)
│   │   ├── pve2/                   # Awow AK34Pro Mini PC Node (192.168.1.240)
│   │   └── pve3/                   # HP EliteDesk Node (192.168.1.245)
│   ├── network/                    # Authoritative network hardware configurations & backups
│   │   └── configs/                # Araknis 520, Araknis 920, Pakedge SX-8P, Netgear, DD-WRT, OpenWrt
│   └── vms/                        # Guest definitions, drift audits & blueprints (8 VMs + LXC 105)
│       ├── pve-100-nexus-server/
│       ├── pve-102-luna-server/
│       ├── pve-103-media-server/
│       ├── pve-107-vxlan-server/
│       ├── pve-109-minecraft-server/
│       ├── pve2-100-discovery-server/
│       ├── pve3-100-nexus-server2/
│       ├── pve3-101-nas-server/
│       └── pve3-105-pbs-server/
└── mcp/
    └── homelab/                    # Homelab infrastructure FastMCP server (20 action-oriented tools)
        ├── server.py               # FastMCP server entrypoint & tool registry
        └── scripts/                # Automated audit, extraction, sync, NSDP, and matrix tools
```
