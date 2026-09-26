# 🌐 Homelab Network Implementation Plan & Verification Runbook

This implementation plan provides the complete, authoritative, verified roadmap for configuring, securing, auditing, and maintaining your entire homelab network infrastructure.

---

## 📈 Progress Summary — Last Updated 2026-09-25

| Part | Title | Status |
| :--- | :--- | :---: |
| **Part 1** | Core Router & Switch ACL Configuration (21 rules) | ✅ 100% Verified |
| **Part 2** | End-to-End Verification & Testing Runbook (5 tests) | ✅ 100% Verified |
| **Part 2.5** | Multicast & Discovery Architecture (Native Bonjour/IGMP) | ✅ Settled |
| **Part 2.6** | WAN2 & Storage SAN Isolation (untagged vmbr1) | ✅ Settled |
| **Part 2.7** | vxlan-server Split Trunking Architecture (VM 107) | 🟢 Complete — Wire-speed untagged VLAN 1 via AP bridge, isolated tagged VLANs (10, 20, 30, 40, 100, 150, 200) encapsulated over VXLAN 150; STP TCN loops eliminated, PMTU 1500 preserved |
| **Part 2.8** | Netgear GS108Ev2 Office Switch GitOps & Backup | 🟢 Complete — Native NSDP packet driver, L2 relay, and binary/JSON backups verified |
| **Part 2.9** | Wireshark Headless SPAN Sniffer & Storage Engine (Stack 48) | 🟢 Hardened — 500M tmpfs, 50MB chunks, watchdog, continuous 24h FIFO |
| **Part 3** | Unified Monitoring, SNMP & Observability (Grafana stack) | ⏳ Pending — not yet deployed |

### Key Protocol Constraints & Architecture Settled
- **Netgear GS108Ev2** — No HTTP REST API. Uses **NSDP** (Layer 2 UDP, ports 63321/63322). The `backup_netgear_switch` / `get_netgear_switch_status` MCP tools execute via pure Python NSDP using an automated Layer 2 adjacent relay hierarchy: primary OpenWrt router (`192.168.1.226` on `br-lan`) with fallback to Proxmox `pve` (`192.168.1.250` on `vmbr0`). Live telemetry and synchronized dual JSON/binary GitOps backups are 100% verified.

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
| **Bridge VM** | vxlan-server (pve:107) | `192.168.1.150` | VLAN 1 & VLAN 150 | VXLAN Layer 2/3 decapsulator & trunking bridge | 🟢 Active |
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
             │ [Tagged VLANs: 10, 20, 30, 40, 150, 200]                  │
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
2. **Tagged Traffic (VLANs 10, 20, 30, 40, 100, 150, 200)**:
   * Encapsulated into UDP packets (VNI 150, Port 4789, MTU 1450, MSS 1406) by OpenWrt (`192.168.1.226`).
   * Decapsulated by `vxlan-server` (`192.168.1.150`) and injected into Proxmox `vmbr0` with respective 802.1Q tags.
   * Because untagged VLAN 1 is excluded from the tunnel, duplicate Layer 2 paths are physically impossible.
3. **Standby Failover Lifecycle (100% Empirically Verified)**:
   * **Priority 1 (Primary Split-Trunking)**: Untagged VLAN 1 native across physical 830 AP bridge (MTU 1500, wire-speed). Tagged VLANs encapsulated over `vxlan150` to VM 107.
   * **Priority 2 (Wireless VXLAN Fallback)**: Triggered on `wan` carrier loss. OpenWrt redirects `vxlan150` to Wi-Fi 6 station `wl1-sta0` (`192.168.1.225`), adds VLAN 1 to the tunnel, and clamps MSS to 1406. Measured throughput: **573 Mbps, 0 TCP retransmissions, 0% packet loss**.
   * **Priority 3 (Relayd Standby)**: Triggered if both physical wire and VM 107 are offline. OpenWrt activates `relayd` pseudo-bridge on `wl1-sta0` for untagged VLAN 1, maintaining office PC, switch UI, and internet access while tagged VLANs sleep.
   * **Autonomous Recovery & Promotion**:
     * **P3 ➔ P2**: Booting VM 107 triggers instant sub-second detection, stops `relayd`, and cleanly rebuilds `vxlan150` across all VLANs.
     * **P2 ➔ P1**: Reconnecting 830 AP cable restores `wan` carrier, isolates VLAN 1 from VXLAN, sets MTU 1500, and notifies VM 107 via SSH. Latency returns to sub-5ms (2.06ms min) with **0 switch CRC errors across all 8 ports**.

---

## 🔌 Part 2.8: Netgear GS108Ev2 Office Switch — Headless NSDP Architecture & GitOps

### Current State: 🟢 Resolved & Verified (Headless NSDP Native Driver)

| Item | Status |
| :--- | :---: |
| Headless NSDP wire protocol & framing reverse-engineered | ✅ Documented |
| Incompatible web-scraping drivers (`py-netgear-plus`) identified & retired | ✅ Done |
| SOPS-encrypted credentials saved to `infrastructure/secrets/araknis-switch.enc.yaml` | ✅ Done |
| Pure NSDP socket driver & multi-port parser in `manage-netgear-switch.py` | ✅ Verified Live |
| Layer 2 adjacent proxy/runner architecture (OpenWrt `192.168.1.226` / PVE `192.168.1.250`) | ✅ Verified Live |
| Live backup executed & `netgear-gs108e-backup.json` + `netgear-gs108e-backup.cfg` committed | ✅ Done |

---

### ⚠️ Ground Truth: Hardware Realities & Protocol Invariants

1. **Headless Hardware (No Web GUI)**:
   - The Netgear **GS108Ev2** (running firmware `1.00.12`) is an "Easy Smart" ProSAFE Plus switch that is **completely headless**. It does NOT have an HTTP/HTTPS web daemon, SSH server, Telnet listener, or SNMP agent.
   - *Crucial Distinction*: Only subsequent hardware iterations like the **GS108Ev3** incorporate a lightweight embedded web GUI.
   - *Driver Elimination*: All web-scraping libraries (such as `foxey/py-netgear-plus` or `ckarrie/ha-netgear-plus` targeting `login.cgi`) are **completely unusable** on the v2 and produce `ECONNREFUSED` or timeouts.
2. **Protocol Framing (NSDP)**:
   - Management requires raw **NSDP (Netgear Switch Discovery Protocol)** over UDP.
   - Client sends on source UDP **63321**; switch agent listens on UDP **63322**.
   - Fixed 32-byte header (Big-Endian): `Version (0x01)`, `Opcode` (0x01 Read, 0x02 ReadResp, 0x03 Write, 0x17 Token, 0x18 Challenge, 0x1A AuthWrite), `Status` (0x0000 OK), `Manager MAC` (6B), `Agent MAC` (6B), `Sequence` (uint16), Signature `"NSDP"` (`0x4E534450`), and trailing null padding.
   - Variable TLV records concluded with mandatory 4-byte End-of-Message delimiter: `0xFFFF0000`.
3. **Key Register Space**:
   - `0x0001`: Model Name (`GS108Ev2`), `0x0003`: Host Name, `0x0004`: MAC, `0x0006`: IP, `0x000D`: Firmware Bank 1.
   - `0x0C00`: Port Link Matrix (4 bytes/port: Link Status, Speed 10/100/1000M, Duplex, Admin State).
   - `0x1000`: Port Statistics (192 bytes total: 24 bytes/port for Rx/Tx Octets, Packets, CRC errors, Drops).
   - `0x2800`: 802.1Q VLAN Membership & `0x2900`: Port PVID Assignment (16 bytes).
4. **Flash Memory Persistence & Lockout Risk**:
   - Writes commit **immediately to SPI NOR flash** with no volatile staging or uncommitted buffer.
   - Automated scripts must never perform high-frequency writes (flash wear exhaustion).
   - All mutations must be batched atomically into single datagrams with pre-flight invariant validation (uplink PVID & VLAN 1 protection) to avert permanent lockout.

---

### 🏛️ Two-Tier Execution Strategy

Because NSDP is strictly Layer 2 UDP broadcast/unicast on VLAN 1 (`192.168.1.0/24`), frames cannot route across Layer 3 boundaries from remote MCP runners:

```
┌─────────────────────────────────────────────────────────────┐
│                 MCP Control Host / IDE                      │
│     mcp/homelab/scripts/manage-netgear-switch.py            │
│  (Thin client issuing HTTP/JSON to adjacent daemon)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / REST (Port 8080)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│       Adjacent Layer 2 Proxy: OpenWrt Router                │
│             Belkin AX3200 (192.168.1.226)                   │
│  - Micro-daemon (nsdpd) listening on :8080                  │
│  - Bound directly to br-lan (VLAN 1 broadcast domain)       │
│  - Dispatches raw NSDP UDP:63321 -> UDP:63322               │
│  - Handles v2auth, commit-confirm rollback, and TLV packing │
└──────────────────────────────┬──────────────────────────────┘
                               │ Raw NSDP Frames (L2 Broadcast/Unicast)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             Netgear GS108Ev2 Switch (192.168.1.220)         │
│               Headless - ProSAFE Plus Utility Only          │
└─────────────────────────────────────────────────────────────┘
```

* **Target Execution Host A (Recommended)**: OpenWrt Belkin AX3200 (`192.168.1.226`) on `br-lan`. Runs `nsdpd` daemon cross-compiled from `yaamai/go-nsdp` (ARM64 MT7622).
* **Target Execution Host B (Interim / Direct)**: Proxmox `pve` (`192.168.1.250`) on `vmbr0`. Runs native Python NSDP socket script directly adjacent to switch.

---

## 📡 Part 2.9: Wireshark Headless SPAN Sniffer Optimization & Storage Engine (Stack 48 on luna-server)

### Current State: 🟢 Resolved & Hardened (Ready for Deployment)

| Component | Architecture / Setting | Verification |
| :--- | :--- | :---: |
| **Ingress Interface** | `ens19` (VM 102 `tap102i1` on `vmbr1` / `lan1` SPAN mirror) | Promiscuous Mode ON |
| **Drive Wear Protection** | RAM `tmpfs` `/captures` (size increased from 150M to **500M**) | 0 SSD NVMe Writes |
| **Capture Chunk Size** | `-b filesize:50000` (50 MB) + `-b files:100` ring buffer | Prevents Buffer Exhaustion |
| **Process Supervision** | Active watchdog in `tshark-capture` checks PID every 10s | Auto-restarts on crash |
| **Continuous FIFO Pruning** | `find /nas-storage/ -mmin +1440 -delete` + 150-file hard cap | Runs every 5 minutes in loop |
| **Storage Fault Tolerance** | Pre-flight write check on `/nas-storage` before moving chunks | Buffers safely in tmpfs |

### Architecture & Data Flow

```
[Araknis 920 SPAN Mirror] ──► [pve lan1 / vmbr1] ──► [VM 102 ens19]
                                                          │
                                         ┌────────────────┴────────────────┐
                                         ▼                                 ▼
                             [tmpfs /captures (RAM: 500M)]         [Web GUI :3000]
                                 │ (0 Drive Wear / 50MB Chunks)
                                 ▼ (Watchdog & Completed Chunk Mover)
                             [/nas-storage (NFS Mount)]
                                 │ (24-Hour Continuous FIFO + 150-File Safety Cap)
                                 ▼
                             [nas-server VM 101 Storage Pool]
```

---

## 📊 Part 3: Unified Monitoring, SNMP & Observability Roadmap

> **Status: ⏳ Paused / Pre-flight Ready (Host Selected & SNMP Audited)**
> Prerequisite: Resolve VXLAN/OpenWrt failover loop stability first; configure SNMP on Araknis fleet before launching stack.

* **Target Host**: `nexus-server` (`192.168.40.185` / VM 100 on `pve`)
  * *Selection Rationale*: Dedicated to core networking/ingress (NPM, Tailscale, Cloudflared). Eliminates severe I/O competition on `luna-server` (which runs continuous Wireshark SPAN captures in Stack 48 and Home Assistant event logging). Enables direct local ingress without cross-VM hairpinned proxying.
* **Network SNMP Readiness Audit (Screenshots Inspected 2026-09-25)**:
  * **Araknis 520 Core Router** (`192.168.1.1`): `Enable SNMP v1/v2` is currently **OFF**, SNMPv3 is **OFF**.
  * **Araknis 920 Switch** (`192.168.1.215`): SNMP Community list has **No Data** (needs read-only community defined under Server Configuration).
  * **Araknis 830 APs** (`192.168.1.231`, `.236`, `.237`): `SNMPv2 Status` is currently **OFF**, SNMPv3 is **OFF**.
  * *Next Action for Part 3*: Configure read-only SNMPv2c/v3 community across all 5 Araknis devices, store community secret in SOPS (`infrastructure/secrets/`), verify UDP 161 reachability from `nexus-server`, then deploy the unified compose stack.
* **Planned Observability Architecture**:
  * `snmp-exporter`: Scrapes Araknis 520 router, Araknis 920 switch, and Araknis 830 APs.
  * `node-exporter`: Hypervisors (`pve`, `pve2`, `pve3`).
  * `cadvisor`: Containers across all 83 Portainer stacks.
  * `pve-exporter`: Proxmox QEMU VM and LXC storage/CPU metrics.
  * `prometheus`: Central TSDB (30-day retention, persistent volume).
  * `grafana`: Unified homelab dashboard exposed via NPM and Tailscale.


