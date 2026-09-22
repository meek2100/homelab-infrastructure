# 🌐 Homelab Network Implementation Plan & Verification Runbook

This implementation plan provides the complete, authoritative, verified roadmap for configuring, securing, auditing, and maintaining your entire homelab network infrastructure.

---

## 📈 Progress Summary — Last Updated 2026-09-22

| Part | Title | Status |
| :--- | :--- | :---: |
| **Part 1** | Core Router & Switch ACL Configuration (21 rules) | ✅ 100% Verified |
| **Part 2** | End-to-End Verification & Testing Runbook (5 tests) | ✅ 100% Verified |
| **Part 2.5** | Multicast & Discovery Architecture (Native NSDP/mDNS) | ✅ Settled |
| **Part 2.6** | WAN2 & Storage SAN Isolation (untagged vmbr1) | ✅ Settled |
| **Part 2.7** | vxlan-server Split Trunking Architecture (VM 107) | ✅ Designed — `vxlan-server` on standby, tested |
| **Part 2.8** | Netgear GS108Ev2 Office Switch GitOps & Backup | 🟡 In Progress — SOPS secrets stored; NSDP tooling installed in `.venv`; **MCP backup cannot run remotely** (requires L2-local host on VLAN 1) |
| **Part 3** | Unified Monitoring, SNMP & Observability (Grafana stack) | ⏳ Pending — not yet deployed |

### Key Protocol Constraints Discovered This Session
- **Netgear GS108Ev2** — No HTTP REST API. Uses **NSDP** (Layer 2 UDP, ports 63321/63322). The `backup_netgear_switch` / `get_netgear_switch_status` MCP tools **must execute from a host physically on VLAN 1** (`192.168.1.0/24`). Running from a remote routed host will always time out. To resolve: add SSH-exec wrapper invoking `manage-netgear-switch.py` on `pve` (192.168.1.250) or `nexus-server`.

---



## 🏛️ Empirical Network Architecture & IP Reference

| Equipment | Model | IP Address | Subnet / VLAN | Role | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Core Router** | Araknis 520 Dual-WAN | `192.168.10.1` & `192.168.1.1` | VLAN 1 & VLAN 10/40 | Layer 3 Gateway, Interzone Routing, NAT, ACL Firewall | 🟢 Active |
| **Core Switch** | Araknis 920 Managed | `192.168.1.215` | VLAN 1 (Management) | 10G/2.5G L2+ Distribution, IGMP Snooping Querier, SPAN Mirror | 🟢 Active |
| **AP 1 (Master)**| Araknis 830 Wi-Fi 7 | `192.168.1.231` | VLAN 1 (Management) | Broadcasts SSIDs + Wired Master for 5GHz PTP Bridge | 🟢 Active |
| **AP 2 (Core)** | Araknis 830 Wi-Fi 7 | `192.168.1.236` | VLAN 1 (Management) | Broadcasts SSIDs (Ch 1 / 149 / 69) | 🟢 Active |
| **AP 3 (Bridge)**| Araknis 830 Wi-Fi 7 | `192.168.1.237` | VLAN 1 (Management) | Dedicated Wireless Bridge Client (Insomniac_Bridge) | 🟢 Active |
| **Office Switch**| Netgear GS108Ev2 | `192.168.1.220` | VLAN 1 (Management) | Desktop distribution switch behind OpenWrt — **No official API/CLI; managed via NSDP (UDP 63321/63322)** | 🟢 Active |
| **Office Router**| Belkin AX3200 (OpenWrt) | `192.168.1.226` / `10.99.99.1` | VLAN 1 & VLAN 150 | 3-Priority Failover (Wire, VXLAN 150, Wi-Fi repeater) | 🟢 Active |
| **WAN2 Router** | Asus RT-N66U (DD-WRT Aurora)| `10.25.25.1` & `10.20.20.2` | WAN2 / `10.25.25.0/24` | Torrent/discovery isolation with PIA VPN auto-watchdog | 🟢 Active |
| **Upstream GW** | DD-WRT Luna | `10.20.20.1` | `10.20.20.0/24` | Upstream transit gateway (firewalled from WAN) | 🟢 Active |
| **Admin VM** | nexus-server (pve:100)| `192.168.40.185` | VLAN 40 (Servers) | WireGuard (:51820), Tailscale (:69), AdGuard Home Primary (:53), NPM | 🟢 Active |
| **DNS2 VM** | nexus-server2 (pve3:100)| `192.168.40.186` | VLAN 40 (Servers) | AdGuard Home Secondary (:53) | 🟢 Active |
| **Smart Home VM**| luna-server (pve:102) | `192.168.40.249` | VLAN 40 (Servers) | Home Assistant (:8123), Homebridge (:8581), Spoolman (:7912), Syncthing (:22000), SPAN Mirror (:ens19) | 🟢 Active |
| **Media VM** | media-server (pve:103) | `192.168.40.247` | VLAN 40 (Servers) | Plex (:32400 with Intel P630 QuickSync), Audiobookshelf | 🟢 Active |
| **NAS VM** | nas-server (pve3:101) | `192.168.40.248` & `10.25.25.248` | VLAN 40 & SAN | OpenMediaVault Storage (SMB / NFS) | 🟢 Active |
| **Download VM** | discovery-server (pve2:100)| `10.25.25.246` | Dedicated WAN2 SAN | VPN automated torrent & discovery engine | 🟢 Active |
| **Gaming VM** | minecraft-docker (pve:109)| `192.168.40.175` | VLAN 40 (Servers) | Minecraft Bedrock Connect / Proxy | 🟢 Active |
| **Bridge VM** | vxlan-server (pve:107) | `192.168.1.150` | VLAN 1 & VLAN 150 | VXLAN Layer 2/3 decapsulator & trunking bridge | 🟡 Standby |
| **Automation** | Control4 CA-10 (Director)| `192.168.10.200` | VLAN 10 (Trusted) | Primary Control4 Automation Controller | 🟢 Active |
| **3D Printing** | mainsail (Raspberry Pi) | `192.168.30.90` | VLAN 30 (IoT) | Klipper / Moonraker host (MAC `E4:5F:01:78:DF:81`) | 🟢 Active |

---

## 📋 Part 1: Core Router & Switch Authoritative Configuration

### 1. Araknis 520 Router Access Control Lists (ACL Hierarchy)
Audited and verified live via `GET /api/cgi-bin/v1/config/acls`. 21 rules active with strict evaluation order:

| Priority | Rule Name | Action | Service | Source | Destination | Status |
| :---: | :--- | :---: | :--- | :--- | :--- | :---: |
| **1** | Inter-VLAN DNS | Permit | DNS (UDP:53) | Any | `192.168.40.185-186` | 🟢 Active |
| **2** | AdGuard Local DNS (DoH) | Permit | HTTPS (DoH) (TCP:443) | Any | `192.168.40.185-186` | 🟢 Active |
| **3** | AdGuard Local DNS (DoQ) | Permit | DNS over QUIC (UDP:853) | Any | `192.168.40.185-186` | 🟢 Active |
| **4** | Inter-VLAN DNS | Permit | DNS (UDP:53) | `192.168.40.185-186` | Any | 🟢 Active |
| **5** | DNS over HTTPS (DoH) | Permit | HTTPS (DoH) (TCP:443) | `192.168.40.185-186` | Any | 🟢 Active |
| **6** | DNS over QUIC (DoQ) | Permit | DNS over QUIC (UDP:853) | `192.168.40.185-186` | Any | 🟢 Active |
| **7** | Unblock C4 | Permit | All Traffic | `192.168.30.0/24` (IoT) | `192.168.10.200` (C4 CA-10) | 🟢 Active |
| **8** | Media to Control4 | Permit | All Traffic | `192.168.20.0/24` (Media) | `192.168.10.200` (C4 CA-10) | 🟢 Active |
| **9** | IoT to Home Assistant | Permit | Home-Assistant (TCP:8123) | `192.168.30.0/24` (IoT) | `192.168.40.249` (luna-server) | 🟢 Active |
| **10** | IoT to Homebridge | Permit | Homebridge (TCP:8581) | `192.168.30.0/24` (IoT) | `192.168.40.249` (luna-server) | 🟢 Active |
| **11** | Mainsail to Luna Server | Permit | All Traffic | `192.168.30.90` (mainsail) | `192.168.40.249` (luna-server) | 🟢 Active |
| **12** | Media to Plex Server | Permit | Plex-Media (TCP:32400) | `192.168.20.0/24` (Media) | `192.168.40.247` (media-server) | 🟢 Active |
| **13** | Media to Home Assistant | Permit | Home-Assistant (TCP:8123) | `192.168.20.0/24` (Media) | `192.168.40.249` (luna-server) | 🟢 Active |
| **14** | Sonos UPnP Callback | Permit | Sonos-Callback (TCP:3400-3500) | `192.168.20.0/24` (Media) | `192.168.10.0/24` (Trusted) | 🟢 Active |
| **15** | Block IoT to Management | Deny | All Traffic | `192.168.30.0/24` (IoT) | `192.168.1.0/24` (Management) | 🟢 Active |
| **16** | Block IoT to Trusted LAN | Deny | All Traffic | `192.168.30.0/24` (IoT) | `192.168.10.0/24` (Trusted) | 🟢 Active |
| **17** | Block IoT to Guest | Deny | All Traffic | `192.168.30.0/24` (IoT) | `192.168.20.0/24` (Media/Guest) | 🟢 Active |
| **18** | Block IoT to Servers | Deny | All Traffic | `192.168.30.0/24` (IoT) | `192.168.40.0/24` (Servers) | 🟢 Active |
| **19** | Block Guests to Management | Deny | All Traffic | `192.168.20.0/24` (Media) | `192.168.1.0/24` (Management) | 🟢 Active |
| **20** | Block Guests to Trusted LAN | Deny | All Traffic | `192.168.20.0/24` (Media) | `192.168.10.0/24` (Trusted) | 🟢 Active |
| **21** | Block Guests to Servers | Deny | All Traffic | `192.168.20.0/24` (Media) | `192.168.40.0/24` (Servers) | 🟢 Active |

---

## 🔍 Part 2: End-to-End Verification & Testing Runbook

### Test 1: Automated Network Reachability Matrix Audit — PASSED
* **Coverage**: All 21 core network targets verified (<10ms average latency) via `verify-network-matrix.py`.

### Test 2: WireGuard Cellular Ingress & Management Reach — PASSED
* Verified over cellular LTE/5G via `vpn.theurer.dev`. Reaches `pve` (`192.168.1.250:8006`), router (`192.168.10.1`), and Home Assistant (`192.168.40.249:8123`).

### Test 3: Tailscale Mesh Ingress & Subnet Routing — PASSED
* Direct reach to Home Assistant (`:8123`) and Araknis Switch (`192.168.1.215`) via `nexus-server` (Stack 69).

### Test 4: Cross-VLAN Sonos & Spotify Connect Fluidity — PASSED
* Verified streaming from phone on Trusted (VLAN 10) to Sonos on Media (VLAN 20) via native Araknis 520 Bonjour repeater, 920 IGMP Querier, and Rule 14 UPnP callback permit.

### Test 5: IoT & Media Containment Verification — PASSED
* IoT (VLAN 30) blocked from hypervisors and router admin. Whitelisted for Home Assistant (`:8123`), Homebridge (`:8581`), Control4 Director (`192.168.10.200`), and Mainsail ➔ Luna (`192.168.40.249`).
* Media (VLAN 20) strictly blocked from hypervisors and internal servers, with whitelists for Plex (`:32400`), Control4 CA-10 (`192.168.10.200`), and Home Assistant (`:8123`).

---

## 📻 Part 2.5: Multicast & Discovery Architecture (Native Resolution & Loop Prevention)

### Permanent Retirement of Software Relays
Containerized software relays (`multicast-relay`) tested earlier created severe duplicate-forwarder broadcast loops with the Araknis 520 router native multicast forwarding, triggering FDB MAC move flapping and switch port damping.
* **Settled Architecture**: 100% native resolution via Araknis 520 Bonjour mDNS repeater + Araknis 920 IGMP Snooping Querier.
* Zero software relays, zero multi-homed VM bridges, zero broadcast loop risk.

---

## 🔒 Part 2.6: WAN2 & Storage SAN Isolation Architecture (Tagged vs. Untagged Best Practice)

* **Architecture**: Dedicated untagged physical bridge (`vmbr1`, `10.25.25.0/24`) across hypervisors (`nas-server` VM 101, `discovery-server` VM 100).
* **Router Setting**: Araknis WAN2 configured with `dataForwarding: false`.
* **Guarantee**: Total physical air-gapping, immunity to 802.1Q tag stripping, zero switch FDB poisoning risk, and unencapsulated multi-gigabit wire speed for NFS/SMB transfers.

---

## 🌉 Part 2.7: `vxlan-server` (VM 107) & OpenWrt Split Trunking Architecture

### 1. Problem Statement & Root Cause of Previous Loop
The Araknis 830 AP 5GHz wireless bridge strips 802.1Q tags across the link to the office. Previously, when `vxlan-server` (VM 107) bridged untagged `192.168.1.0/24` while the physical wireless bridge was also forwarding untagged `192.168.1.0/24`, two active Layer 2 paths existed for the same broadcast domain, triggering instant loop storms and switch port damping.

### 2. The Solution: Split Untagged vs. Tagged Trunking

```text
┌─────────────────────────┐                                 ┌─────────────────────────┐
│     Office Belkin       │                                 │   Main Rack Switch      │
│     AX3200 OpenWrt      │                                 │     Araknis 920         │
│   (192.168.1.226)       │                                 │   (192.168.1.215)       │
└────────────┬────────────┘                                 └────────────▲────────────┘
             │                                                           │
             │ [Untagged VLAN 1 Native]                                  │ [VLAN 1 Untagged]
             ├─────────────────────── Araknis 830 AP Bridge ─────────────┤
             │                       (Priority 1: Wire Speed)            │
             │                                                           │
             │ [Tagged VLANs: 10, 20, 30, 40, 150]                       │
             └─────── Encapsulated into VXLAN UDP Port 4789 ─────────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │    vxlan-server     │
                          │   (pve: VM 107)     │
                          │   192.168.1.150     │
                          └──────────┬──────────┘
                                     │ Decapsulates & Tags
                                     ▼
                          Proxmox vmbr0 Trunk ➔ SW920 Port 1/0/2
```

### 3. Implementation Rules & Guardrails
1. **Untagged Traffic (VLAN 1 / Management `192.168.1.0/24`)**:
   * Flows exclusively across the physical 830 AP wireless bridge (Priority 1) with full 1500 MTU.
   * `vxlan150` on VM 107 and OpenWrt does **NOT** bridge untagged VLAN 1 during normal operation.
2. **Tagged Traffic (VLANs 10, 20, 30, 40, 150)**:
   * Encapsulated into UDP packets (VNI 150, Port 4789, MTU 1450, MSS 1406) by OpenWrt (`192.168.1.226`).
   * Decapsulated by `vxlan-server` (`192.168.1.150`) and injected into Proxmox `vmbr0` with respective 802.1Q tags.
   * Because untagged VLAN 1 is excluded from the tunnel, duplicate Layer 2 paths are physically impossible.
3. **Standby Failover (Priority 2)**:
   * If and only if the physical 830 AP bridge drops (ping loss to `192.168.1.237`), OpenWrt dynamically bridges untagged VLAN 1 into VXLAN until the wireless link recovers.

---

## 🔌 Part 2.8: Netgear GS108Ev2 Office Switch — GitOps Backup Status

### Current State: 🟡 In Progress

| Item | Status |
| :--- | :---: |
| SOPS-encrypted credentials saved to `infrastructure/secrets/araknis-switch.enc.yaml` | ✅ Done |
| Community NSDP drivers installed (`netgear-tool`, `py-netgear-plus`) in repo `.venv` | ✅ Done |
| `manage-netgear-switch.py` script authored with `status` and `backup` actions | ✅ Done |
| FastMCP tools `backup_netgear_switch` / `get_netgear_switch_status` registered in `server.py` | ✅ Done |
| Live backup executed & `netgear-gs108e-backup.json` committed to repo | ❌ Blocked |

### Blocker: NSDP Requires Layer 2 Local Execution

The GS108Ev2 has **no HTTP REST API, no SSH, and no web UI**. It uses **NSDP (Netgear Switch Discovery Protocol)** — a proprietary Layer 2 UDP broadcast protocol on ports **63321 (client) / 63322 (switch)**. NSDP frames rely on local MAC broadcast and do not route across Layer 3 boundaries.

The MCP server runs on an external/routed host. `manage-netgear-switch.py` must run on a host **physically on VLAN 1 (`192.168.1.0/24`)**.

**Resolution options:**
1. **SSH-exec wrapper** *(recommended)*: Update `backup_netgear_switch` in `server.py` to SSH into `pve` (`192.168.1.250`) and run `manage-netgear-switch.py` there using the repo's `.venv`.
2. **Manual execution**: SSH into `pve` directly and run `.venv/bin/python3 mcp/homelab/scripts/manage-netgear-switch.py backup`.
3. **VM-based agent / proxy**: Deploy a lightweight daemon inside `nexus-server` or `vxlan-server` (both on VLAN 1) that proxies NSDP requests or provides a local REST API endpoint.

---

### 🔬 Technical Learnings & Driver Comparison

#### 1. `netgear-tool` ([GitHub: s-t-e-f-a-n-o/netgear-tool](https://github.com/s-t-e-f-a-n-o/netgear-tool)) — Primary Driver
* **Protocol Implementation**: Pure Python communicating directly over raw NSDP sockets (UDP 63321/63322).
* **Capabilities**:
  * System info extraction (Model, Firmware, MAC, IP, Gateway).
  * Port settings (enable state, speed configured, actual negotiated speed, duplex).
  * Port statistics (bytes RX, bytes TX, CRC error counters for cable diagnostic).
  * 802.1Q VLAN IDs and per-port VLAN membership tables.
  * PVIDs (Port VLAN IDs).
  * Advanced L2 features: rate limiting, IGMP snooping, port mirroring, loop detection, power saving, QoS mode, broadcast storm filtering.
* **Architecture**: Clean context manager (`with sw: ...`) managing socket lifecycle. Converts internal dataclasses and `IntEnum` objects neatly to JSON.
* **Learnings**: The most comprehensive and reliable library for full configuration extraction and backup of the GS108Ev2.

#### 2. `py-netgear-plus` ([GitHub: foxey/py-netgear-plus](https://github.com/foxey/py-netgear-plus)) — Fallback Driver
* **Protocol Implementation**: Python client designed primarily for the Home Assistant Netgear Plus custom integration.
* **Capabilities**: Automatic model detection (`autodetect_model()`), switch information retrieval (`get_switch_infos()`), and port status.
* **Learnings**: Useful as a secondary fallback for basic switch metadata, but lacks granular L2 features (such as CRC error counters, deep 802.1Q membership mapping, and granular rate limits) found in `netgear-tool`.

---

### 📚 Candidate Repositories for Investigation

To eliminate dependency on the proprietary Windows 11 Netgear ProSAFE Plus Configuration Utility, the following open-source NSDP projects have been identified for deep-dive investigation:

1. **[`nccgroup/nsdp-discover`](https://github.com/nccgroup/nsdp-discover)**
   * **Language**: Python
   * **Focus**: Discovery, credential testing, and security assessment of Netgear NSDP switches by NCC Group.
   * **Value**: Excellent reference for NSDP opcode dissection, protocol frame structure, authentication exchange verification, and edge-case behavior.

2. **[`AlbanBedel/libnsdp`](https://github.com/AlbanBedel/libnsdp)**
   * **Language**: C
   * **Focus**: Clean C library and CLI utilities for Netgear Switch Discovery Protocol.
   * **Value**: High-performance, zero-runtime-overhead reference implementation. Ideal for cross-compiling directly for OpenWrt (Belkin AX3200 on `192.168.1.226`) or embedding into low-footprint Linux containers.

3. **[`yaamai/go-nsdp`](https://github.com/yaamai/go-nsdp)**
   * **Language**: Go
   * **Focus**: Go package implementing the NSDP protocol.
   * **Value**: Enables building a standalone single-binary CLI or background daemon (e.g. an NSDP-to-REST bridge or a Netgear Prometheus exporter) that can run directly on Proxmox (`pve`) or OpenWrt without Python virtual environments or runtime dependencies.

---

### 🛠️ Non-Windows Automation & Configuration Pathways

| Strategy | Mechanism | Pros | Cons |
| :--- | :--- | :--- | :--- |
| **A. SSH-Exec to PVE** | MCP script SSHs to `pve` (`192.168.1.250`) and runs `manage-netgear-switch.py` in repo `.venv` | Zero new services; uses existing Python tooling | Requires SSH key auth between MCP host and PVE |
| **B. OpenWrt Native Binary** | Compile `libnsdp` or `go-nsdp` into a standalone binary deployed to OpenWrt (`192.168.1.226`) | Runs directly adjacent to GS108E switch; independent of Proxmox | Requires cross-compilation pipeline for OpenWrt target architecture |
| **C. Lightweight Go REST Micro-Daemon** | Run a small Go daemon (`go-nsdp`) on `nexus-server` or `pve` exposing a local REST API (`/status`, `/backup`, `/config`) | Eliminates L2 broadcast limitations for remote MCP tools | Requires maintaining a small service container |
| **D. NSDP UDP Proxy / Relay** | Forward UDP 63321/63322 packets between remote MCP host and VLAN 1 | Keeps tooling remote | NSDP packet formatting expects matching subnet semantics; prone to timeout issues |

---

## 📊 Part 3: Unified Monitoring, SNMP & Observability Roadmap

> **Status: ⏳ Pending — not yet deployed.**
> Prerequisite: All Part 2.x backup & GitOps tasks should be settled before standing up the observability stack to avoid configuration drift.

* **Host**: `nexus-server` (`192.168.40.185`).
* **Components**:
  * `snmp-exporter`: Scrapes Araknis 520 router, Araknis 920 switch, and Araknis 830 APs.
  * `node-exporter`: Hypervisors (`pve`, `pve2`, `pve3`).
  * `cadvisor`: Containers across all 83 Portainer stacks.
  * `pve-exporter`: Proxmox QEMU VM and LXC storage/CPU metrics.
  * `prometheus`: Central TSDB (30-day retention).
  * `grafana`: Unified homelab dashboard.

