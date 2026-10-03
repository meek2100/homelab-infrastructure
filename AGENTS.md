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
  - `VM 100` (`nexus-server` Ingress VM): **9 Portainer Stacks + Stack 71 Observability Stack** (`nginx-proxy-manager`, `cloudflared`, `adguardhome` secondary, `adguardhome-sync`, `wg-easy`, `rustdesk`, `tailscale` subnet router Stack 69, `openspeedtest` Stack 70, `prometheus`, `grafana` :3030, `loki` :3100, `promtail`, `pve-exporter` :9221, `snmp-exporter` :9116, `node-exporter` :9100, `cadvisor` :8088)
  - `VM 102` (`luna-server` Smart Home VM): **32 Portainer Stacks** (`homeassistant`, `homebridge`, `syncthing`, `spoolman`, `gitwatch`, etc.)
  - `VM 103` (`media-server` Media VM): **9 Portainer Stacks** (`plex`, `audiobookshelf`, `homarr`, `overseerr`, `calibre-web`, `filebrowser`, etc.)
  - `VM 107` (`vxlan-server` Network Bridge VM): `vxlan-nm.service` daemon on IP `192.168.1.150` (bridging interface `vxlan150`).
  - `VM 109` (`minecraft-server` Gaming VM): **2 Portainer Stacks** (`mcbd-connect`, `mcbd-proxy`, etc.)

### Node 2: `pve2` (Awow AK34Pro Mini PC Profile — `192.168.1.240`)
- **Hardware**: Intel Celeron J3455 (4C/4T), 6GB RAM.
- **Network Bridges**: `vmbr0` (`192.168.1.240` on `enp1s0`, untagged VLAN 1 management only — no VLAN sub-interfaces, verified 2026-09-30), `vmbr1` (`10.25.25.240` on `enp2s0`, storage network; VM 100 attaches only here).
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
- Master Tool Definition: `mcp/homelab/server.py` implements the FastMCP server (`Homelab Infrastructure System`), bundling 48 native tools covering hypervisors, containers, switching, routing, and external services.

### Bundled FastMCP Tool Catalog (`mcp/homelab/server.py`)

#### 1. Fleet Discovery, Blueprints & Drift Management
- `sync_fleet(node, vmid, apply, diff_only)`: Discovers and synchronizes live Proxmox host configs, VM configs, and Portainer stacks into GitOps blueprints (`sync-live-fleet.py`).
- `generate_stack_index()`: Rebuilds `infrastructure/docker-stacks/STACK-INDEX.md` mapping all 83 stacks, services, and SOPS secret states.
- `audit_infrastructure()`: Runs Phase 1 system, VM, and host configuration audits across nodes (`pve`, `pve2`, `pve3`).
- `register_host(node, ip)` / `register_vm(node, vmid, name)`: Registers host and VM metadata under `infrastructure/`.

#### 2. Proxmox Host, VM & Container Lifecycle
- `list_vms(node)`: Lists all QEMU VMs (`qm list`) and LXC containers (`pct list`) across nodes.
- `get_docker_status(node, vmid)`: Inspects live Docker containers via QEMU Guest Agent (`qm guest exec`) or `pct exec`.
- `snapshot_vm(node, vmid, name, description, include_ram)`: Creates atomic live snapshot for QEMU VM or LXC container (`manage-vm-snapshots.py`).
- `list_vm_snapshots(node, vmid)`: Lists existing snapshots for a VM/CT.
- `rollback_vm(node, vmid, name)`: Rolls back a VM/CT to a snapshot.
- `delete_vm_snapshot(node, vmid, name)`: Prunes a VM/CT snapshot.
- `backup_vm_vzdump(node, vmid, storage)`: Triggers a full Proxmox `vzdump` backup archive.
- `start_vm(node, vmid)` / `stop_vm(node, vmid)`: Starts or gracefully stops a VM or LXC container.

#### 3. Disaster Recovery & Zero-Trust State Blueprints
- `backup_host(node)` / `restore_host(node, dry_run)` / `restore_host_configs(node, dry_run)`: Backs up custom host files and restores host configurations/drifts.
- `backup_vm(node, vmid)` / `restore_vm(node, vmid, dry_run)`: Backs up and restores VM custom drift files.
- `backup_stacks()` / `restore_stacks(node, vmid, stack, dry_run)` / `start_docker_stacks(node, vmid, dry_run)`: Splits, decrypts SOPS secrets (`secrets.enc.yaml`), and deploys/starts Portainer stacks.
- `backup_apt_packages(node, vmid)` / `restore_apt_packages(node, vmid, dry_run)`: Audits and restores APT package installations across nodes and guests.

#### 4. Switch & Core Network Automation
- **Araknis 920 Switch (`192.168.1.215`)**:
  - `get_araknis_switch_status()`: Queries live ports, link speeds, learned MAC tables, RSTP status, and IGMP querier state via FASTPATH SSH.
  - `backup_araknis_switch()`: Pulls sanitized running-config into `infrastructure/network/configs/araknis-920-running.cfg`.
  - `power_cycle_switch_poe_port(port)`: Power cycles PoE power on individual ports (e.g. `1/0/3` AP).
- **Araknis 520 Router (`192.168.1.1` / `192.168.10.1`)**:
  - `get_araknis_router_status()`: Queries system stats, WAN status, LAN subnets, 52 DHCP reservations, and 32 ACL rules via authenticated REST API (`/api/cgi-bin/v1/`).
  - `backup_araknis_router()`: Exports OpenSSL-encrypted configuration blob to `infrastructure/network/configs/araknis-520-backup.cfg`.
  - `restore_araknis_router(backup_file)`: Pushes blueprint configuration blob via `POST /command/restore-config`.
- **Pakedge SX-8P Managed Switch (`192.168.1.205`)**:
  - Data trunked on Araknis 920 Port 1/0/7; mains-powered via Control4 WattBox outlet 11 (*Office → All Test Equipment* Control4 button with 90-min auto-off timer).
  - `get_pakedge_switch_status(host)`: Queries switch status, open services, and upstream learned MACs.
  - `backup_pakedge_switch(host)`: Backs up running config via RFC 854 raw Telnet socket engine to `pakedge-sx8p-running.cfg`.
  - `configure_pakedge_vlans(host)`: Provisions hybrid trunk `gi1` (PVID 1, tagged 10/150/200), access VLAN 10 (`gi2-7`), access VLAN 150 (`gi8`), disables STP, enables BPDU flooding.
  - `power_cycle_pakedge_poe_port(port, wait_sec, host)`: Reboots individual PoE testbench loads (ports 1–8).
  - `power_cycle_pakedge_switch(port)`: Reboots the switch (to be wired to Control4 WattBox macro).
- **Netgear GS108Ev2 Managed Switch (`192.168.1.220`)**:
  - Native headless pure-Python NSDP (UDP 63321/63322) protocol driver via OpenWrt L2 bridge relay (`192.168.1.226`). See `docs/specifications/netgear-gs108ev2-nsdp.md`.
  - `get_netgear_switch_status(ip)`: Audits live ports, speed, duplex, traffic counters, and CRC error statistics.
  - `backup_netgear_switch(ip)`: Dumps full switch configuration to GitOps.
  - `set_netgear_vlan(vid, tagged_ports, untagged_ports, pvid_ports, force_uplink, ip)`: Provisions 802.1Q VLANs with uplink safety guards.
  - `delete_netgear_vlan(vid, ip)`: Removes VLANs safely reverting PVIDs.
  - `set_netgear_pvid(port, pvid, force_uplink, ip)`: Configures port default PVID.
  - `set_netgear_port(port, admin, speed, force_uplink, ip)`: Controls port administrative status and link speed.
  - `set_netgear_features(igmp, loop_detection, ip)`: Sets IGMP snooping and loop detection.
  - `restore_netgear_switch(config_file, confirm, ip)` / `verify_netgear_switch(baseline_file, ip)`: Validates and restores ProSAFE binary `.cfg` or JSON configs.

#### 5. Routing, Failover & Network Observability
- **OpenWrt & DD-WRT**:
  - `get_openwrt_status(ip)`: Audits Office Belkin AX3200 OpenWrt router (`192.168.1.226`), routes, and failover daemon state.
  - `backup_openwrt(ip, user)` / `restore_openwrt(ip, user, dry_run)`: Backs up and restores `/etc/config/`, custom daemons, and failover scripts.
  - `deploy_vxlan_hardening()`: Deploys hardened failover scripts, isolated probe VLAN 4094, loop guard, and STP priority 8192.
  - `get_ddwrt_status(ip)` / `restore_ddwrt(router, ip, dry_run)`: Manages DD-WRT routers (`aurora: 10.25.25.1`, `luna: 10.20.20.1`) and PIA VPN watchdogs.
- **Network Matrix & SPAN Observability**:
  - `verify_network_matrix(profile)`: Automated end-to-end ICMP and TCP port matrix verification across all 8 VLANs.
  - `get_wireshark_status(vmid)`: Inspects luna-server (VM 102) SPAN mirror interface (`ens19`), packet counters, and tmpfs capture chunks.
  - `sync_wireshark_capture()`: Synchronizes headless tshark capture mover scripts from Stack 48 into Git.

#### 6. External Cloud Services & Security Hardening
- `get_external_services_status()`: Zero-trust synthetic health audit for `theurer.dev` web and `mail.theurer.dev`.
- `check_ssl_certificates()`: Audits TLS/SSL certificate validity and expiration dates across external domains.
- `audit_email_pipeline()`: Validates submission (SMTP :587), IMAPS (:993), and webmail health for `mail.theurer.dev`.
- `audit_external_hosts(host)` / `backup_external_host(host)`: Audits and archives GitOps configuration bundles for cloud VPS hosts.
- `get_external_security_status(host)`: Audits Fail2Ban active jails, banned IPs, UFW firewall rules, and listening ports.
- `deploy_external_promtail(host, url, tenant_id, dry_run)`: Deploys Promtail log shipping agent to external cloud VPS.
- `whitelist_external_ip(ip, host)`: Safely whitelists home egress IP in cloud Fail2Ban `ignoreip`.

#### 7. Architecture & Runbook Reference Links
- `docs/architecture/vlan-matrix.md`: Authoritative 8-VLAN table and 32 live ACL rules.
- `docs/architecture/network-topology.md`: Dual-WAN topology, Araknis 520, 920 switch, 830 APs, and DNS split-horizon.
- `docs/specifications/netgear-gs108ev2-nsdp.md`: Comprehensive reverse-engineered NSDP protocol specification and register mapping.
- `docs/runbooks/network-automation.md`: Authoritative quick-reference runbook for all network automation, Netgear NSDP, and Wireshark capture scripts.
- `docs/roadmaps/network-implementation-plan.md`: Master phased homelab roadmap and historical decision log.

## Araknis 520 Router REST API — Technical Reference
- **Auth Mechanism**: HTTP Basic Auth via `GET /api/cgi-bin/v1/authorize` with `Authorization: Basic base64(user:pass)` header. Returns `302` on success, `401` on failure. NO session cookies — send the `Authorization` header on every request.
- **Base URL**: `http://192.168.1.1/api/cgi-bin/v1/`
- **Discovery method**: Chrome DevTools XHR/fetch breakpoint on "authorize" while logging in revealed the React SPA sends `GET` (not `POST`) with Basic Auth header, not form data.
- **Backup format**: `GET /command/export-config` returns HTTP `201` with a base64-encoded OpenSSL-encrypted config blob (`Salted__` prefix). Restore via `POST /command/restore-config` with the blob as body.
- **Known working endpoints**: `/config/lan/subnets`, `/config/wan`, `/status/wan`, `/status/ports`, `/status/system/system-information`, `/status/system/stats`, `/config/firewall`, `/config/lan/dhcp-reservation`, `/config/acls`, `/command/export-config`, `/command/restore-config`.
- **Timed-out endpoints (avoid)**: `/config/firewall/interzone` — hangs indefinitely, use 2s timeout.
- **VLAN DNS**: All 8 VLANs use `192.168.40.185` (nexus-server AdGuard) and `192.168.40.186` (nexus-server2 AdGuard) as DHCP-assigned DNS servers.
- **Config backup file**: `infrastructure/network/configs/araknis-520-backup.cfg` (19K encrypted blob).
