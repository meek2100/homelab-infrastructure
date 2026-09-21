# Homelab Workspace Rules & Operating Guidelines

## Phase 1 Operating Principles (Read-Only Audit & Zero-Trust Backup)
- **Zero Modifications in Phase 1**: All 3 Proxmox hosts (`pve`, `pve2`, `pve3`), VMs, Docker stacks, and network routes are working. No configuration file changes or container modifications will be executed until Phase 1 read-only audits and encrypted restoration blueprints are complete and approved.
- **Background Command Execution**: When `run_command` transitions to a background task while waiting for user approval:
  - Do NOT cancel or call `manage_task kill` on the task simply because it is waiting for user approval.
  - Allow the user to approve the command in the UI at their own pace.
  - Trust the system notification mechanism to deliver stdout/stderr logs automatically once the task completes after approval.
- **Synchronous Wait Threshold**: Use an adequate `WaitMsBeforeAsync` threshold (5000–10000ms) for commands intended to run synchronously.

## Technical Learnings & Backup Gotchas
- **QEMU Guest Agent (QGA) Binary Corruption**: When using `qm guest exec` to extract files from VMs, the output is returned in a JSON envelope (`{"out-data": "..."}`). Directly piping this to a file irreversibly corrupts binary files (like Docker SQLite `.db` files). You MUST run `base64 -w 0` inside the VM, parse the JSON, and `base64.b64decode()` in Python.
- **QGA Stdin Hangs & Base64 Payload Streaming**: Passing raw text or stdin into `qm guest exec` with `--pass-stdin 1` is unreliable and frequently hangs without an interactive TTY. All files (compose files, environment secrets) should be base64-encoded on the host and decoded inside the guest with `echo '<b64>' | base64 -d > <target_file>`.
- **Docker Compose Container Conflicts**: When re-deploying stacks with explicit container names (`container_name: ...`), pre-existing exited containers must be cleaned up (`docker rm`) or Docker Compose will exit with a container name conflict. `restore-docker-stacks.py` captures inner QGA `exitcode` and outputs `err-data` directly.
- **File Metadata & Permissions Gap**: Pulling file contents via QGA or `cat` entirely strips file permissions (`chmod`) and ownership (`chown`). If a Docker container database is restored as `root:root` instead of the required container UID (e.g., UID 1000), the container will crash with `Permission Denied`. Metadata must be explicitly captured via `stat -c '%a:%u:%g'` and re-applied during restoration.
- **Git Push Limits & DPkG Drift**: The dpkg "unowned files" audit technique is powerful but will indiscriminately grab heavily compiled userspace toolchains (like `.rustup` or `.cargo` installed via `curl`). These must be strictly pruned via `find ... -prune`, otherwise 100MB+ `.so` files will permanently jam GitHub repository pushes.

## Architecture & Topology Guidelines
- **Topology**: All 3 Proxmox nodes (`pve`, `pve2`, `pve3`) operate as **Standalone Hosts** (NO PVE Cluster) to eliminate cluster quorum failure risks if a node reboots or enters a restricted VPN state.
- **Subnets & Routing**:
  - `192.168.1.0/24`: Primary Management & Egress LAN
  - `10.25.25.0/24`: Dedicated High-Speed Private NAS Storage Network (`vmbr1` across hosts, `10.25.25.248` on `nas-server`, `10.25.25.246` on `discovery-server`)
  - `192.168.40.0/24` & `192.168.50.0/24`: IoT & Security VLANs
- **Virtualization Strategy**: Use **Full Virtual Machines (VMs)** for all Docker/Portainer hosts. Do NOT run Docker inside unprivileged LXC containers to avoid overlay2 storage driver bugs, permission errors, and update breakages.
- **Central Repository**: This repository (`homelab-infrastructure`) serves as the single source of truth for all 3 nodes, network routing, DNS configurations, and stack templates.

## Empirical Host & Service Matrix (83 Portainer Stacks Backed Up)

### Node 1: `pve` (Dell Precision 5520 Laptop Profile — `192.168.1.250`)
- **Hardware**: Intel Xeon E3-1505M v6 (4C/8T), 32GB RAM, 1TB Toshiba NVMe + 2x 1TB WD 2.5" Disks.
  - `vmbr0` (`192.168.1.250/24` on `lan0` / Dell DBQBCBC064, MAC `9c:eb:e8:96:11:44`): Primary management & VLAN trunk
  - `vmbr1` (on `lan1` / Dell DA200, MAC `00:24:9b:55:a0:49`, promiscuous mode on): Dedicated Wireshark SPAN packet capture bridge (mapped to VM 102 `tap102i1`)
- **GPUs**:
  - Intel HD P630 (`00:02.0`): Assigned as `hostpci0: 0000:00:02` in `VM 103` (`media-server` for Plex QuickSync).
  - NVIDIA Quadro M1200 4GB (`[10de:13b6]` / `01:00.0`): Currently **100% unmapped / idle** on host `pve`.
- **Lid & Power Fixes**: Proxmox systemd `HandleLidSwitch=ignore`; ACPI lid script `/etc/acpi/lid-backlight.sh` toggles Intel panel backlight to 0 on close, 400 on open.
- **Active Virtual Machines**:
  - `VM 100` (`nexus-server` Ingress VM): **9 Portainer Stacks** (`nginx-proxy-manager`, `cloudflared`, `adguardhome` secondary, `adguardhome-sync`, `wg-easy`, `rustdesk`, `tailscale` subnet router Stack 69, `openspeedtest` Stack 70, etc.)
  - `VM 102` (`luna-server` Smart Home VM): **32 Portainer Stacks** (`homeassistant`, `homebridge`, `syncthing`, `spoolman`, `gitwatch`, etc.)
  - `VM 103` (`media-server` Media VM): **9 Portainer Stacks** (`plex`, `audiobookshelf`, `homarr`, `overseerr`, `calibre-web`, `filebrowser`, etc.)
  - `VM 107` (`vxlan-server` Network Bridge VM): `vxlan-nm.service` daemon on IP `192.168.1.150` (bridging interface `vxlan150`).
  - `VM 109` (`minecraft-docker` Gaming VM): **2 Portainer Stacks** (`mcbd-connect`, `mcbd-proxy`, etc.)

### Node 2: `pve2` (Awow AK34Pro Mini PC Profile — `192.168.1.240`)
- **Hardware**: Intel Celeron J3455 (4C/4T), 6GB RAM.
- **Network Bridges**: `vmbr0` (`192.168.1.240`), `vmbr0.40`, `vmbr0.50`, `vmbr1` (`10.25.25.240`).
- **Backed Up Portainer VM Stacks**:
  - `VM 100` (`discovery-server` Download VM): **24 Portainer Stacks** (2 Active: `audiobookbay-automated-dev` VPN master stack, `watchtower`; 22 Inactive/historical stacks).
  - **Active Container Infrastructure**:
    - `audiobookbay-automated-dev`: 7 Containers (`gluetun` VPN gateway, `qbittorrent`, `qbittorrent-porthelper`, `firefox`, `audiobookbay-downloader-dev`, `autoheal`, `vpn-restarter`).
    - `watchtower`: `watchtower` container.
    - `portainer`: Standalone unstacked UI (`portainer/portainer-ce:latest` on ports 8000/9443).
    - **Storage Interface**: `ens18` on IP **`10.25.25.246/24`** connecting directly to `nas-server` (`10.25.25.248`).

### Node 3: `pve3` (HP EliteDesk Profile — `192.168.1.245`)
- **Hardware**: HP EliteDesk Node, 16GB RAM.
- **Role**: Primary DNS & Core NAS Storage Array.
- **Network Bridges**: `vmbr0` (`192.168.1.245`), `vmbr1` (`10.25.25.245`).
- **Backed Up Portainer VM Stacks**:
  - `VM 100` (`nexus-server2` Primary DNS VM): **7 Portainer Stacks** (2 Active: `adguardhome` v36, `watchtower` v8; 5 Inactive: `cloudflare-ddns` v3, `cloudflared` v1, `nginx-proxy-manager` v9, `pi-hole` v2, `wireguard-easy` v20).
  - **Active Containers**: `adguardhome`, `adguardhome-certbot` (`172.19.0.2`), `watchtower` (`172.18.0.3`), `portainer` (`172.17.0.2`).
  - `VM 101` (`nas-server` NAS VM): `OpenMediaVault` on 500GB disk `shared-nas:vm-101-disk-0` with **`ens19` IP `10.25.25.248/24`** (Private Storage Network) and **`ens18` IP `192.168.40.248/24`** (VLAN 40 Management).

## MCP & Tool Standards
- Keep Model Context Protocol (MCP) servers modular in `mcp/` and reference project-level MCP tools in `.agents/mcp_config.json`.
- Secret Backup Standard: Encrypt all secrets using `SOPS` + `age` (`*.enc.yaml`). Keep master key in user password manager; no unencrypted secrets in Git.
- **Snapshot & Backup Tooling (VM & LXC Support)**:
  - `mcp/homelab/scripts/manage-vm-snapshots.py`: Programmatic snapshot creation, listing, rollback, deletion, and vzdump backup with automatic detection for both QEMU VMs (`qm`) and Linux Containers (`pct`).
  - Native FastMCP tools: `snapshot_vm`, `list_vm_snapshots`, `rollback_vm`, `delete_vm_snapshot`, `backup_vm_vzdump`, `list_vms`, `get_docker_status`.
- **Network Infrastructure & GitOps Tooling**:
  - `infrastructure/network/vlan-matrix.md`: Authoritative 8-VLAN table (VLAN 1 Management, 10 Main Trusted, 20 Guest Media, 30 Isolated IOT, 40 Servers Admin, 100 Wireshark Debug, 150 CA-1 Test, 200 Core-5 Test).
  - `infrastructure/network/network-topology.md`: Dual-WAN topology (WAN1 house LAN, WAN2 `10.25.25.0/24` egress for `discovery-server`), Araknis 520 router, 920 switch, 830 APs, and DNS split-horizon.
  - `mcp/homelab/scripts/manage-araknis-switch.py`: FastMCP tools `backup_araknis_switch`, `get_araknis_switch_status`, `power_cycle_switch_poe_port` via interactive FASTPATH SSH automation.
  - `mcp/homelab/scripts/manage-araknis-router.py`: FastMCP tools `backup_araknis_router`, `get_araknis_router_status`, `restore_araknis_router` via authenticated REST API (`/api/cgi-bin/v1/`).
  - `mcp/homelab/scripts/backup-openwrt-config.py`: FastMCP tool `backup_openwrt` pulls and SOPS-encrypts OpenWrt `/etc/config/`.
  - `mcp/homelab/scripts/sync-wireshark-capture-script.py`: FastMCP tool `sync_wireshark_capture` archives headless capture scripts from `luna-server` (VM 102) into Stack 48.

## Araknis 520 Router REST API — Technical Reference
- **Auth Mechanism**: HTTP Basic Auth via `GET /api/cgi-bin/v1/authorize` with `Authorization: Basic base64(user:pass)` header. Returns `302` on success, `401` on failure. NO session cookies — send the `Authorization` header on every request.
- **Base URL**: `http://192.168.1.1/api/cgi-bin/v1/`
- **Discovery method**: Chrome DevTools XHR/fetch breakpoint on "authorize" while logging in revealed the React SPA sends `GET` (not `POST`) with Basic Auth header, not form data.
- **Backup format**: `GET /command/export-config` returns HTTP `201` with a base64-encoded OpenSSL-encrypted config blob (`Salted__` prefix). Restore via `POST /command/restore-config` with the blob as body.
- **Known working endpoints**: `/config/lan/subnets`, `/config/wan`, `/status/wan`, `/status/ports`, `/status/system/system-information`, `/status/system/stats`, `/config/firewall`, `/config/lan/dhcp-reservation`, `/config/acls`, `/command/export-config`, `/command/restore-config`.
- **Timed-out endpoints (avoid)**: `/config/firewall/interzone` — hangs indefinitely, use 2s timeout.
- **VLAN DNS**: All 8 VLANs use `192.168.40.185` (nexus-server AdGuard) and `192.168.40.186` (nexus-server2 AdGuard) as DHCP-assigned DNS servers.
- **Config backup file**: `infrastructure/network/configs/araknis-520-backup.cfg` (19K encrypted blob).
