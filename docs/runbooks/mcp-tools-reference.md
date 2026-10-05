# 🛠️ FastMCP Homelab Tools Architecture & Reference Guide

This document provides the authoritative, extensive reference for the **20 consolidated FastMCP tools** implemented in [`mcp/homelab/server.py`](../../mcp/homelab/server.py).

---

## 🎯 Architecture & Core Design Goals

1. **Token Efficiency via Action-Oriented Tooling**:
   - Rather than registering 65 fine-grained tools that flood the AI context window with schema bloat, tools are consolidated into **20 action-oriented interfaces**.
   - Cuts schema token utilization by **over 65%** while retaining 100% of underlying infrastructure automation capabilities.
2. **Deterministic Virtual Environment (`.venv`)**:
   - All script invocations route automatically through the project's pre-configured virtual environment (`.venv/bin/python3`).
   - Eliminates missing dependency errors (e.g. `requests`, `pyyaml`, `fastmcp`, `dpkt`) and removes the need for manual environment activation.
3. **Zero-Trust Local Secret Decryption**:
   - All passwords, API tokens, and private SSH keys are stored encrypted via SOPS + age (`homelab-infrastructure.key`).
   - Tools decrypt secrets in-memory at execution time, eliminating interactive TTY password prompts.
4. **Committed vs. Local Exploration Separation**:
   - **Committed Production Automation**: Resides strictly in [`mcp/homelab/scripts/`](../../mcp/homelab/scripts/) and is directly mapped to FastMCP tools.
   - **Local Scratch & Exploration**: Ad-hoc scripts, diagnostic prototypes, and one-off discovery tools reside in `.agents/scripts/` (untracked in Git).

---

## 📋 Master 20-Tool Catalog & Capability Matrix

| # | Tool Name | Functional Domain | Primary Actions | Underlying Script |
| :-: | :--- | :--- | :--- | :--- |
| **1** | `sync_fleet` | Fleet GitOps Drift | `diff_only`, `apply` | `sync-live-fleet.py` |
| **2** | `manage_hosts` | Physical Hypervisors | `audit`, `backup`, `restore`, `restore_configs`, `register` | `extract_host_configs.sh`, `restore-host-drifts.py`, `restore-host-configs.py` |
| **3** | `manage_vms` | QEMU VMs & LXCs | `list`, `status`, `start`, `stop`, `restore`, `register` | Native SSH / QGA / `restore-vm-drifts.py` |
| **4** | `manage_vm_snapshots` | VM Snapshots & PBS | `list`, `create`, `rollback`, `delete`, `vzdump` | `manage-vm-snapshots.py` |
| **5** | `manage_stacks` | Portainer Stacks (91) | `index`, `backup`, `restore`, `start` | `generate-stack-index.py`, `restore-docker-stacks.py`, `start-docker-stacks.py` |
| **6** | `manage_apt_packages` | Package Drift | `backup`, `restore` | `restore-apt-packages.py`, `sync-live-fleet.py` |
| **7** | `manage_araknis_router` | Core L3 Router (520) | `status`, `backup`, `restore` | `manage-araknis-router.py` |
| **8** | `manage_araknis_switch` | Core L2+ Switch (920) | `status`, `backup`, `poe_cycle` | `manage-araknis-switch.py` |
| **9** | `manage_netgear_switch` | Office Switch (GS108Ev2) | `status`, `backup`, `restore`, `verify`, `set_vlan`, `delete_vlan`, `set_pvid`, `set_port`, `set_features` | `manage-netgear-switch.py` |
| **10** | `manage_pakedge_switch` | Lab Switch (SX-8P) | `status`, `backup`, `poe_cycle`, `power_cycle`, `configure_vlans` | `manage-pakedge-switch.py` |
| **11** | `manage_openwrt` | Office Bridge Router | `status`, `backup`, `restore`, `deploy_vxlan` | `get-openwrt-status.py`, `backup-openwrt-config.py`, `restore-openwrt-config.py`, `deploy-vxlan-hardening.py` |
| **12** | `manage_ddwrt` | DD-WRT Routers (2) | `status`, `backup`, `restore` | `get-ddwrt-status.py`, `backup-ddwrt-config.py`, `restore-ddwrt-config.py` |
| **13** | `verify_network_matrix`| Cross-VLAN Audit | `quick`, `comprehensive` | `verify-network-matrix.py` |
| **14** | `manage_wireshark` | Headless SPAN Sniffer | `status`, `sync_capture` | `get-wireshark-status.py`, `sync-wireshark-capture-script.py` |
| **15** | `analyze_pcap_telemetry`| Streaming PCAP Engine | `comprehensive`, `summary`, `l2_hygiene`, `routing_matrix`, `transport_health`, `core_services`, `security_anomalies` | `analyze-pcap-telemetry.py` |
| **16** | `query_pcap_flows` | Forensic Packet Query | Filter by host, port, protocol, VLAN | `analyze-pcap-telemetry.py` |
| **17** | `manage_external_services`| Cloud VPS Services | `status`, `ssl`, `email`, `security`, `whitelist` | `manage-external-services.py` |
| **18** | `manage_external_hosts`| Cloud VPS Hosts | `audit`, `backup`, `deploy_promtail` | `manage-external-hosts.py`, `deploy-external-promtail.py` |
| **19** | `sync_adguard_clients` | DNS Identity Alignment | Non-destructive dry-run, live sync | `sync-adguard-clients.py` |
| **20** | `align_ovrc_devices` | OvrC Cloud Sync | `preview`, `csv`, `apply` | `align-ovrc-devices.py` |

---

## 🔍 Detailed Tool Specifications & Usage

### 1. Fleet & Hypervisor Management

#### `sync_fleet`
* **Purpose**: Compares live Proxmox hosts, VMs, and Portainer stacks against Git blueprints.
* **Arguments**:
  - `apply` (*bool*, default: `False`): When `True`, commits live state to Git repository.
  - `diff_only` (*bool*, default: `True`): Non-destructive dry-run showing exact drift.
* **Example**:
  ```python
  sync_fleet(diff_only=True)
  ```

#### `manage_hosts`
* **Purpose**: Lifecycle, drift audit, and configuration capture for physical Proxmox nodes (`pve`, `pve2`, `pve3`).
* **Arguments**:
  - `action` (*str*, required): `'audit'`, `'backup'`, `'restore'`, `'restore_configs'`, or `'register'`.
  - `node` (*str*, optional): Target host (e.g. `'pve'`, `'pve2'`, `'pve3'`).
  - `ip` (*str*, optional): Host IP address when registering.
* **Example**:
  ```python
  manage_hosts(action="backup")
  manage_hosts(action="restore", node="pve")
  ```

#### `manage_vms`
* **Purpose**: Unified control for QEMU Virtual Machines and LXC containers across all hypervisors.
* **Arguments**:
  - `action` (*str*, required): `'list'`, `'status'`, `'start'`, `'stop'`, `'restore'`, or `'register'`.
  - `node` (*str*, optional): Target node name.
  - `vmid` (*str*, optional): Target VM or container ID.
  - `name` (*str*, optional): VM name for registration.
* **Example**:
  ```python
  manage_vms(action="list")
  manage_vms(action="status", node="pve", vmid="102")
  ```

#### `manage_vm_snapshots`
* **Purpose**: Manages live QEMU memory/disk snapshots and cold Proxmox `vzdump` backups.
* **Arguments**:
  - `action` (*str*, required): `'list'`, `'create'`, `'rollback'`, `'delete'`, or `'vzdump'`.
  - `node` (*str*, required): Target node name.
  - `vmid` (*str*, required): Target VM ID.
  - `snapshot_name` (*str*, optional): Identifier for snapshot operations.
* **Example**:
  ```python
  manage_vm_snapshots(action="create", node="pve", vmid="100", snapshot_name="pre-upgrade")
  manage_vm_snapshots(action="list", node="pve", vmid="100")
  ```

---

### 2. Docker Stacks & Software Manifests

#### `manage_stacks`
* **Purpose**: Manages all 91 Portainer stacks and 188 microservices across the fleet.
* **Arguments**:
  - `action` (*str*, required): `'index'`, `'backup'`, `'restore'`, or `'start'`.
  - `target_vm` (*str*, optional): e.g. `'luna-server'`, `'nexus-server'`, `'media-server'`.
  - `stack_name` (*str*, optional): Specific stack directory or number.
* **Example**:
  ```python
  manage_stacks(action="index")
  manage_stacks(action="restore", target_vm="luna-server")
  ```

#### `manage_apt_packages`
* **Purpose**: Backs up or restores installed Debian/Ubuntu package manifests to prevent software drift.
* **Arguments**:
  - `action` (*str*, required): `'backup'` or `'restore'`.
  - `node` (*str*, optional): Target node name.
  - `vmid` (*str*, optional): Target VM ID.

---

### 3. Switching & Routing Automation

#### `manage_araknis_router`
* **Purpose**: Manages the core Araknis 520 router via authenticated REST API (`/api/cgi-bin/v1/`).
* **Arguments**:
  - `action` (*str*, default: `'status'`): `'status'`, `'backup'`, or `'restore'`.
  - `config_file` (*str*, optional): Path to backup configuration blob.
  - `confirm` (*bool*, default: `False`): Safety confirmation for restoration.
* **Credentials**: Automatically decrypted from `infrastructure/secrets/araknis-switch.enc.yaml`.

#### `manage_araknis_switch`
* **Purpose**: Manages the Araknis 920 Multi-Gig Core switch via SSH/Telnet CLI.
* **Arguments**:
  - `action` (*str*, default: `'status'`): `'status'`, `'backup'`, or `'poe_cycle'`.
  - `port` (*str*, optional): Target switch port (e.g. `'1/0/7'`).
  - `wait_sec` (*int*, default: `5`): Power cycle duration in seconds.

#### `manage_netgear_switch`
* **Purpose**: Fully programmatic management of the headless Netgear GS108Ev2 desktop switch via pure-Python Layer 2 NSDP protocol across an L2 relay hop (`192.168.1.226` or `192.168.1.250`).
* **Arguments**:
  - `action` (*str*, default: `'status'`): `'status'`, `'backup'`, `'verify'`, `'restore'`, `'set_vlan'`, `'delete_vlan'`, `'set_pvid'`, `'set_port'`, `'set_features'`.
  - `relay` (*str*, default: `'192.168.1.226'`): Layer 2 bridge relay IP.
  - `vid`, `pvid`, `port`, `tagged`, `untagged`, `admin`, `speed`, `igmp`, `loop`, `confirm`, `json_output`.
* **Example**:
  ```python
  manage_netgear_switch(action="status")
  manage_netgear_switch(action="set_pvid", port=2, pvid=10)
  ```

#### `manage_pakedge_switch`
* **Purpose**: Manages the work automation lab Pakedge SX-8P switch via native Telnet/RFC854 socket engine.
* **Arguments**:
  - `action` (*str*, default: `'status'`): `'status'`, `'backup'`, `'poe_cycle'`, `'power_cycle'`, `'configure_vlans'`.
  - `port` (*int*, optional): Port number (1–8).
  - `wait_sec` (*int*, default: `5`).
  - `vlans` (*str*, optional): Port VLAN mapping string.

#### `manage_openwrt`
* **Purpose**: Manages the Belkin AX3200 OpenWrt office router and 3-priority failover engine.
* **Arguments**:
  - `action` (*str*, default: `'status'`): `'status'`, `'backup'`, `'restore'`, `'deploy_vxlan'`.
  - `config_file` (*str*, optional): Custom configuration archive path.

#### `manage_ddwrt`
* **Purpose**: Manages upstream DD-WRT routers (`aurora`: `10.25.25.1`, `luna`: `10.20.20.1`) over SSH.
* **Arguments**:
  - `action` (*str*, default: `'status'`): `'status'`, `'backup'`, or `'restore'`.
  - `router` (*str*, default: `'all'`): `'aurora'`, `'luna'`, or `'all'`.

---

### 4. Telemetry, Forensics & Diagnostics

#### `verify_network_matrix`
* **Purpose**: Audits latency, reachability, and inter-VLAN ACL isolation across all 21 core targets.
* **Arguments**:
  - `profile` (*str*, default: `'quick'`): `'quick'` (ICMP ping latency) or `'comprehensive'` (full TCP/UDP and inter-VLAN ACL matrix).

#### `manage_wireshark`
* **Purpose**: Manages the headless SPAN sniffer running on `luna-server` (`VM 102`) monitoring `ens19`.
* **Arguments**:
  - `action` (*str*, default: `'status'`): `'status'` (packet capture rates & NAS storage) or `'sync_capture'`.

#### `analyze_pcap_telemetry`
* **Purpose**: High-throughput streaming diagnostic engine for continuous multi-gigabyte PCAP/PCAPNG captures.
* **Arguments**:
  - `path` (*str*, optional): Directory or file path (defaults to auto-discovered capture storage).
  - `focus` (*str*, default: `'comprehensive'`): `'comprehensive'`, `'summary'`, `'l2_hygiene'`, `'routing_matrix'`, `'transport_health'`, `'core_services'`, `'security_anomalies'`.
  - `vlan` (*int*, optional): Filter specifically by 802.1Q VLAN tag.
  - `max_files` (*int*, optional): Limit number of files processed.
  - `max_packets` (*int*, optional): Limit number of packets analyzed.
  - `json_output` (*bool*, default: `False`): Return structured JSON instead of formatted Markdown.
* **Example**:
  ```python
  analyze_pcap_telemetry(focus="l2_hygiene", max_files=10)
  ```

#### `query_pcap_flows`
* **Purpose**: Targeted flow search tool for extracting exact packet conversations from PCAP captures.
* **Arguments**:
  - `host` (*str*, optional): e.g. `'192.168.10.200'`
  - `port` (*int*, optional): e.g. `53`
  - `proto` (*str*, optional): `'tcp'`, `'udp'`, `'icmp'`, `'arp'`
  - `vlan` (*int*, optional): 802.1Q VLAN ID
  - `limit` (*int*, default: `50`): Maximum matched conversations to return.

---

### 5. External Cloud VPS & Edge Services

#### `manage_external_services`
* **Purpose**: End-to-end health, security, and SSL inspection for Oracle Cloud (`theurer.dev`) and Google Cloud (`mail.theurer.dev`).
* **Arguments**:
  - `action` (*str*, default: `'status'`): `'status'`, `'ssl'`, `'email'`, `'security'`, `'whitelist'`.
  - `ip` (*str*, optional): Required for `'whitelist'` action.

#### `manage_external_hosts`
* **Purpose**: Drift inspection, GitOps configuration backup, and Promtail log shipping deployment for external VPS hosts.
* **Arguments**:
  - `action` (*str*, default: `'audit'`): `'audit'`, `'backup'`, `'deploy_promtail'`.
  - `target` (*str*, default: `'all'`): `'web-server'`, `'email-server'`, or `'all'`.

---

### 6. Identity, OvrC & DHCP Synchronization

#### `sync_adguard_clients`
* **Purpose**: Synchronizes authoritative DHCP reservations into AdGuard Home's Persistent Clients table via REST API (`http://192.168.40.185:8081`).
* **Arguments**:
  - `host` (*str*, default: `'http://192.168.40.185:8081'`): Primary AdGuard Home URL.
  - `dry_run` (*bool*, default: `False`): Preview client updates without writing to AdGuard.

#### `align_ovrc_devices`
* **Purpose**: Correlates and aligns Snap One OvrC Cloud device inventory with authoritative DHCP reservations.
* **Authentication**: Decrypts `infrastructure/secrets/ovrc.enc.yaml` via SOPS + age, or uses `OVRC_TOKEN` / `OVRC_USERNAME` env vars.
* **Arguments**:
  - `action` (*str*, default: `'preview'`):
    - `'preview'`: Non-destructive correlation diff showing devices to rename.
    - `'csv'`: Generates updated `infrastructure/network/configs/ovrc-device-list-aligned.csv`.
    - `'apply'`: Connects to live OvrC Cloud API and applies device names and room assignments.
* **Example**:
  ```python
  # Non-destructive preview
  align_ovrc_devices(action="preview")

  # Live cloud push
  align_ovrc_devices(action="apply")
  ```

---

## 🔐 OvrC Credentials & Authentication Architecture

To enable live OvrC synchronization without manual tokens:
1. Create the secret template file:
   ```yaml
   # infrastructure/secrets/ovrc.enc.yaml
   token: "<OVRC_BEARER_OR_API_TOKEN>"
   username: "<OVRC_LOGIN_EMAIL>"
   password: "<OVRC_LOGIN_PASSWORD>"
   ```
2. Encrypt the file using the repository master age key:
   ```bash
   sops --encrypt --in-place infrastructure/secrets/ovrc.enc.yaml
   ```
3. When `align_ovrc_devices(action="apply")` is called, the script automatically:
   - Locates `homelab-infrastructure.key` in repo root.
   - Decrypts `ovrc.enc.yaml` in memory via SOPS.
   - Pushes device names and room assignments directly to the OvrC Cloud API.
