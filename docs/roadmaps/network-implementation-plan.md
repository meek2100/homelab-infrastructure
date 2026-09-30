# 🌐 Homelab Network Implementation Plan & Verification Runbook

This implementation plan provides the complete, authoritative, verified roadmap for configuring, securing, auditing, and maintaining your entire homelab network infrastructure.

---

## 📈 Progress Summary — Last Updated 2026-09-29

| Part | Title | Status |
| :--- | :--- | :---: |
| **Part 1** | Core Router & Switch ACL Configuration (21 rules) | ✅ 100% Verified |
| **Part 2** | End-to-End Verification & Testing Runbook (5 tests) | ✅ 100% Verified |
| **Part 2.5** | Multicast & Discovery Architecture (Native Bonjour/IGMP) | ✅ Settled — 2026-09-29: IGMP snooping + querier added for VLAN 30; AP mDNS gate off on MGMT SSID; 2026-09-30: luna HA/Homebridge bound to ens18 (verified), Vivint panel mDNS blocked on SW920 1/0/17 (runbook) |
| **Part 2.6** | WAN2 & Storage SAN Isolation (untagged vmbr1) | ✅ Settled |
| **Part 2.7** | vxlan-server Split Trunking Architecture (VM 107) | 🟢 Complete — 2026-09-29: fixed 30 s tunnel-rebuild loop (59–73% office loss → 0%); VLAN 100 removed from tunnel; 2026-09-30: `TAGGED_VLANS="10 30"` deployed on both ends; tester re-run pending |
| **Part 2.8** | Netgear GS108Ev2 Office Switch GitOps & Backup | 🟢 Complete — Native NSDP packet driver, L2 relay, and binary/JSON backups verified |
| **Part 2.9** | Wireshark Headless SPAN Sniffer & Storage Engine (Stack 48) | 🟢 Hardened — 2026-09-29: unicast now captured (vmbr1 ageing 0 / learning off); 500M tmpfs, 50MB chunks, 8-file ring; 2026-09-30: vmbr1 hub mode + GRO off persisted, 512 B snaplen, VLAN-aware filter, open-file-safe background NAS worker as `abc`, soft `/mnt/captures` mount |
| **Part 2.10**| Pakedge SX-8P Managed Switch & Work Testbench Lifecycle | 🟢 Complete — 2026-09-29: STP off + BPDU flooding, SW920 1/0/7 admin-edge + BPDU Guard (tested), trunk 1,10,150,200; ⚠️ power is WattBox, not PoE — `power_cycle_pakedge_switch` needs rework |
| **Part 3** | Observability Engine & Synthetic Probing (Stack 71) | 🟢 100% Deployed & Active (10 containers, Alertmanager, Blackbox, external targets) |
| **Part 4** | Unified Full-Fleet Control Center, External Systems & PBS Foundation | 🟢 100% Deployed & Active (49/49 targets UP, distributed agent pods active on 5 VMs, Loki streaming all containers) |
| **Part 5** | Production Operationalization, PBS Migration & External GitOps | 🟢 100% Operationalized (PBS Active Cluster-Wide, Backups Verified, Alerts Active, External VPS FastMCP Active) |
| **Part 5.6** | Phase 2 Automation, External Log Shipping & GitOps Drills | 🟢 100% Complete & Operationalized (Snapshot FastMCP, Device Auto-Sync, Promtail Tooling, GitOps Drills) |
| **Part 6** | Comprehensive Architectural Learnings & Production Gotchas | 📚 24 Critical Learnings Documented & Fleet-Hardened |
| **Part 7** | 2026-09-29 Capture-Driven Network Remediation (SPAN/pcap analysis) | 🟡 In Progress — core faults fixed; open items tracked in Part 7 checklist |
| **Part 8** | Compute Platform Review (pve hosts, VMs, LXCs, Docker, GPU) | ⏸️ Future — starts once the network is stable and all important config/state is in git |

### Key Protocol Constraints & Architecture Settled
- **Netgear GS108Ev2** — No HTTP REST API. Uses **NSDP** (Layer 2 UDP, ports 63321/63322). The `backup_netgear_switch` / `get_netgear_switch_status` MCP tools execute via pure Python NSDP using an automated Layer 2 adjacent relay hierarchy: primary OpenWrt router (`192.168.1.226` on `br-lan`) with fallback to Proxmox `pve` (`192.168.1.250` on `vmbr0`). Live telemetry and synchronized dual JSON/binary GitOps backups are 100% verified.
- **Pakedge SX-8P Managed Switch** — Embedded `Hydra/0.1.8` web server with Backbone.js SPA (`192.168.1.205`, static, DHCP off). Connected via 802.1Q trunk (native VLAN 1 untagged; tagged 10, 150, 200) to Araknis 920 Port 1/0/7. **Mains-powered via its own adapter on a WattBox outlet** switched by a Control4 button (90-minute auto-off, together with SA1 on 1/0/5 and Core5 on 1/0/8); its ports 1–8 are PoE *outputs*, so toggling PoE on 920 1/0/7 does not power it. STP disabled with BPDU Processing = Flooding; 920 1/0/7 is Admin Edge + BPDU Guard (verified 2026-09-29). Ports 2–7 = VLAN 10 (main-system test gear), port 8 = VLAN 150 (CA-1). Exempt from 24/7 uptime SLOs; probes labeled `environment: 'testbench-ondemand'`.

---



## 🏛️ Empirical Network Architecture & IP Reference

| Equipment | Model | IP Address | Subnet / VLAN | Role | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Core Router** | Araknis 520 Dual-WAN | `192.168.<vlan>.1` on every VLAN | VLANs 1, 10, 20, 30, 40, 150, 200 (100 excluded) | Layer 3 Gateway, Interzone Routing, NAT, ACL Firewall, DHCP (all VLANs), global Bonjour repeater | 🟢 Active |
| **Core Switch** | Araknis 920 Managed | `192.168.1.215` | VLAN 1 (Management) | 10G/2.5G L2+ Distribution, **RSTP root (priority 4096)**, BPDU Guard on edge ports, IGMP Snooping + Querier (VLANs 1, 10, 20, 30, 40), SPAN session 1 (1/0/1 Tx/Rx → 1/0/24) | 🟢 Active |
| **AP 1 (Master)**| Araknis 830 Wi-Fi 7 | `192.168.1.231` | VLAN 1 (Management) | Broadcasts SSIDs + Wired Master for 5GHz PTP Bridge | 🟢 Active |
| **AP 2 (Core)** | Araknis 830 Wi-Fi 7 | `192.168.1.236` | VLAN 1 (Management) | Broadcasts SSIDs (Ch 1 / 149 / 69) | 🟢 Active |
| **AP 3 (Bridge)**| Araknis 830 Wi-Fi 7 | `192.168.1.237` | VLAN 1 (Management) | Dedicated Wireless Bridge Client (Insomniac_Bridge) | 🟢 Active |
| **Office Switch**| Netgear GS108Ev2 | `192.168.1.220` | VLAN 1 (Management) | Desktop distribution switch behind OpenWrt — **No official API/CLI; managed via NSDP (UDP 63321/63322)** | 🟢 Active |
| **Test Switch**  | Pakedge SX-8P Managed | `192.168.1.205` | VLAN 1 (trunk tagged 10/150/200) | Work Automation Lab / Testbench — **powered on demand by the Control4 **Office → All Test Equipment** button (WattBox 11 relay; 90 min auto-off)** | 🟡 On-Demand |
| **Office Router**| Belkin AX3200 (OpenWrt) | `192.168.1.226` (`br-lan`), `192.168.1.225` (`wl1-sta0`), `10.99.99.1` (out-of-band mgmt on `lan1`/`br-mgmt`) | VLAN 1 (+ tagged 10/30 bridged to VXLAN VNI 150) | 3-Priority Failover (Wire, VXLAN VNI 150, Wi-Fi repeater). BusyBox `ash` only — no bash | 🟢 Active |
| **WAN2 Router** | Asus RT-N66U (DD-WRT Aurora)| `10.25.25.1` & `10.20.20.2` | WAN2 / `10.25.25.0/24` | Torrent/discovery isolation with PIA VPN auto-watchdog | 🟢 Active |
| **Upstream GW** | DD-WRT Luna | `10.20.20.1` | `10.20.20.0/24` | Upstream transit gateway (firewalled from WAN) | 🟢 Active |
| **Admin VM** | nexus-server (pve:100)| `192.168.40.185` | VLAN 40 (Servers) | WireGuard (:51820), Tailscale (:69), AdGuard Home Primary (:53), NPM | 🟢 Active |
| **DNS2 VM** | nexus-server2 (pve3:100)| `192.168.40.186` | VLAN 40 (Servers) | AdGuard Home Secondary (:53) | 🟢 Active |
| **Smart Home VM**| luna-server (pve:102) | `192.168.40.249` | VLAN 40 (Servers) | Home Assistant (:8123), Homebridge (:8581), Spoolman (:7912), Syncthing (:22000), SPAN Mirror (:ens19) | 🟢 Active |
| **Media VM** | media-server (pve:103) | `192.168.40.247` | VLAN 40 (Servers) | Plex (:32400 with Intel P630 QuickSync), Audiobookshelf | 🟢 Active |
| **NAS VM** | nas-server (pve3:101) | `192.168.40.248` & `10.25.25.248` | VLAN 40 & SAN | OpenMediaVault Storage (SMB / NFS) | 🟢 Active |
| **Download VM** | discovery-server (pve2:100)| `10.25.25.246` | Dedicated WAN2 SAN | VPN automated torrent & discovery engine | 🟢 Active |
| **Gaming VM** | minecraft-server (pve:109)| `192.168.40.175` | VLAN 40 (Servers) | Minecraft Bedrock Connect / Proxy | 🟢 Active |
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

> **VLANs 150 / 200 (work testbench) are isolated by Interzone Forwarding, not by the ACLs above.** Both zones have every "Allow forward TO/FROM" box unchecked and Device Management off. ACL Rule 1 (Any → AdGuard DNS) still permits their DNS. Verified 2026-09-29 in a SPAN capture: CA-1 (`192.168.150.200`) attempts to reach CA-10 (`192.168.10.200`:8883/6002) were rejected by the router (ICMP port-unreachable from `192.168.150.1`). The global Bonjour repeater cannot be scoped per VLAN, so home mDNS service names are still *visible* in 150/200 (information-only; no L3 path).

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

### 2026-09-29 Findings & Adjustments (from SPAN capture)
* **IGMP**: 920 snooping *and* querier now cover VLANs **1, 10, 20, 30, 40** (VLAN 30 was missing both). Never enable snooping on a VLAN without its querier. VLANs 150/200 intentionally left off (testbench, mostly powered down).
* **AP "mDNS Forwarding" is a per-SSID gate, not a second repeater**: when off, that SSID's mDNS is blocked from leaving its network; the 520's Bonjour repeater does the cross-VLAN copy. Kept **on** for Insomniac / Guest / IOT, **off** for Insomniac_MGMT (AP1 + AP2). Captures showed no AP-originated mDNS, so no duplicate forwarder.
* **mDNS was ~60% of all captured bytes.** Two amplifiers: (1) the **Vivint Security Panel** (`192.168.10.108`, `88:6a:e3:d8:eb:1c`, SW920 1/0/17, identified 2026-09-30 from its DNS/TLS traffic to `app.vivintsky.com` / `vivint.ai`) querying ~16/s nonstop for Chromecast/Spotify/HomeKit/Hue/Matter/Thread services — vendor firmware behaviour, not configurable; (2) luna (`192.168.40.249`) — Homebridge's HAP records (confirmed; Home Assistant likely too) carry **all 8 Docker bridge addresses (172.17–172.25.0.1) plus ~17 veth link-locals** in every reply, pushing responses over 1500 bytes (158k IP fragments/19 h) which the repeater then copies into 6 VLANs and which cannot cross the 1450-MTU VXLAN. **Fix pending**: bind Homebridge (`bridge.bind: ["ens18"]`, incl. child bridges) and Home Assistant (Settings → System → Network → ens18 only) to `ens18`.
* **The repeater leaks home service names into testbench VLANs 150/200** (cannot be scoped per VLAN on the 520). Accepted as information-only; optional future control is a UDP 5353 filter toward the Pakedge.

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
2. **Tagged Traffic (`TAGGED_VLANS` — single source in `failover.sh` and vxlan-server `vxlan-nm`)**:
   * **2026-09-29**: reduced to the VLANs that actually have office devices per the Netgear VLAN table — **10** (Control4 Core-1/Core-3/T5/SA1, HP & Brother printers) and **30** (Office Apple TV). VLAN 100 (SPAN isolation) is never tunneled. Repo updated; live deploy of `"10 30"` + one-time `bridge vlan del` of 20/40/150/200 pending (Part 7). Previously `10, 20, 30, 40, 100, 150, 200`.
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
4. **P1 Integrity Check & Rebuild Guard (fixed 2026-09-29)**:
   * The integrity check (commit `bedc269`) tested `ip link show vxlan150 | grep "state UP"`. VXLAN devices report `state UNKNOWN` even when healthy, so the check always failed and cron (`* * * * * failover.sh -m; sleep 30; failover.sh -m`) **deleted and rebuilt vxlan150 every 30 s** — also flushing ARP and re-running `vxlan-nm -p1` on VM 107. Result: **59–73% packet loss** to every office device on tagged VLANs, router ARP answered only 26–35% of the time, flapping Prometheus alerts.
   * Fix: `vxlan_admin_up()` checks the admin `UP` flag (`grep -qE "[<,]UP[,>]"`); `integrity_restore()` allows at most **one integrity rebuild per 300 s** and logs `WARNING … NOT rebuilding` on repeats. Verified live: office ping **0% loss** (100/100 in and out of `vxlan150`); two AP reboots at 21:19 and 21:31 recovered as `P1 check failed (1–2/3) → P1 recovered` with no rebuild.
   * The frozen `known-good/openwrt/scripts/failover.sh` still contains the same `state UP` test in its P2 path (line 332) — do not restore it unmodified.
5. **Failover-tester VLAN probe**: probes `PROBE_VLAN_ID` (default **10**, target gateway `192.168.10.1`). Before assigning its temporary /32, it runs an RFC 5227 duplicate-address probe (ARP from `0.0.0.0`, scapy or BusyBox/iputils `arping -D`) — the broadcast crosses `vxlan150`, so one probe covers hosts on both sides — and steps down from `LOCAL_VLAN_IP` (default `.254`) through `.240` until a free address is found. If all 15 answer, the test records `V<id>:ERR` and assigns nothing, so it can never cause a conflict. Keep `.240`–`.254` outside the VLAN 10 DHCP pool. On a VLAN-filtering bridge (OpenWrt `br-lan`, and vxlan-server `br0`, where `vxlan-nm` adds only vid 1 to the CPU port) the tester adds the probe VID to the bridge CPU port and removes it at teardown only if it added it — fix for the 2026-09-30 remote `V10:FAIL`. The duplicate-address result is reported as unverified when the probe path itself fails.

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

### Current State: 🟢 Deployed & Capturing Full Traffic (2026-09-29)

| Component | Architecture / Setting | Verification |
| :--- | :--- | :---: |
| **SPAN Source** | SW920 session 1: `1/0/1` (Araknis 520 router, 2.5G) Tx/Rx → probe `1/0/24` (1G, access VLAN 100 dead-end) | Router-crossing traffic only; inter-VLAN flows appear twice (router-on-a-stick); probe port can drop under >1G load |
| **Ingress Interface** | `ens19` (VM 102 `tap102i1` on `vmbr1` / `lan1` SPAN mirror), firewall off | Promiscuous Mode ON |
| **Bridge Learning (critical)** | `vmbr1` must flood everything: `bridge-ageing 0` + `bridge link set dev lan1 learning off`. With learning on, the bridge learned every mirrored MAC on `lan1` and **dropped all mirrored unicast** — captures before 2026-09-29 18:51 contain zero TCP | Applied live 2026-09-29; **persist in `/etc/network/interfaces` pending** |
| **Drive Wear Protection** | RAM `tmpfs` `/captures` **500M** (live since 2026-09-29) | 0 SSD NVMe Writes |
| **Capture Chunk Size** | `-b filesize:50000` (50 MB), `-s 256` snaplen, `-b files:8` ring (8 × 50 MB < tmpfs: a NAS outage overwrites the oldest RAM chunk instead of ENOSPC-crashing dumpcap) | Deployed 2026-09-29 |
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

## 🔌 Part 2.10: Pakedge SX-8P Managed Switch — Work Automation Testbench & Lifecycle Automation

### Current State: 🟢 Resolved & Integrated (On-Demand FastMCP Tooling)

| Item | Status |
| :--- | :---: |
| Physical uplink & 802.1Q trunk (Port 1/0/7 on Araknis 920) | ✅ Documented & Active |
| FastMCP telemetry tool (`get_pakedge_switch_status`) | ✅ Verified Live (11 learned MACs) |
| FastMCP remote power tool (`power_cycle_pakedge_switch`) | ⚠️ Ineffective — toggles PoE on 920 1/0/7, but the SX-8P is mains-powered via WattBox; rework to WattBox control pending |
| Loop protection: STP off + BPDU flooding on SX-8P; 920 1/0/7 Admin Edge + BPDU Guard | ✅ Verified 2026-09-29 (1 BPDU → 1/0/7 disabled, as designed) |
| FastMCP config backup tool (`backup_pakedge_switch`) | ✅ Integrated with SOPS credentials |
| Prometheus synthetic probe & alert suppression | ✅ Configured (`environment: 'testbench-ondemand'`) |
| Grafana Smart Home & Control4 Dashboard integration | ✅ Provisioned with Standby/Online badge |

---

### 🏛️ Architecture & Hardware Topology

1. **Role & Hardware Profile**:
   - Model: **Pakedge SX-8P** (8-port Gigabit Managed PoE+ Switch).
   - Management IP: **`192.168.1.205`** (VLAN 1).
   - Upstream Switch: **Araknis 920 Managed Switch** (`192.168.1.215`), Interface `1/0/7`.
   - Power (Control4 programming reviewed 2026-09-30): the Control4 **Office → All Test Equipment** button drives three separate relays.
     - **On** (after 5 s, and only if timer `Testing Equipment Off` is not running): close *Rack Room → Wattbox 11 (Test Equipment)* (the SX-8P's own adapter; 920 1/0/12 is the WattBox), then +1 s *Office → Triad SA1* relay, then +1 s *Office → Remotes n Touchscreens* relay.
     - **Off**, or expiry of the 90-minute `Testing Equipment Off` timer: macro `Testing Equipment` opens each closed relay (SA1 and Remotes 2 s after clearing their `State Flipping` variables) and sets the button state Off.
     - SA1 (920 1/0/5, access VLAN 200) is on its **own Triad relay**, not the WattBox outlet. Core5 (920 1/0/8, access VLAN 200) comes up with the same button; which relay feeds it is not yet confirmed. 920 1/0/7 still has `poe high-power 4ptdot3af`, which has no effect (SX-8P ports are PoE outputs).
   - Trunk Configuration: 802.1Q trunk carrying native untagged **VLAN 1** (Management) and tagged **VLAN 10**, **150** (`CA-1 Test`), **200** (`Core-5 Test`) — pruned on both the SX-8P (port 1 hybrid) and 920 1/0/7 (`1,10,150,200`) on 2026-09-29.
   - Port map (live 2026-09-29): ports 2–7 access **VLAN 10** (DS2 door station, Luma X20 cams, Pakedge PoE switch on 6 (device to confirm), EA1 + unmanaged switch on 7 — main-system test gear); port 8 access **VLAN 150** (CA-1); port 9 VLAN 1.
   - Spanning tree: **disabled** on the SX-8P (global + per port), **BPDU Processing = Flooding** so a loop behind it returns the 920's BPDUs; 920 1/0/7 is **Admin Edge + BPDU Guard** and shuts the port on the first BPDU. The SX-8P has no BPDU guard / loop detection of its own. SX-8P MAC `90:A7:C1:9E:D9:26` is higher than the 920's, so it could never win a root election at equal priority.
   - SNMP: `public` read-write removed; `homelab-metrics` read-only only.

2. **On-Demand Power & SLA Invariant**:
   - The Pakedge switch and attached test equipment serve strictly as a work automation testbench.
   - **Powered Down When Idle**: Kept unpowered when active testing is not in progress.
   - **Exempt from 24/7 SLA**: Alertmanager rules explicitly suppress `TargetDown` and `BlackboxProbeFailed` alerts for targets with `environment: 'testbench-ondemand'`.
   - **Remote Power Control**: Power is the Control4 button. The legacy command below only toggles PoE on 920 1/0/7 and does **not** power the SX-8P. Its replacement should trigger the Control4 button/macro rather than the WattBox outlet directly: toggling only the outlet would leave SA1, the remotes relay, the button state and the auto-off timer out of sync.
     ```bash
     python3 mcp/homelab/scripts/manage-pakedge-switch.py poe-cycle --port 7   # ineffective — see above
     ```

3. **GitOps Backup & Management Tooling**:
   - Tool script: [`mcp/homelab/scripts/manage-pakedge-switch.py`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/manage-pakedge-switch.py).
   - FastMCP Native Tools in [`mcp/homelab/server.py`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/server.py):
     - `get_pakedge_switch_status`: Audits switch reachability (HTTP/Telnet) and inspects upstream Araknis Port 1/0/7 MAC table.
     - `backup_pakedge_switch`: Authenticates to Pakedge Hydra web server, initiates configuration export, and saves backup to `infrastructure/network/configs/pakedge-sx8p-running.cfg` (⚠️ the committed copy predates the 2026-09-29 VLAN/SNMP/STP changes — refresh).
     - `configure-vlans` (CLI action): re-applies the live layout (VLANs 10/150/200; gi1 tagged 10,150,200; gi2–7 access 10; gi8 access 150) over **Telnet**. Additive only (does not remove VLANs) and unusable if Telnet is disabled; not yet run against the live switch.
     - `power_cycle_pakedge_switch`: Toggles PoE on Araknis 920 Port 1/0/7 over FASTPATH SSH CLI (⚠️ does not power the mains-powered SX-8P — rework to WattBox pending).

---

## 📊 Part 3: Unified Monitoring, SNMP, Proxmox & Observability (Grafana LGTM Stack)

> **Status: 🟢 100% Deployed & Active (Stack 71 on `nexus-server`)**
> Deployed and verified 2026-09-26. Central TSDB, SNMP telemetry, Proxmox hypervisor API exporter, host metrics, container analytics, and Grafana Loki log engine active with auto-provisioned Grafana dashboards.

* **Target Host**: `nexus-server` (`192.168.40.185` / VM 100 on `pve`)
  * *Selection Rationale*: Dedicated to core networking/ingress (NPM, Tailscale, Cloudflared). Eliminates I/O competition on `luna-server` (which runs continuous Wireshark SPAN captures in Stack 48). Enables direct local ingress without cross-VM hairpinned proxying.
  * *Blueprint*: [`infrastructure/docker-stacks/nexus-server/71-monitoring/`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/71-monitoring/)
* **Live Service & Port Matrix (10 Containers)**:
  * **Grafana (`11.1.0`)**: Port `3030:3000` (Web UI at `http://192.168.40.185:3030` or reverse-proxied via NPM / Tailscale `http://100.70.65.45:3030`)
  * **Prometheus TSDB (`v2.53.1`)**: Port `9090:9090` (30-day persistent retention, active alerting rules engine)
  * **Alertmanager (`v0.27.0`)**: Port `9093:9093` (Pushover mobile priority alerts & SMTP notification routing)
  * **Blackbox Exporter (`v0.25.0`)**: Port `9115:9115` (HTTP/HTTPS, DNS UDP, TCP, and TLS SSL cert expiration probing)
  * **Grafana Loki (`3.0.0`)**: Port `3100:3100` (High-efficiency log aggregation engine with `v13` TSDB index schema)
  * **Promtail Agent (`3.0.0`)**: Internal (Direct Docker socket integration dynamically discovering 20 containers and host syslogs)
  * **PVE Exporter (`latest`)**: Port `9221:9221` (Scrapes Proxmox hypervisors `pve`, `pve2`, `pve3` via read-only `monitoring@pve` API tokens)
  * **SNMP Exporter (`v0.26.0`)**: Port `9116:9116` (Scrapes Araknis router, switch, AP fleet, and office printers)
  * **Node Exporter (`v1.8.2`)**: Port `9100:9100` (Host OS, CPU, RAM, disk, load averages)
  * **cAdvisor (`v0.49.1`)**: Port `8088:8080` (Container-level CPU, RAM, and network I/O)
* **2026-09-29 changes (deployed via `deploy-monitoring-stack.py`, verified live)**:
  * Exporter host ports bound to **`127.0.0.1`** (blackbox 9115, snmp 9116, pve 9221, cadvisor 8088) — confirmed closed from the LAN. Prometheus 9090, Alertmanager 9093, Grafana 3030 and Loki 3100 (Promtail push) remain LAN-reachable.
  * **node-exporter** runs `network_mode: host` + `pid: host` (real VM NICs); scraped as `192.168.40.185:9100`.
  * **Proxmox jobs** scrape every **60 s** (pve-exporter opened ~4,500 TLS sessions per 11 min at 15 s).
  * **Grafana admin password** comes from `GRAFANA_ADMIN_PASSWORD` in `secrets.enc.yaml` → compose `.env` (mode 600); live DB password reset via `grafana cli`.
  * **Printers**: SNMP community moved from `public` to `homelab-metrics` on both printers (auth `public_v2`, set per target via `__param_auth`); HP web probe targets `/DevMgmt/ProductStatusDyn.xml` (the EWS home page truncates its body and fails blackbox).
  * **T5 touchscreen** moved from HTTP to a new `blackbox_icmp` job (it RSTs port 80).
  * The office-device probe failures (Core-1, Core-3, T5, printers) were caused by the VXLAN rebuild loop (Part 2.7 §4), not stale IPs — the VLAN 10 addresses are correct.
  * Known follow-ups: the deploy script's `chmod -R 755` makes `grafana.db`/secrets world-readable, and its health checks print 🟢 on failure; Home Assistant and Homebridge are each probed twice.
* **Active Target Inventory (as of 2026-09-29 ~21:00: all up except `pakedge-sx8p-switch` when the testbench is off)**:
  * 🟢 `192.168.1.1`: Araknis 520 Core Router (`snmp_infrastructure`, `if_mib` via community `homelab-metrics`)
  * 🟢 `192.168.1.215`: Araknis 920 Switch (`snmp_infrastructure`, `if_mib` - 24 ports + SFP+)
  * 🟢 `192.168.1.231`: Araknis 830 AP 1 House Front (`snmp_access_points`, `ap_system`)
  * 🟢 `192.168.1.236`: Araknis 830 AP 2 House Back (`snmp_access_points`, `ap_system`)
  * 🟢 `192.168.1.237`: Araknis 830 AP 3 Office Bridge (`snmp_access_points`, `ap_system`)
  * 🟢 `192.168.10.195`: HP Color LaserJet MFP M283cdw (`snmp_printers`, `printer_mib` - 4 toners, 1,739 lifetime pages)
  * 🟢 `192.168.10.196`: Brother QL-1110NWB (`snmp_printers`, `printer_mib` - 1,399 labels, console state `READY`)
  * 🟢 `192.168.1.250`: Proxmox Node 1 `pve` (`proxmox_pve` - Dell Precision 5520, VMs 100, 102, 103, 107, 109)
  * 🟢 `192.168.1.240`: Proxmox Node 2 `pve2` (`proxmox_pve2` - Awow AK34Pro, VM 100 discovery-server; storage NIC `10.25.25.240`)
  * 🟢 `192.168.1.245`: Proxmox Node 3 `pve3` (`proxmox_pve3` - HP EliteDesk, VMs 100 nexus-server2, 101 nas-server)
  * 🟢 `http://192.168.40.185:3030`: Grafana web frontend (`blackbox_http`)
  * 🟢 `http://192.168.40.185:81`: Nginx Proxy Manager admin UI (`blackbox_http`)
  * 🟢 `http://192.168.40.249:8123`: Home Assistant UI (`blackbox_http`)
  * 🟢 `http://192.168.40.247:32400/identity`: Plex Media Server identity API (`blackbox_http`)
  * 🟢 `https://192.168.40.185:9443`: Portainer management UI (`blackbox_http`)
  * 🟢 `https://192.168.40.185:9443`: Portainer TLS certificate expiration tracker (`blackbox_ssl`)
  * 🟢 `https://theurer.dev`: External Web Server frontend HTTP 200 (`blackbox_http`)
  * 🟢 `https://theurer.dev`: External Web Server SSL expiration tracker (`blackbox_ssl`)
  * 🟢 `https://mail.theurer.dev`: External Mail Server webmail HTTP 200 (`blackbox_http`)
  * 🟢 `https://mail.theurer.dev`: External Mail Server SSL expiration tracker (`blackbox_ssl`)
  * 🟢 `mail.theurer.dev:587`: External Mail SMTP Submission port probe (`blackbox_tcp`)
  * 🟢 `mail.theurer.dev:993`: External Mail IMAPS secure retrieval probe (`blackbox_tcp`)
  * 🟢 `192.168.40.185:53`: AdGuard Home Primary DNS probe (`blackbox_dns`)
  * 🟢 `192.168.40.186:53`: AdGuard Home Secondary DNS probe (`blackbox_dns`)
  * 🟢 `alertmanager:9093`: Alertmanager self-telemetry
  * 🟢 `blackbox-exporter:9115`: Blackbox Exporter self-telemetry
  * 🟢 `node-exporter:9100`: Local `nexus-server` host metrics
  * 🟢 `cadvisor:8080`: Docker container metrics
  * 🟢 `localhost:9090`: Prometheus self-monitoring
* **Active Prometheus Alerting Rules (9 Production Rules)**:
  * `TargetDown`: Triggers if any scrape target is unreachable for > 2m (Severity: Critical)
  * `BlackboxProbeFailed`: Triggers if any HTTP service or DNS probe fails (Severity: Critical)
  * `DNSResolutionFailed`: Triggers if AdGuard Home fails resolving queries (Severity: Critical)
  * `SSLCertExpiringSoon`: Triggers if TLS cert expires in < 14 days (Severity: Warning)
  * `SwitchPortLinkDown`: Triggers if core trunks 1/0/1–1/0/4 go down (Severity: Warning)
  * `SwitchPortCRCErrors`: Triggers on frame corruption or ingress CRC errors (Severity: Warning)
  * `PrinterSupplyLow`: Triggers if printer toner or labels drop below 15% (Severity: Warning)
  * `NodeHighCPU`: Triggers if host CPU exceeds 90% for 5m (Severity: Warning)
  * `NodeLowDiskSpace`: Triggers if host disk available space drops below 15% (Severity: Warning)
* **Pre-Provisioned Dashboards**:
  * **Homelab Network & Infrastructure Overview (v4)**: UID `homelab-network-overview` under folder `Homelab Network`. Displays real-time device health stat cards, router WAN bandwidth, switch top-active port throughput, printer toner levels (K/C/M/Y gauges), Proxmox node online states, VM CPU/RAM utilization graphs, and live interactive Loki log streams.
* **Management Tooling**:
  * [`mcp/homelab/scripts/deploy-monitoring-stack.py`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/deploy-monitoring-stack.py): Programmatic lifecycle control (`deploy`, `status`, `stop`) with automated Proxmox API token generation, permissions hardening, and container health verification.

---

## 🎛️ Part 4: Unified Full-Fleet Observability, External Control Center & PBS

> **Status: 🟢 100% Deployed & Operational**
> Unifies all 155 containerized apps across 85 stacks, all 3 Proxmox hypervisors, physical networking hardware, external infrastructure (`theurer.dev`, `mail.theurer.dev`), centralized Loki logging, and establishes the blueprint for Proxmox Backup Server (PBS).

### 1. External Systems Architecture (`theurer.dev` & `mail.theurer.dev`) — 🟢 100% Integrated

A comprehensive external telemetry, diagnostic, and log ingestion framework protecting critical web and email infrastructure without compromising internal LAN security boundaries:

- **Security Invariants**:
  - Outbound synthetic probes and secure VPN log shipping.
  - Zero inbound ports opened on the residential/homelab router.
  - All public metrics collected non-intrusively from the monitoring stack.

- **Suite of FastMCP Tools** (Integrated in [`mcp/homelab/server.py`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/server.py)):
  - `get_external_services_status`: Executes full health audit across web (`theurer.dev`), mail (`mail.theurer.dev`), SSL certificates, and public DNS records.
  - `check_ssl_certificates`: Continuous tracking of TLS/SSL certificate expiration dates and days remaining for HTTPS (443) and IMAPS (993).
  - `audit_email_pipeline`: In-depth mail diagnostic testing Postfix submission handshake on port 587, IMAPS retrieval on port 993, and Roundcube webmail HTTP response.

- **Continuous 24/7 Synthetic Prometheus Monitoring**:
  - `https://theurer.dev`: HTTP 200 validation and SSL expiration countdown (`blackbox_http` & `blackbox_ssl`).
  - `https://mail.theurer.dev`: Webmail HTTP 200 validation (`blackbox_http`).
  - `mail.theurer.dev:587`: TCP connect, latency, and banner check (`220 mail.theurer.dev ESMTP Postfix`) (`blackbox_tcp`).
  - `mail.theurer.dev:993`: IMAPS TLS port check (`blackbox_tcp` & `blackbox_ssl`).
  - **Alerting Rules**: `ExternalServiceDown` (P1 Critical, Pushover siren) and `ExternalSSLCertExpiringSoon` (Warning if < 14 days).

- **Consolidated External Log Ingestion Pipeline (Loki 3.0)**:
  - **Architecture**: Distributed Promtail daemon instances installed on the external Ubuntu web and mail hosts.
  - **Transport**: Secured via private Tailscale mesh (or WireGuard client connecting to Stack 20 `wg-easy`) forwarding directly to `http://100.x.y.z:3100/loki/api/v1/push`.
  - **Log Streams Captured**:
    - Nginx Web Server: `/var/log/nginx/access.log` and `/var/log/nginx/error.log` (labeled `service="theurer.dev-web"`).
    - Postfix & Dovecot Mail Server: `/var/log/mail.log` and `/var/log/mail.err` (labeled `service="theurer.dev-mail"`).
    - Host Security / SSH: `/var/log/auth.log` (monitoring for failed external SSH attempts).
  - **Unified Log Explorer**: Live streams, full-text regex search, and security auditing fully unified inside the **Homelab Command & Control Center** Grafana dashboard.

### 2. Proxmox Backup Server (PBS) Centralization — 📄 Runbook Ready
- **Goal**: Retire legacy per-node `vzdump` full dumps and replace with fast, deduplicated incremental backups over the dedicated `10.25.25.0/24` SAN network (`vmbr1`).
- **Runbook**: [`docs/runbooks/proxmox-backup-server.md`](file:///home/agentsvc/repos/homelab-infrastructure/docs/runbooks/proxmox-backup-server.md)
- **Status**: Complete step-by-step instructions documented in [`.agents/MANUAL-SETUP-TODOS.md`](file:///home/agentsvc/repos/homelab-infrastructure/.agents/MANUAL-SETUP-TODOS.md) for installation on `pve3` and client registration across `pve`, `pve2`, and `pve3`.

### 3. Distributed Fleet Telemetry Pods (Full In-Guest & Container Visibility) — 🟢 100% Deployed & Active
- **Deployed Fleet**: Standardized lightweight telemetry agent pods (`node-exporter` :9100 + `cAdvisor` :8088) deployed across all Docker VMs via `mcp/homelab/scripts/deploy-telemetry-fleet.py`:
  - 🟢 `luna-server` (VM 102 — Smart Home & SPAN sniffer, 33 stacks)
  - 🟢 `media-server` (VM 103 — Plex, Media transcode, 9 stacks)
  - 🟢 `nexus-server2` (VM 100 on `pve3` — Secondary DNS, 7 stacks)
  - 🟢 `minecraft-server` (VM 109 — Gaming)
  - 🟢 `nexus-server` (VM 100 — Ingress, Stack 71)
- **Scrape Status**: 5/5 Node Exporters and 5/5 cAdvisors 🟢 UP in Prometheus (Total active scrape targets: **49/49 UP**).

### 4. Consolidated Fleet Logging (Loki 3.0 + Promtail DaemonSets) — 🟢 100% Deployed & Active
- **Architecture**: Distributed Promtail instances dynamically scraping Docker container logs (`/var/run/docker.sock`) and host syslogs, tagging with `vm`, `container`, and `stream`, pushing to `http://192.168.40.185:3100/loki/api/v1/push`.
- **Active Streaming**: 42+ distinct containers and 4 VMs streaming live logs into central Loki within the first minute of deployment.
- **Capabilities**: Global full-text search across all containers, instant stack-level filtering, and cross-VM error correlation in Grafana.

### 5. Master Homelab Command & Control Center Dashboard — 🟢 100% Deployed & Active
- **Dashboard File**: [`infrastructure/docker-stacks/nexus-server/71-monitoring/grafana/provisioning/dashboards/homelab-command-center.json`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/docker-stacks/nexus-server/71-monitoring/grafana/provisioning/dashboards/homelab-command-center.json)
- **Generator**: [`mcp/homelab/scripts/generate-command-center-dashboard.py`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/generate-command-center-dashboard.py)
- **URL**: `http://192.168.40.185:3030` (`uid: homelab-command-center`)
- **26 Real-Time Panels across 6 Functional Rows**:
  1. **Executive Vitals & Global Health**: Active Prometheus Scrape Targets (49 UP), Active Containers, Active Alerts, Hypervisors Online, Router WAN Real-Time Bandwidth (Tx/Rx).
  2. **External Systems & Mail Infrastructure**: `theurer.dev` HTTP Status & SSL Days Remaining, `mail.theurer.dev` Webmail Status, SMTP Submission (:587) Open/Closed, IMAPS (:993) Open/Closed, and Mail SSL Days Remaining.
  3. **Physical Network & Hardware Supplies**: Araknis 920 Switch Active Port Real-Time Throughput (Top Ports), HP LaserJet M283cdw Toner Gauge Supplies (K/C/M/Y).
  4. **Proxmox Hypervisors & Fleet In-Guest Performance**: VM In-Guest CPU Utilization (%) & In-Guest RAM Consumption across all VMs.
  5. **Docker Container Fleet Telemetry (cAdvisor)**: Top 8 Containers by Memory Usage, Top 8 Containers by CPU Utilization across all VMs.
  6. **Application Web Services & API Matrix**: Real-time HTTP health stat grid (Grafana, NPM, Portainer, Home Assistant, Plex, AdGuard Primary & Secondary).
  7. **Consolidated Live Loki Log Explorer**: Unified log explorer streaming stdout/stderr from all VMs and 42+ containers with instant regex search and multi-label filtering.

---

## 🚀 Part 5: Production Operationalization, PBS Migration & Hardening (Remaining Roadmap)

> **Status: 🟡 Active Implementation Phase**
> This part bridges completed Phase 1 read-only audits and monitoring into full production operationalization across backup pipelines, cluster-wide storage registration, symmetrical routing remediation, and alert routing validation.

### 5.1: Hypervisor Symmetrical Routing Remediation (`pve2` Asymmetric Blackhole Fix) — 🟢 COMPLETE
- **Current State**: 🟢 **Completed & Operational**.
- **Resolved Remediation**:
  1. Prometheus Stack 71 scrape target for `pve2` was realigned to standard management IP `192.168.1.240` (commit `24d7f40`).
  2. NPM reverse proxy host `pve2.secure.theurer.dev` ➔ `https://192.168.1.240:8006` verified with HTTP 200 and live WebSockets.
  3. Wire-speed storage network (`vmbr1`, `10.25.25.0/24`) is completely isolated and verified transmitting PBS daily backups at 112.8 MiB/s wire speed without inter-VLAN interference.

### 5.2: Proxmox Backup Server (PBS) Cluster-Wide Storage Activation
- **Current State**: 🟢 **Completed & Operational**. CT 105 (`pbs-server`) is running on `pve3` with services `proxmox-backup` and `proxmox-backup-proxy` active. Storage `/backup/pbs-datastore` bind-mounted to `/mnt/pve/backup/pbs-datastore`. Web UI active at `https://192.168.1.244:8007` and `https://10.25.25.244:8007`. Storage pool `pbs-backup` registered and online across all 3 nodes (`pve`, `pve2`, `pve3`).
- **Resolved Blockers**:
  1. *Permission Intersection*: Token was upgraded to `DatastorePowerUser` (`proxmox-backup-manager acl update /datastore/homelab-datastore DatastorePowerUser --auth-id 'pve-backup@pbs!backup-token'`) to grant `Datastore.Prune` required by PVE retention routines.
  2. *Encryption Key Sync across Standalone Nodes*: Standalone PVE nodes do not share `/etc/pve/priv/storage/`. Working key `pbs-backup.enc` was SCP'd from `pve` to `pve2` and `pve3`.

### 5.3: Transition Backup Schedules (Legacy vzdump ➔ PBS Daily Incremental CBT)
- **Current State**: 🟢 **Completed & Verified Across All 3 Nodes**.
- **Empirical Initial Seed Verification (All `TASK OK`)**:
  - **`pve` (pve1)**: Successfully backed up test VM to `pbs-backup`.
  - **`pve2`**: VM 100 (`discovery-server`, 50GB disk) completed in **7m 28s** at 112.8 MiB/s wire speed with client encryption `55:67:8b:75...` and clean pruning.
  - **`pve3`**:
    - VM 100 (`nexus-server2`, 50GB disk): Completed in **61 seconds** (839 MiB/s, 85% sparse/reused).
    - VM 101 (`nas-server`, 505GB disks): Completed in **49m 56s** (371 GiB / 73% sparse zero data skipped thanks to pre-backup `fstrim`), CBT dirty-bitmaps established.
    - CT 105 (`pbs-server` rootfs): Completed in **17 seconds** (909 MiB compressed to 316 MiB, bind-mount `/backup` safely excluded).
- **Ongoing Automation**:
  - Unified daily snapshot schedule registered targeting `pbs-backup` with retention: `keep-daily=7, keep-last=7, keep-weekly=4, keep-monthly=12`.

### 5.4: End-to-End Alerting Pipeline Validation & Routing Verification
- **Current State**: 🟢 **Completed & Verified Operational**. Alertmanager Stack 71 actively evaluates alerts and dispatches via dual notification channels.
- **Empirical Validation**:
  - Synthetic critical test alert successfully triggered (`alertname="TestAlert"`).
  - **Pushover**: High-priority alert notification and emergency siren delivered to mobile phone (`priority: 1`, `sound: siren`).
  - **SMTP**: Delivered cleanly to `darin@theurer.dev` via SMTP2Go smarthost (`mail.smtp2go.com:587`, TLS upgraded).
- **Production Rules Active**: 9 production alert rules evaluated 24/7 across all network switches, Proxmox hypervisors, containers, certificates, and printers (`SwitchPortLinkDown`, `SwitchPortCRCErrors`, `PrinterSupplyLow`, `SSLCertExpiringSoon`, `TargetDown`, `BlackboxProbeFailed`).

### 5.5: External Host Audit, Zero-Trust Logging & GitOps Recovery — 🟢 COMPLETE
- **Architecture**: Zero-exposure ingestion via Cloudflare Tunnel (`logs.theurer.dev/loki/api/v1/push`) with Bearer token authentication, eliminating public VPS presence inside internal Tailscale or LAN subnets.
- **Milestones Completed (2026-09-28)**:
  1. **Non-Destructive Deep Audits**: Completed across both external cloud VPS instances using dedicated SSH key pairs (`free-main-server_id_ed25519` and `free-email-server_id_ed25519`):
     - `web-server` (`theurer.dev` on Oracle Cloud / `146.235.203.133`): Ubuntu 24.04.5 LTS, Nginx HTTP/2 + TLS 1.3, PHP 8.3-FPM, MariaDB 10.11.14, Fail2Ban, hosting `theurer.dev`, `ivyhairlounge.com`, `theivyhairlounge.com`.
     - `email-server` (`mail.theurer.dev` on Google Cloud / `35.212.229.212`): Ubuntu 24.04.5 LTS, Postfix MTA (port 25, 587 STARTTLS), Dovecot IMAP/POP3 (port 993, 995, 110), Rspamd milter + Redis cache, Roundcube Webmail, Postfix Admin, and Fail2Ban.
  2. **GitOps Blueprints & Backups**: Version-controlled in `infrastructure/external-hosts/web-server/` and `infrastructure/external-hosts/email-server/` with automated configuration archives, Nginx vhosts, Postfix/Dovecot active configs, and Fail2Ban jail definitions.
  3. **FastMCP Lifecycle & Security Management**: Built `mcp/homelab/scripts/manage-external-hosts.py` and registered 6 dedicated native FastMCP tools in `mcp/homelab/server.py`:
     - `audit_external_hosts(host)`: Remote execution of baseline audit and SCP bundle synchronization.
     - `backup_external_host(host)`: Automated extraction of configuration snapshots to local GitOps repository.
     - `get_external_security_status(host)`: Real-time queries for Fail2Ban active jails, banned IPs, UFW firewall status, and listening sockets.
     - `get_external_services_status()`: Synthetic external reachability probes (HTTP 200, TLS verification).
     - `check_ssl_certificates()`: Live certificate lifecycle audits and expiration warnings.
     - `audit_email_pipeline()`: End-to-end SMTP submission banner, IMAPS, and webmail status.
  4. **Cloudflare Restricted Ingress**: Loki log push endpoint (`https://logs.theurer.dev/loki/api/v1/push`) mapped in Stack 100 on `nexus-server` with Bearer token authentication, ready for Promtail log shipping from both VPS instances.


### 5.6: Phase 2 Automation, Scheduled Snapshots & GitOps Drills — 🟢 COMPLETE
- **Action Items & Operational Verification**:
  1. **Programmatic VM/LXC Snapshot Automation**: 🟢 **Operational**. FastMCP tool `manage-vm-snapshots.py` (`snapshot_vm`, `list_vm_snapshots`, `rollback_vm`, `delete_vm_snapshot`, `backup_vm_vzdump`) supports both QEMU VMs (`qm`) and Linux Containers (`pct`), allowing zero-friction snapshot creation prior to any container or guest OS upgrade.
  2. **Switch & Router GitOps Automation**: 🟢 **Operational**. Dedicated FastMCP tools (`backup_araknis_switch`, `backup_araknis_router`, `backup_netgear_switch`, `backup_openwrt`) programmatically export and version-control live device configurations with drift detection.
  3. **External Cloud VPS Lifecycle Tools**: 🟢 **Operational**. FastMCP tools (`audit_external_hosts`, `backup_external_host`, `get_external_security_status`) manage `theurer.dev` and `mail.theurer.dev` without manual shell commands.
  4. **Promtail External Log Ingestion**: 🟢 **Operational Tooling Deployed**. FastMCP tool `deploy_external_promtail` in `mcp/homelab/scripts/deploy-external-promtail.py` provisions systemd service `/etc/systemd/system/promtail.service` on both external VPS hosts, tailing Nginx access/error, Postfix, Dovecot, and Fail2Ban security logs directly into central Loki.
  5. **Periodic GitOps Drills & Secret Rotation**: 🟢 **Operationalized**. Complete runbook published in [`docs/runbooks/gitops-drills-and-secret-rotation.md`](file:///home/agentsvc/repos/homelab-infrastructure/docs/runbooks/gitops-drills-and-secret-rotation.md) establishing exact step-by-step procedures for age key rotation across 68 stacks and disaster recovery rollback drills for Netgear NSDP, Araknis router/switch, and PBS incremental backups.

---

## 🧠 Part 6: Comprehensive Architectural Learnings & Production Gotchas

This section records empirical hard-won discoveries and architectural invariants established during homelab hardening.

### 1. Proxmox Backup Server (PBS) Token Permission Intersection
- **The Gotcha**: Proxmox Backup Server evaluates API token permissions using an intersection rule:
  $$\text{Effective Permissions} = \text{User Permissions} \cap \text{Token Permissions}$$
- **The Failure Mode**: Creating an API token `pve-backup@pbs!backup-token` and granting it `DatastoreBackup` on `/datastore/homelab-datastore` while the parent user `pve-backup@pbs` has no permissions results in an empty permission set. When PVE nodes run `pvesm add pbs`, PBS rejects the connection with:
  `create storage failed: pbs-backup: Cannot find datastore 'homelab-datastore', check permissions and existence!`
- **The Invariant**: Always grant parent user permissions (`DatastoreAdmin` on `/datastore` and `DatastoreAudit` on `/`) or assign permissions directly to the user identity before generating backup tokens.

### 2. Debian 13 (Trixie) 64-bit time_t Drift vs. Debian 12 LXC Isolation
- **The Gotcha**: Host `pve3` runs Debian 13 (Trixie testing) which underwent the Debian 64-bit `time_t` ABI transition (e.g. `libapt-pkg6.0t64`, `libsgutils2-1.48t64`). Upstream Proxmox Backup Server packages are currently compiled strictly for Debian 12 (Bookworm) (`libapt-pkg6.0`, `libsgutils2-2`). Installing PBS directly on bare-metal `pve3` breaks APT package resolution with unresolvable dependencies.
- **The Solution**: Provisioning a lightweight Debian 12 LXC container (`CT 105`) on `pve3` with nesting enabled and bind-mounting the host backup disk (`/mnt/pve/backup` ➔ `/backup`) completely isolates the host OS from Debian library drift, allowing PBS to install official packages cleanly in under 2 minutes.

### 3. Hypervisor Multi-Homing & Asymmetric Routing (`rp_filter` Blackhole)
- **The Gotcha**: Assigning IP addresses to VLAN sub-interfaces (e.g. `vmbr0.40` on `192.168.40.240/24`) on a hypervisor whose physical uplink port is an untagged access port creates silent packet loss.
- **The Failure Mode**: When an inter-VLAN request arrives from `nexus-server` (`192.168.40.185`) on `vmbr0`, Linux kernel Strict Reverse Path Filtering (`rp_filter=1`) checks the routing table. Because the route for `192.168.40.0/24` points to `vmbr0.40`, the kernel drops the packet as spoofed. Even if accepted, replies are transmitted with 802.1Q tags onto an untagged switch port, breaking NPM reverse proxying and Tailscale routing.
- **The Invariant**: Hypervisors must maintain a single management IP on VLAN 1 (`192.168.1.0/24`) with default gateway `192.168.1.1` on `vmbr0`, and an isolated SAN IP on `vmbr1` (`10.25.25.0/24`). Never configure host IPs on VM VLANs (`vmbr0.40`, `vmbr0.50`).

### 4. QEMU Guest Agent (QGA) Binary Base64 Corruption & Stdin Hangs
- **The Gotcha**: Using `qm guest exec` to extract files from guest VMs returns standard output wrapped in a JSON envelope (`{"out-data": "..."}`). Piping this output directly to a host file irreversibly corrupts binary formats (SQLite databases, compressed tarballs).
- **The Invariant**: All binary data extracted via QGA must be base64-encoded inside the guest (`base64 -w 0 <file>`), parsed from JSON, and decoded using `base64.b64decode()` in Python. Conversely, passing raw text via stdin with `--pass-stdin 1` hangs indefinitely without a TTY; files written into guests must be base64-encoded on the host and decoded inside the VM via `echo '<b64>' | base64 -d > <target>`.

### 5. Docker Compose Container Name Collisions on Redeployment
- **The Gotcha**: When deploying or re-deploying Docker Compose stacks with explicit container names (`container_name: ...`), pre-existing stopped or exited containers cause Docker Compose to abort with `Conflict. The container name "..." is already in use`.
- **The Invariant**: Deployment scripts (`deploy-monitoring-stack.py`, `restore-docker-stacks.py`) must inspect container lifecycle states, removing exited containers prior to invoking `docker compose up -d`.

### 6. File Metadata & UID/GID Preservation Gap
- **The Gotcha**: Extracting configuration files or databases from containers via `cat` or QGA completely strips Linux file permissions (`chmod`) and ownership (`chown`). Restoring a container database as `root:root` (0:0) instead of the required application UID (e.g. UID 1000 for Home Assistant or NPM) triggers immediate container crash loops with `Permission Denied`.
- **The Invariant**: File extraction scripts must record file metadata using `stat -c '%a:%u:%g'` alongside content and re-apply permissions upon restoration.

### 7. Multicast Forwarding Loops & Permanent Retirement of Software Relays
- **The Gotcha**: Containerized software relays (such as `multicast-relay` or `avahi-daemon` bridging multiple Docker networks) forward multicast packets across interfaces in userspace. When running in a network with hardware mDNS repeaters, software relays create duplicate forwarders, causing severe broadcast storms, switch port damping, and FDB MAC flapping.
- **The Invariant**: Multicast discovery across VLANs must be handled exclusively by native hardware: the Araknis 520 Bonjour mDNS repeater and Araknis 920 IGMP Snooping Querier. Software multicast bridges are permanently retired.

### 8. Wireless Point-to-Point Bridge 802.1Q Tag Stripping & Split Trunking
- **The Gotcha**: The Araknis 830 AP 5GHz wireless backhaul strips 802.1Q VLAN tags across the link to the office. Bridging untagged VLAN 1 in parallel with a virtual tunnel causes instant Layer 2 broadcast loops and switch port shutdown.
- **The Invariant**: Split Trunking architecture: Untagged VLAN 1 (Management) traverses the physical wireless bridge natively at wire speed (1500 MTU). The tagged VLANs listed in `TAGGED_VLANS` (currently 10 and 30 — only VLANs with office devices) are encapsulated into VXLAN UDP packets (Port 4789, MTU 1450, MSS 1406) terminated by `vxlan-server` (VM 107). Mutual exclusion prevents Layer 2 loops while providing transparent multi-VLAN trunking. Every VLAN in the list floods its broadcast/multicast across the Wi-Fi tunnel, so keep it minimal.

### 9. Headless Switch NSDP Layer 2 Broadcast Boundaries
- **The Gotcha**: The Netgear GS108Ev2 switch has no HTTP web interface, SSH server, or SNMP agent. Management relies entirely on the proprietary Netgear Switch Discovery Protocol (NSDP) over UDP (ports 63321/63322). Because NSDP frames are Layer 2 broadcast/unicast, management scripts cannot cross Layer 3 subnets.
- **The Invariant**: NSDP commands must execute either on an adjacent Layer 2 proxy (OpenWrt `192.168.1.226` on `br-lan`) or directly on a local hypervisor (`pve` `192.168.1.250` on `vmbr0`). Furthermore, all writes commit immediately to SPI NOR flash with no volatile staging, requiring atomic batching and pre-flight validation.

### 10. Laptop Hypervisor Power & Backlight Management
- **The Gotcha**: Proxmox installed on a laptop (`pve` Dell Precision 5520) defaults to suspending the system when the lid is closed, and keeps the high-brightness panel backlight active even when unattended.
- **The Invariant**: Systemd logind configured with `HandleLidSwitch=ignore`, and an ACPI event script (`/etc/acpi/lid-backlight.sh`) toggles the Intel panel backlight to 0 on lid close and 400 on open, saving power and preventing thermal throttling without interrupting hypervisor operations.

### 11. Proxmox Backup Server (PBS) Post-Backup Pruning Role Invariant
- **The Gotcha**: Proxmox VE evaluates storage retention policies (`prune-backups keep-daily=7,keep-last=7...`) immediately upon backup task completion. If the API token is only granted `DatastoreBackup`, PBS rejects the post-backup cleanup with a 403 Forbidden error on `Datastore.Prune` (`permission check failed for Datastore.Prune`).
- **The Invariant**: Effective token permissions must include `DatastorePowerUser` (or `DatastoreAdmin`) on `/datastore/<datastore-name>`.

### 12. Standalone Hypervisor Encryption Key Synchronization
- **The Gotcha**: Standalone Proxmox hosts do not participate in a shared PVE cluster filesystem (`/etc/pve/`). Client-side PBS encryption keys generated on Node 1 (`/etc/pve/priv/storage/pbs-backup.enc`) do not replicate automatically. Missing or malformed keys on standalone nodes cause QEMU tasks to abort with `failed to load decryption key` and LXC tasks to fail with `fingerprint too long at line 1 column 260`.
- **The Invariant**: Client encryption keys and `/etc/pve/notifications.cfg` must be distributed across all standalone hypervisors via `scp` from `pve1` to ensure identical cryptographic and alert configurations across the fleet.

### 13. SMTP Submission (Port 587 STARTTLS) vs. Implicit SMTPS (Port 465 SSL)
- **The Gotcha**: Port 465 uses direct SSL socket wrapping from byte 0 and does not advertise the `STARTTLS` extension. Applications implementing standard Go `net/smtp` (like Prometheus Alertmanager) require an explicit TLS upgrade over port 587 (`STARTTLS`). Pointing Alertmanager to port 465 with `require_tls: true` triggers continuous retry failures (`does not advertise the STARTTLS extension`).
- **The Invariant**: Always route Alertmanager through submission port 587 with `STARTTLS`. Furthermore, Alertmanager requires a container restart to apply disk configuration changes unless `--web.enable-lifecycle` is explicitly passed in container arguments.

### 14. Portainer External Stack Mechanics & Zero-Downtime Adoption
- **The Gotcha**: Containers launched outside Portainer via `docker compose up` carry Docker compose labels (`com.docker.compose.project`), allowing Portainer to detect the stack. However, because Portainer's internal BoltDB (`portainer.db`) lacks the stack metadata and compose file text, it locks the Web Editor with: `Information: This stack was created outside of Portainer. Control over this stack is limited.`
- **The Solution (Zero Downtime Adoption)**: In Portainer Web UI, create a new stack (**Add Stack**) with the exact matching stack name and paste the compose file from the Git repository. When **Deploy the stack** is clicked, Docker Compose recognizes the running containers by name and network, leaves them untouched ("Container ... is up to date"), and Portainer records the stack in its BoltDB, unlocking full Web UI editing with zero container restarts.

### 15. Zero-Exposure Cloud VPS Architecture & Promtail Log Shipping
- **The Invariant**: Public cloud VPS instances (`theurer.dev`, `mail.theurer.dev`) must NEVER join internal Tailscale mesh networks or be granted inbound routing into homelab subnets. Telemetry and logs must ship outward via Cloudflare Tunnel (`logs.theurer.dev/loki/api/v1/push`) authenticated with Bearer tokens.
- **The Rationale**: Breaching an external cloud VPS must never provide a direct network path or lateral movement bridge into home IoT, storage, or hypervisor networks.

### 16. External VPS Lifecycle Automation & Fail2Ban Permission Isolation
- **The Gotcha**: Cloud VPS instances enforce strict public-key authentication per host (`free-main-server_id_ed25519` for Oracle Cloud, `free-email-server_id_ed25519` for Google Cloud). Running manual interactive shell scripts on mobile terminals causes multi-word commands to wrap at column ~70, injecting arguments as separate shell errors. Furthermore, `fail2ban-client` communicates via a Unix domain socket (`/var/run/fail2ban/fail2ban.sock`) owned exclusively by `root:root`, returning `Permission denied` to non-root users even though the jail configurations in `/etc/fail2ban/` and active iptables rules are readable.
- **The Solution**: Native FastMCP tools (`audit_external_hosts`, `backup_external_host`, `get_external_security_status`) encapsulate the SSH keys, profiles, and error handling into Python `manage-external-hosts.py`. Configuration backups gracefully skip root-protected secret tokens while archiving Nginx, MariaDB, Postfix, Dovecot, Rspamd, and Fail2ban jail structures directly into GitOps.

### 17. VXLAN Interfaces Report `state UNKNOWN` When Healthy
- **The Gotcha**: VXLAN (and other carrier-less virtual) devices show `<BROADCAST,MULTICAST,UP,LOWER_UP> … state UNKNOWN` in `ip link`. A health check of `grep "state UP"` is therefore always false.
- **The Failure Mode**: `failover.sh` treated the tunnel as down on every cron pass and rebuilt it every 30 s (plus ARP flush and a remote `vxlan-nm -p1`), causing 59–73% loss for every office device on tagged VLANs.
- **The Invariant**: Test the admin flag (`grep -qE "[<,]UP[,>]"` or `/sys/class/net/<if>/flags`), and rate-limit any self-healing rebuild so a broken check cannot become an outage loop.

### 18. A Linux Bridge in Front of a SPAN Capture VM Drops Mirrored Unicast
- **The Gotcha**: Mirrored frames all arrive on the physical SPAN port, so a learning bridge (`vmbr1`) learns every source MAC on that port and then drops every unicast frame whose destination is "on the port it came in on". Only broadcast/multicast/unknown-unicast reach the VM.
- **The Invariant**: A SPAN bridge must act as a hub: `bridge-ageing 0` and `bridge link set dev <nic> learning off`, persisted in `/etc/network/interfaces`, with the bridge used for nothing else.

### 19. Pin the STP Root; Linux Bridges Speak Slow 802.1D
- **The Gotcha**: The office OpenWrt bridge advertised priority `0x7fff` (32767), beating the Araknis 920 default 32768 — the office router became root of the whole house whenever its BPDUs reached the 920. Linux kernel bridges only speak legacy 802.1D, so the 920 ports that hear them (1/0/2 pve, 1/0/3 AP1 bridge) fall back to 30–50 s timers after any topology change.
- **The Invariant**: 920 bridge priority **4096**; OpenWrt `br-lan` priority **61440**; optional future step `mstpd` for RSTP on the Linux bridges.

### 20. Edge Ports + BPDU Guard Protect Against Switches That Cannot Protect Themselves
- **The Pattern**: Downstream switch with STP off and BPDU flooding → upstream port Admin Edge + BPDU Guard. Any loop behind it returns a BPDU and the upstream port is disabled instead of the house storming. Admin Edge also stops WattBox power cycles from generating topology changes.
- **The Invariant**: Never use Admin/Auto Edge or BPDU Guard on ports that legitimately carry BPDUs (920 1/0/2 and 1/0/3 have Auto Edge off). Recovery after a trip: fix the cause, then re-enable the port (temporarily untick global BPDU Guard if the downstream switch is unreachable).

### 21. MAC-Based VLAN Classifies Ingress Only
- **The Gotcha**: A 920 MAC-based VLAN entry puts a device's *outgoing* frames into the VLAN, but replies only egress ports that are members of that VLAN. On an access port of a different VLAN the device can send but never receive.
- **The Failure Mode**: The OvrC-MoIP controller (`D4:6A:91:62:A2:7E`, MAC-VLAN 10) ARPed its gateway every second for 16 h; the router's replies and ARPs never reached it.
- **The Invariant**: Use a normal access VLAN on the port; MAC-based VLAN entries were deleted 2026-09-29.

### 22. Containers Leak Docker Bridge Addresses into mDNS
- **The Gotcha**: Homebridge (confirmed in captures) — and likely Home Assistant — advertise every host interface, all Docker bridges and veths, in their mDNS answers, inflating replies past 1500 bytes and handing clients unreachable 172.x addresses.
- **The Invariant**: Bind mDNS advertisers to the real LAN interface (`ens18`).

### 23. OpenWrt Runs BusyBox `ash`
- **The Gotcha**: No bash, no `timeout` applet; `2>/dev/null` hid a `timeout: not found` error and made a tcpdump test look like a result.
- **The Invariant**: OpenWrt scripts and runbook commands must be POSIX `sh`; bound captures with `( cmd & P=$!; sleep N; kill $P )` or `tcpdump -c N`; do not silence errors in diagnostics.

### 24. Reading a Router-on-a-Stick SPAN Correctly
- **The Gotcha**: Mirroring the router port (Tx/Rx) shows every inter-VLAN packet twice (in on VLAN A, out on VLAN B) and never shows same-VLAN device-to-device traffic. Naive tools report the second copy as a TCP retransmission.
- **The Invariant**: Analyse per VLAN tag (`vlan.id`), treat the mirror as router-crossing traffic only, and temporarily add device ports as extra mirror sources for same-VLAN problems.

---

## 🩺 Part 7: 2026-09-29 Capture-Driven Network Remediation

> **Status: 🟡 In Progress** — Source: 19.3 h broadcast-only baseline (2026-09-28 21:10 → 2026-09-29 16:44 PDT) plus an 11-minute full-traffic capture after the SPAN fix. Analysis with `dpkt` in the `personal-ai` WSL distro (no Wireshark on the workstation).

### Findings & Root Causes
| # | Finding | Root Cause | Status |
| :---: | :--- | :--- | :---: |
| 1 | Captures contained zero TCP | `vmbr1` learning bridge dropped mirrored unicast (Learning 18) | ✅ Fixed live; persist pending |
| 2 | 59–73% loss to office devices on tagged VLANs | `failover.sh` rebuilt `vxlan150` every 30 s (Learning 17) | ✅ Fixed & verified (0% loss) |
| 3 | Office tagged devices held VLAN 1 addresses overnight | Exact cause not captured (broadcast-only data); cleared when the 2026-09-29 16:15–16:51 failover/trunk-port changes landed | ✅ Resolved (devices on VLAN 10/30) |
| 4 | Office router was STP root; 802.1D interop | Default priorities (Learning 19) | ✅ 920 = 4096; OpenWrt 61440 pending confirmation |
| 5 | Testbench "STP storm" | STP on the SX-8P + no edge/guard on 920 1/0/7 | ✅ STP off + Admin Edge + BPDU Guard (tested) |
| 6 | mDNS ≈ 60% of captured bytes, 158k fragments | Query-storm client `.10.108` + luna advertising Docker IPs (Learning 22) | 🟡 Binding fix pending |
| 7 | Router ARP sweeps of empty VLANs 150/200 every ~20 s | Most likely OvrC client discovery on the 520 while the testbench is powered off (not proven) | ✅ Understood; stops when testbench is up |
| 8 | OvrC-MoIP controller could send but not receive | MAC-based VLAN (Learning 21) | 🟡 MAC-VLAN deleted; give controller a VLAN 10 port |
| 9 | vxlan-server DNS pointed at dead `.1.249` / `.1.186` | Stale pre-re-IP resolv.conf | ✅ Now `.40.185`, `.40.186`, `.1.1` |
| 10 | Monitoring exposure & false alerts | Open exporter ports, default Grafana creds, bad probes | ✅ Deployed (Part 3) |
| 11 | mainsail offline ~22 h | Pi hang/Wi-Fi stuck (logs lost to RAMlog) | ✅ Back; RAMlog #2 set; Wi-Fi monitor recommended; no watchdog (would kill prints) |
| 12 | DNS: `.local` search domain junk, AdGuard bypass | DHCP domain `local`; Google devices/APs/Pakedge hardcoded DNS | 🟡 Pending |

### Applied (verified live 2026-09-29)
- [x] `vmbr1` `ageing_time 0` + `lan1 learning off` (runtime)
- [x] `failover.sh` integrity fix + 300 s rebuild guard; `TAGGED_VLANS` variable; VLAN 100 removed from `vxlan150`/`lan2-4` (OpenWrt) and `vxlan150`/`ens18` (vxlan-server)
- [x] vxlan-server `/etc/resolv.conf` → `192.168.40.185`, `192.168.40.186`, `192.168.1.1`
- [x] SW920: bridge priority 4096; BPDU Guard; Admin Edge 1/0/5, 1/0/7, 1/0/8; Auto Edge off 1/0/2, 1/0/3; IGMP snooping + querier VLAN 30; VLAN 100 removed from all trunks; 1/0/7 = `1,10,150,200`; MAC-based VLAN entries deleted
- [x] pve `vmbr0` VLAN IDs `10 20 30 40 150 200`; pve3 `vmbr0` VLAN IDs `40`
- [x] SX-8P: STP disabled, BPDU flooding, VLANs 1/10/150/200 only, static IP, SNMP `homelab-metrics` RO only
- [x] APs: Fast Roaming off on Insomniac_Guest; mDNS Forwarding off on Insomniac_MGMT; AP3 5 GHz DFS off
- [x] Printers on SNMP `homelab-metrics`; monitoring stack redeployed (Part 3); Grafana password rotated
- [x] Capture stack: 500M tmpfs, 50 MB chunks, 8-file ring, 256 B snaplen
- [x] mainsail: DietPi-RAMlog #2; hardware watchdog deliberately not used

### Capture Review — 2026-09-29 21:39 → 09-30 00:47 (11 files, snaplen 256)

> ⚠️ **Correction (overnight files 09-30 00:47–06:21):** the SPAN lost **all unicast from ~22:24 on 9/29**. The user applied pve VLAN changes in the Proxmox GUI at about that time, which reloads the bridges and reset the runtime-only `vmbr1` hub settings (`ageing_time 0`, `lan1 learning off`). As a result:
> - The retransmission, DNS and ARP-reply figures below cover only **21:39–22:24**.
> - The 5× packet-rate drop at 22:25 was this fault, not usage ending.
> - The overnight files hold broadcast/multicast only (0 ARP replies, 0 TCP, 0 DNS; 8 unicast frames in 5.6 h). What they still show: STP stable (10,030 BPDUs, root `0x1000`, 0 TC); the router ARP sweep heavier overnight (VLAN 1 ≈ 30/s, VLAN 200 ≈ 20/s, VLAN 150 ≈ 12/s, VLAN 10 ≈ 5/s; about 90% of all captured frames); Vivint panel mDNS ≈ 4.6/s (IPv4 + IPv6); most-requested ARP targets `.1.181`, `.1.205` (Pakedge, powered off) and `.1.112`.
>
> Fix: re-apply the runtime settings on pve and persist them in `/etc/network/interfaces` (repo copies updated 2026-09-30).

**Healthy:**
- STP: 4,200 BPDUs, all with root `0x1000`/SW920, and **0 topology changes**.
- Office TCP retransmission-like segments are **4.1%**, down from 35.5% before the §4 integrity fix. That figure is inflated by Director MQTT retries to the powered-off `.10.213` and `.10.220`.
- OpenWrt `.1.225` and `.1.226` each map to one MAC, so no ARP flapping.

**Problems:**

| Finding | Evidence | Action |
|---|---|---|
| Capture mover lost 46 min (23:11–23:57) | Chunk `00007` reached the NAS as a 278-byte header. The mover treated the newest-mtime file as active, so it `mv`'d the still-open chunk across filesystems | Repo fix: skip files held open by dumpcap (`/proc/<pid>/fd`); tested against the race. Also 2026-09-30: NAS copies and pruning run as linuxserver user `abc` (= `PUID:PGID` 1000:1000), not root, so files are usable over SMB/NFSv4 even with root squash. Files are written as a hidden `.partial` and renamed when complete (mode 664, timestamps kept); failed copies are retried |
| Mirror path merges packets (GRO) | IP lengths >1500 from WAN hosts (Netflix `45.57.x`), i.e. GRO/LRO coalescing on pve `lan1` → `tap102i1` → luna `ens19` | `ethtool -K lan1 gro off lro off` (pve) and `ethtool -K ens19 gro off lro off` (luna); persist with the vmbr1 hub-mode change |
| snaplen 256 hides DHCP | All 170 DHCP frames are cut before the options (they start at byte ~286) | `SNAPLEN` raised to **512** in the repo `tshark-capture` (2026-09-30); deploy stack 48 |
| Router ARP sweep on every VLAN | All 254 addresses on each VLAN. VLAN 1 and VLAN 200 ≈ every 10 s (~25/s and ~21/s), VLAN 150 ≈ every 24 s, VLANs 10/20/30/40 every 3–8 min. It makes up ~99% of VLAN 1/150/200 broadcasts | OvrC/520 discovery scan; limit per the OvrC VLAN settings |
| Vivint panel mDNS is dual-stack | IPv4 78k + **IPv6 74.5k** packets (≈13.5/s combined) | The mDNS block needs an IPv6 ACL as well as the IPv4 one |
| DNS queries without a response | `.40.186` 741/2,364 (31%), `.40.185` 1,546/14,345 (11%), `8.8.8.8` 31% | Check the AdGuard query logs and per-client rate limits; decide whether direct 8.8.8.8 use should be blocked or redirected |
| mainsail `.30.90` link quality | 67% repeated segments from `.40.185:443` → `.30.90` | 2026-09-30 08:21: `-60 dBm`, 2.4 GHz channel 1, rx 39 / tx 57.7 Mbit/s, associated to BSSID `1a:3f:c3:e8:b9:95`. Correction: that BSSID sits next to AP `.1.231`'s MAC (`14:3f:c3:e8:b9:93`), so mainsail connects to **AP `.1.231`**, not the AP3 wireless bridge; there is no double wireless hop. **Uptime shows a reboot at ~02:13 on 9/30**; the cause is unknown because the journal is volatile under RAMlog. Check power-save, the undervoltage flags and any watchdog |
| Work laptop dual-homed on VLAN 1 | Realtek USB Ethernet `.1.117` (`a0:29:19:8f:5d:45`, 12.7% repeated segments; EEE, Green Ethernet and Idle Power Saving enabled) **and** Wi-Fi `.1.186` on the same subnet | Disable Wi-Fi when wired or turn off the Realtek power-saving features (IT-managed laptop); move off VLAN 1 |
| Control4 Core5 "Dinner Time" on VLAN 1 | `.1.181` ↔ Director `.10.200` MQTT/TLS routed between VLANs, 5% repeated segments | Move to VLAN 10 with the rest of Control4 |
| DHCP search domain `.local` | Lookups such as `stats.grafana.org.local` and `api.local` | Supports the pending DHCP domain → `home.arpa` change |
| Vivint `192.168.1.112` still dead | 1,792 unanswered router ARPs, 83 RTSP SYNs from the panel | See the Vivint camera / Smart Drive items |
| Homebridge mDNS fragments (pre-fix) | 3,102 fragmented mDNS datagrams from `.40.249` | Fixed 2026-09-30 (ens18 binding verified) |
| AP3 `.1.237` uses two MACs | `14:3f:c3:e8:b9:20` (replies) and `36:3f:c3:e8:b9:23` (wireless-bridge STA MAC, requests) | Expected for a Wi-Fi client bridge. Watch only |

### Capture Review — 2026-09-30 08:07 → 09:05 (unicast restored; 21 files, snaplen 256 → 512)

**Verified fixed:**
- Vivint panel mDNS: **0** (IPv4 and IPv6); no traffic to `.1.112`.
- No IP fragments, and no packets over 1500 bytes (GRO off works).
- STP: 4,748 BPDUs, root `0x1000`, 0 TC.
- Office TCP repeats: **0.02%**.
- DNS no-response is down to ~3%: `.40.185` 2.3%, `.40.186` 4.4% (was 31%).
- OpenWrt ARP clean.
- DHCP hostnames are now readable. `00:0f:ff:0c:41:ca` = **SA1** and CA1 = `00:0f:ff:51:92:2f`, which resolves the earlier SA1/CA1 MAC mix-up.

**What fills the capture** (1.25 GB stored in ~1 h, ≈1.2 GB/h):

| Share | Traffic | Action |
|---|---|---|
| **~44%** | Work laptop `.1.117` Microsoft Teams call media (UDP 3478–3481 → `52.112.0.0/14`) | Excluded in `CAPTURE_FILTER` (repo, 2026-09-30) |
| ~18% | iPhone `.10.123` Reddit/Instagram video over QUIC (UDP 443, Fastly/fbcdn) | Normal use; keep |
| ~7% | **CA1 `192.168.150.200` running Ookla speed tests** (TCP 8080 to Comcast/CenturyLink/Charter). Caused the 23 Mbit/s burst at 08:10:43 (a 50 MB file in 17 s) and another at ~08:46 | Find out what schedules it (Control4/OvrC on the testbench); it stops when the bench is off |
| ~3% | Google/Android update downloads (`.20.156`, gvt1.com) | Normal |
| ~4% | Monitoring polls from nexus: SNMP to SW920 and the Proxmox API (8006) on pve/pve2/pve3 | Normal |

Snaplen what-if on the same packets: 384 = 82% of 512, 256 = 62%, 128 = 41%. **Kept 512**; the Teams exclusion is the big saving (expected ≈2× longer retention).

**New findings:**

| Finding | Evidence | Next step |
|---|---|---|
| iPhone `.10.123` (private MAC `66:af:7a:cc:eb:e4`) cross-VLAN sessions failed after the handshake, 08:07–09:05 only | TCP 8009 (Google Cast) to Google devices `.20.186`/`.121`/`.116`/`.236`/`.142`, and to the ecobee "Hallway" `.30.167` (`44:61:32`, likely HomeKit). The router forwarded the phone's packets onto VLAN 20/30, but the devices kept resending SYN-ACKs (191 vs 49 SYN) and ACKed almost nothing. **Not network-wide:** 09:06–09:53, nexus `.40.185` → the same Cast devices on 8009 was healthy (2–3% repeats), and the second iPhone `.10.178` (`5a:92:e0:02:c7:ea`) → Apple device `.30.127` was healthy. No AirPlay (7000/7100), Sonos (1400/1443) or Spotify Connect (4070) sessions from phones were seen, so those are untested | Ask whether casting/Home app on that phone misbehaves; run a timed test (cast + ecobee in the Home app) and review that capture |
| mainsail `.30.90` loses Wi-Fi frames | Correction: the frequent connections are **nexus → Pi** (Prometheus blackbox probes of `http://192.168.30.90` and `:7125`, 15 s scrape), not the Pi calling out. About 25% of nexus's connection attempts get no SYN-ACK (553 SYN vs 405 SYN-ACK; 111 vs 83 later), and 67% of nexus → Pi data on the long-lived Moonraker (`python`, pid 479) session to nexus `:443` is resent. Both directions cross the router intact, so the loss is on the Wi-Fi hop. Power save is already **off**; signal is -60 dBm | Check the AP client view for mainsail (which AP, retries/rate); optionally lengthen the mainsail probe interval (the load is tiny, the loss is the issue); a USB-Ethernet adapter would remove Wi-Fi entirely |
| Work laptop uploads repeat | `.1.117` → `160.79.104.10:443` 34% repeated segments, with the server's ACKs arriving at the router. The laptop's own counter since boot is 0.9% retransmitted overall | Realtek USB power-saving features (EEE/Green/Idle); which port or dock? |
| Work laptop reaches VLAN 40 and the NAS **through Tailscale** | This laptop routes `192.168.40.0/24` and `10.25.25.0/24` via the `Tailscale` adapter (subnet routes, most likely advertised by nexus). Copying captures at 09:06 went laptop → router → nexus inside WireGuard (UDP 41065, 44% of that window), then nexus → 520 → **WAN2** (the 520's WAN2 sits on the `10.25.25.0/24` storage network) → NAS `10.25.25.248` over SMB (11%). The capture recorded it at up to 145 Mbit/s stored | At home, turn off *Use Tailscale subnets* on the laptop (`tailscale set --accept-routes=false`) and use the NAS at `192.168.40.248`. Capture filter now also excludes `10.25.25.248` |
| SDDP: Vivint panel, SW920 and AP `.1.231` missing from Composer's Available Devices | APs `.1.236`/`.1.237`, Core5, both Sonos and the 520 still answer the Director (unicast SDDP to `.10.200`). IGMP snooping ruled out (2026-09-30): the 920 has **no** snooping entry for `239.255.255.250` (`01:00:5E:7F:FF:FA`) on any VLAN, so it is unregistered and flooded normally; the only VLAN 10 groups are on 1/0/7, 1/0/11 and 1/0/13. The Vivint ACL is also ruled out. None of the three missing devices sent SDDP in the 09:05–09:51 capture, although AP `.1.231` (`14:3f:c3:e8:b9:93`) is otherwise healthy (SNMP, OvrC, ARP) and its neighbours `.1.236`/`.1.237` each sent 24 SDDP replies. **Not the Vivint ACL** (list removed, the panel still did not appear). The panel works in Control4 with its reserved IP entered manually | Inspect the 920 IGMP snooping table for `239.255.255.250`; compare AP firmware in OvrC (`.231` vs `.236`/`.237`); check the SDDP setting on the 920 and on AP `.1.231`; reboot `.231` when mainsail is idle |
| Android `.20.156` Pokémon GO asset download | 352 MB stored at 09:27 (`nianticstatic.com`) | Normal user traffic |
| Router still ARPs dead IPs above the sweep rate | `.1.243` 1,763, `.1.112` 1,701, `.1.247`, `.1.5`, `.1.137`, `.1.7`, `.1.3`, `.20.106` (sweep median 777) | Remove stale OvrC devices / 520 DHCP reservations for them |
| Control4 Director resolves `stats.grafana.org` ~6×/min | 1,048 lookups in 2.7 h (most NXDOMAIN/blocked), plus `api.local` from the `.local` search domain | Low priority |

### OvrC / 520 Inventory Review — 2026-09-30

The 520's stale DHCP leases were cleared by the user; OvrC needs manual clean-up. The OvrC export (main network) has 71 *Healthy* and 105 *Critical* entries.

**Delete from OvrC** (disconnected for months to a year; they keep old IPs "known", and some match addresses the router still ARPs for):
- ~20 old Proxmox VM MACs (`BC:24:11:…`) on VLAN 1 (`.1.9`, `.100`, `.112`, `.118`, `.128`, `.136`, `.150` ×4, `.176`, `.185`, `.187`, `.198`, `.199`, `.240`), plus `.40.244` and `.40.245`
- **Vivint outdoor camera `ODC350-390827` at `192.168.1.112`** (`84:EB:3E:39:08:27`, now on the panel's own AP), and five old Alpha Networks (Vivint) entries at `.1.109`/`.110`/`.113`/`.114`/`.115`
- Old MoIP units TX/RX/TR at `.1.4`, `.1.85`, `.1.174` and `.1.181`; eero ×3; Nintendo ×6; old touchscreens T3 `.1.96`, T4 `.1.98` and T5 ×2 at `.1.55`/`.1.65`; Space Monkey `.1.5`; `guard2` `.1.91`; stale "Home Assistant Gateway (Chowmain)" ×2; old Google TVs (`.1.28`, `.1.37`, `.1.137`); old Apple/Intel/Raspberry Pi/phone entries; `192.168.80.125` (the old 192.168.80.x network)

**Keep or decide:**
- Binary MoIP Controller `.1.137` (physically disconnected)
- Recent real devices that are just off: Guest Bedroom speaker `.20.106`, Emmy's speakers, Office display
- **Josh.ai: three OvrC entries (`.1.151`, `.1.190` 20 days ago; `192.168.200.151` 2 days ago), and none matches Composer's `192.168.1.84`**. Confirm whether Josh.ai is still in use and where

**Just "disconnected" after the lease clean-up** (static-IP hosts; they reappear on the next routed traffic, so don't delete): NAS `.40.248`, AdGuard2 `.40.186`, pve3 `.1.245`, `.1.244`

**Rename:**
- OvrC `192.168.1.225` "NPID93247" → OpenWrt wl1-sta0
- OvrC `192.168.30.90` "adguard-home" → mainsail
- 520 `192.168.1.226` "new-host1" → OpenWrt (wan/br-lan)
- The 920 port labels noted above

**Worth understanding:**
- **Explained (520 static routes, 2026-09-30):** the 520's **WAN2 is on the storage network `10.25.25.0/24`** (the Asus RT-N66U DD-WRT "Aurora" is `10.25.25.1`), so the 520 routes to the NAS's storage IP directly and OvrC sees those hosts. Static routes:
  - `192.168.2.0/24` → `192.168.1.225`: OpenWrt, the office subnet in P3 (L3/relayd) mode
  - `100.64.0.0/10` → nexus: Tailscale return path; nexus does not SNAT, so tailnet IPs stay unique
  - `10.8.0.0/24` → nexus: wg-easy WireGuard return path
  - `10.20.20.0/24` → `10.25.25.1` via WAN2: the DD-WRT upstream transit
  - Still to check: WAN2's mode on the 520 must be **failover/policy only, not load-balancing**; otherwise ordinary internet flows could leave via the Aurora/PIA path
- Testbench SA-1 `.200.100` keeps trying MQTT to `192.168.80.150:8883`, an address on the old 192.168.80.x network, which is a stale config on the testbench. CA1 `.150.200` tries the home Director `.10.200:8883` and is blocked by VLAN isolation (good)

### Decision — NAS shares are mounted inside the VMs, not as Proxmox NFS storage (2026-09-30)

- **Proxmox NFS storage serves Proxmox content** (disk images, ISO, templates, backups). VMs can't use a host mount; host-mount + bind is an LXC-only pattern. The Docker stacks run in VMs (luna, media-server, discovery-server), so they need their own mount anyway.
- **The NAS is a VM on pve3.** Hypervisor-level mounts would create a boot-order loop on pve3 and make pve/pve2 depend on one guest on another host.
- **Blast radius.** A dead NFS storage hangs `pvestatd`, the GUI status and backup/migration jobs on every host. The 2026-09-30 pve3 NIC hang only froze luna's processes, because the mount lived in the VM.
- **Ownership.** In-VM mounts give `1000:1000` files that match the containers; no root-squash/UID mapping through the host.
- **Mount policy:**
  - `/mnt/media` stays `hard` (writers pause and resume; soft can half-write, and makes Plex treat files as missing), plus `_netdev,nofail,x-systemd.mount-timeout=30`
  - Docker drop-in `Wants=`/`After=mnt-media.mount`
  - only the capture archive (`/mnt/captures`) is `soft`
- **Not used:** virtiofs pass-through (Proxmox 8.4+). It stacks on NFS, blocks live migration and keeps the host exposed to NFS hangs.

### Pending Checklist
- [x] **Proxmox email notifications (SMTP2GO) broken on pve2 and pve3** (fixed 2026-09-30: copied `/etc/pve/priv/notifications.cfg` from pve; test sent from pve2 and pve3). They work on pve. The hosts are not clustered, so each keeps its own `/etc/pve/notifications.cfg` (the SMTP password is in `/etc/pve/priv/notifications.cfg`). **Cause found 2026-09-30:** `notifications.cfg` is identical on all three hosts, but pve2/pve3 log `Could not instantiate endpoint 'SMTP2GO': private config does not exist`. The public file was copied, the private file with the password was not. Fix: re-enter the password on pve2/pve3 (Datacenter → Notifications → SMTP2GO → Edit), then Test
- [ ] **PBS `vm/100` collision:** nexus (pve), discovery-server (pve2) and nexus-server2 (pve3) are all VMID 100 and back up to one datastore with no namespace, so they share group `vm/100` (mixed snapshots, or owner-check failures). **Higher priority:** backup jobs prune with `keep-last=7, keep-daily=7, keep-weekly=4, keep-monthly=12`, so a prune from one host counts, and can delete, the other two VMs' snapshots in that shared group. Fix: one PBS namespace per host (`namespace` line in each host's `storage.cfg`), then verify each host's backups and restores
- [ ] **Pakedge VLAN 1 leak to test ports:** OvrC on CA1 (VLAN 150, Pakedge `gi8`) discovered VLAN 1 hosts (APs, pve, vxlan-server, PBS), so the access ports probably keep their factory **untagged VLAN 1** membership (the PVID was changed, membership was not). Check VLAN 1 membership in the Pakedge UI; only `gi1` should be a member
- [ ] OvrC: turn off CA1 Test **LAN Latency** (still hourly); after the power test, set main **Network Scans** to 24 Hours (or file a Snap One ticket if the router ARP sweep persists with scanning off)
- [x] Deploy `TAGGED_VLANS="10 30"` to both ends and prune 20/40/100/150/200 (2026-09-30: OpenWrt `vxlan150` = 10,30; vxlan-server `ens18` = 1,10,30, `vxlan150` = 10,30, `br0` self = 1)
- [ ] Re-run `failover.sh --test --vlan` with the fixed tester (remote V10 failed before because vxlan-server `br0` self had only vid 1) and confirm `V10:OK` on both ends
- [x] Persist `vmbr1` hub mode in pve `/etc/network/interfaces`: `bridge-ageing 0`, `post-up bridge link set dev lan1 learning off` and `post-up ethtool -K lan1 gro off`. Done and verified 2026-09-30: `ifquery -c vmbr1` passes; live ageing_time 0, learning off, GRO off; luna saw 23,380 unicast frames in 10 s. **Re-check after any Proxmox GUI network apply**, since one reset these settings on 2026-09-29 at ~22:24 (optional: disable IPv6 on `vmbr1`)
- [x] luna: persist `ethtool -K ens19 gro off` (udev rule `/etc/udev/rules.d/70-ens19-no-gro.rules`, installed 2026-09-30)
- [x] Stack 48 capture script deployed 2026-09-30: open-file-safe mover, `SNAPLEN=512`, NAS copies as `abc` (1000:1000, mode 664); existing NAS files chowned
- [ ] Capture retention vs. volume: after unicast was restored and snaplen went to 512, the first 50 MB chunks rotated every 1–3 min (morning of 2026-09-30). At that rate `MAX_ARCHIVE_FILES=150` (7.5 GB) keeps only about 4–7 h, not the 24 h `RETENTION_MINUTES`. Measure a full day, then either raise the cap (NAS space permitting), exclude known bulk flows in `CAPTURE_FILTER`, or lower `SNAPLEN` to 384
- [ ] Confirm/persist OpenWrt `br-lan` STP priority 61440 (`uci set network.@device[N].priority='61440'`)
- [x] Homebridge and Home Assistant bound to `ens18` — **verified 2026-09-30**: 120 s luna capture, 113 mDNS packets from `.40.249`, zero `172.x` addresses (set 2026-09-30: Homebridge *Network Interfaces* = `ens18`, advertiser Bonjour HAP; HA *Network adapter* = `ens18` only, Autoconfigure off). Remaining: restart both, then verify with a luna tcpdump that no `172.x` A records remain, child bridges (`0E_*`) included. Leave the Homebridge UI *Host IP Address* at its default; it sets only the web-UI listen address, not mDNS
- [ ] Vivint panel (`192.168.10.108`): the user confirmed (2026-09-30) it needs only cloud arm/disarm (phone and panel), the doorbell camera and the outdoor camera — no local Nest/Google, Spotify or Hue. **Applied 2026-09-30:** `VIVINT_NO_MDNS6` (IPv6) at sequence 1 and `VIVINT_NO_MDNS` (IPv4) at sequence 2, each `deny udp any any eq 5353` / `permit every`, on 1/0/17 inbound, ahead of the built-in `EXC_initial_list`. The panel's mDNS on the SPAN fell from 290 to 1 packet per 30 s. **Runbook: [`vivint-panel-mdns-acl.md`](../runbooks/vivint-panel-mdns-acl.md)** (how to read, test, roll back). Remaining: verify arm/disarm plus doorbell live view (panel and app) and the ACL hit counts, then `write memory`. Undo: `no ip access-group VIVINT_NO_MDNS in` / `no ipv6 traffic-filter VIVINT_NO_MDNS6 in` on 1/0/17
- [x] Vivint cameras off the LAN (2026-09-30): the user moved the Vivint/LG PoE Wi-Fi camera bridge onto the **panel's own AP**, so no Vivint cameras remain on the home LAN. This supersedes the `.1.112` reservation and 1/0/18 cable work. Any router ARPs still seen for `.1.112` are the OvrC sweep (it ARPs every VLAN 1 address about every 10 s), not the panel
- [ ] After `write memory` on the 920: refresh the repo backup `infrastructure/network/configs/araknis-920-running.cfg` (`backup` tool). It still predates STP root, BPDU Guard, IGMP snooping, trunk pruning and the Vivint ACLs
- [ ] SW920 port labels: relabel 1/0/18 ("Vivint Smart Drive", now unused). Two ports say "Control4 CA-10": 1/0/11 (VLAN 10) and 1/0/15 (VLAN 1). Confirm which one holds the Director `.10.200` (`00:0f:ff:20:74:d0`) and what is on the other
- [ ] Control4 ↔ Vivint integration (`.10.200` → panel `.10.108` TCP 8765, both DHCP-reserved, same VLAN 10, so switched and never routed): verify that the Composer driver shows connected, that arm/disarm from Control4 works, and that sensor states update with the mDNS ACL on. Then `write memory` on the 920. The driver must use the reserved IP, not discovery
- [ ] Move the OvrC-MoIP controller's LAN port to access VLAN 10
- [ ] Prune remaining trunks: AP ports 1/0/3, 1/0/4, 1/0/6 → `1,10,20,30,150,200`; pve3 1/0/21 → `1,40`; after the tunnel trim, pve 1/0/2 → `1,10,30,40` and pve `vmbr0` → `10 30 40`; set pve2's switch port (find MAC `38:F7:CD:C1:67:E0` in the 920 MAC table) to access VLAN 1 — pve2 `vmbr0` is **not** VLAN-aware (Proxmox GUI, 2026-09-30), has no VLAN sub-interfaces, and VM 100 uses only the storage NIC
- [ ] DHCP domain `local` → `home.arpa` (check AdGuard rewrites first); set AP and SX-8P DNS to AdGuard; optionally block outbound 53/853 except from AdGuard
- [ ] Printers: replace default Set communities (HP blank → random, Brother `internal` → random)
- [ ] APs: confirm AP1 5 GHz DFS off; consider 2.4 GHz TX power 50–75%; review UPnP on the 520
- [ ] Move end devices off VLAN 1 (cameras, MoIP endpoints, Vivint, dev controllers) to proper VLANs
- [ ] Decide fix vs retire for the pve nginx `*.secure.theurer.dev` upstreams still pointing at `.1.249` / `.1.185` / `.1.186`
- [ ] Rework `power_cycle_pakedge_switch` to trigger the Control4 *All Test Equipment* button/macro (not the WattBox outlet directly — see Part 2.10 power notes); refresh `pakedge-sx8p-running.cfg` via `backup_pakedge_switch`; decide Telnet on/off (the `configure-vlans` action needs it)
- [ ] OpenWrt: confirm ARP-strict is live (`sysctl net.ipv4.conf.all.arp_ignore` = 1, `arp_announce` = 2) and that `sysupgrade -l` now lists `/etc/sysctl.d/10-arp-strict.conf` and `/etc/crontabs/root` (added to the repo `sysupgrade.conf`)
- [ ] Deploy-script hardening: no world-readable secrets (`chmod -R 755`), health checks must fail on errors
- [ ] Long term: run Ethernet to the office and retire the wireless bridge + VXLAN failover

---

## ⏸️ Part 8: Compute Platform Review — Future Phase (recorded 2026-09-30)

**Not started. Nothing to do now** unless a Part 7 fix requires it.

**Preconditions:**
- the network is stable (Part 7 checklist closed);
- all important settings and state are captured and backed up in this repo.

**Goal:** re-evaluate the pve / pve2 / pve3 layout, VMs, LXCs and Docker stacks for performance, robustness and room to grow, especially future AI services on the **4 GB VRAM NVIDIA GPU in `pve`**.

**Known pain points:**
- The **Plex** Docker container has GPU-related limitations.
- **RAM ballooning** limits (a VM with a PCIe-passthrough GPU pins all its RAM, so it cannot balloon).

**Questions to answer then:**
- GPU sharing model: a VM with passthrough (one owner, pinned RAM) vs LXC with the NVIDIA device shared across containers (Plex NVENC plus AI services).
- VRAM budget: 4 GB fits Plex transcodes plus small quantized models (embeddings, speech-to-text, roughly ≤3–4B LLMs), not large models.
- Which workloads belong in LXC vs VM vs Docker-in-VM, and on which host.
- Host resilience lessons from Part 7:
  - pve3's e1000e NIC hang;
  - the NAS and PBS both live on pve3 (single point of failure);
  - NAS mounts stay in-VM (see the 2026-09-30 decision in Part 7).
- Storage placement, and memory and CPU headroom per host.
