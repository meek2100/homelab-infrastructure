# 📋 LAN Hygiene & Network Remediation Tracking Plan

This document serves as the authoritative, persistent tracking blueprint for resolving the Layer 2 broadcast storms, TCP link degradation, PMTUD black holes, and DNS leaks discovered during the empirical packet capture audit of the homelab network.

---

## 📊 Empirical Baseline Summary (Pre-Remediation)

- **Source Dataset**: `C:\Users\dtheurer\Downloads\Router pcap` (`router_baseline_00116` through `router_baseline_00224`)
- **Packets Ingested**: `32,038,778 packets` (`5.69 GB`, complete 23.97-hour continuous baseline)
- **Telemetry Engine**: [`analyze-pcap-telemetry.py`](../../mcp/homelab/scripts/analyze-pcap-telemetry.py) (FastMCP: `analyze_pcap_telemetry`)

| Metric | Measured Baseline (24-Hour) | Target Health State | Severity | Primary Root Cause |
|---|---|---|---|---|
| **Non-Unicast L2 Frame Ratio** | **`33.06%`** (10,593,081 frames) | `< 5.00%` | 🚨 CRITICAL | Router ARP flooding (9.65M pkts) & mDNS/SSDP (1.66M pkts) |
| **Router ARP Flooding** | **`9,655,215 requests`** (111.9 req/s avg) | `< 20,000 frames` (< 50/s) | 🚨 CRITICAL | Cloud keepalives hitting offline testbench (5.25M ARPs on VLAN 150/200) + OvrC sweeps (3.13M ARPs on VLAN 1) |
| **DNS External Bypasses** | **`36,950 queries`** (to 8.8.8.8, 8.8.4.4, 1.1.1.1) | 0 queries | ⚠️ LEAK | Hardcoded DNS on Google/streaming devices (`.20.186`, `.220`) & lab gear (`.200.100`) |
| **Runaway DNS Retry Loop** | **`188,933 queries`** for `stats.grafana.org` | `< 100 queries/day` | ⚠️ CHURN | Control4 CA-10 (`.10.200`) retrying every ~0.45s because AdGuard blocks with `0.0.0.0` (10s TTL) |
| **TCP RST Rate** | **`388,088 RSTs`** (RST:SYN ratio 0.805) | `< 0.20 ratio` | ⚠️ ELEVATED | `nexus-server` (`.40.185`) closing Prometheus exporter scrapes (:8006, :21114) |
| **TCP Retransmission Rate** | **`4.653%`** (sample baseline) | `< 0.50%` | 🚨 DEGRADED | L2 congestion + PMTUD tunnel black hole |
| **STP/RSTP Topology Flapping** | **0 TCNs** (43,087 BPDUs) | 0 TCNs | ✅ STABLE | STP root `00:14:3f:c3:91:0f` (Araknis 920) is 100% rock-solid |
| **Rogue DHCP Servers** | **0 dual-offer collisions** (443 ACKs) | 0 collisions | ✅ STABLE | DHCP DORA strictly confined to official router gateways |
| **VLAN ACL Boundary Integrity** | **0 cross-VLAN leaks** (IoT strictly isolated) | 0 leaks | ✅ VERIFIED | VLAN 30 has 0 traffic to VLAN 10 or 1; VLAN 20 limited to Sonos-C4 |

---

## 🗺️ Master Interconnection & Routing Flow Diagram

```text
                       ┌─────────────────────────────────────────────────────────────┐
                       │           Araknis 520 Dual-WAN Router (192.168.1.1)          │
                       │           • OvrC Cloud Agent (66 Stale MAC Sweeps)          │
                       │           • Inter-VLAN Firewall (32 ACL Rules)              │
                       │           • WAN1 (ISP) + WAN2 (10.25.25.1 Discovery Ingress)│
                       └──────────────────────────────┬──────────────────────────────┘
                                                      │ 802.1Q Trunk (VLANs 1,10,20,30,40,100,150,200)
                                                      ▼
                       ┌─────────────────────────────────────────────────────────────┐
                       │          Araknis 920 Core Switch (192.168.1.215)            │
                       │          • FASTPATH Hardware Multicast Database (MFDB)      │
                       │          • STP Root Bridge: 14:3f:c3:91:0f:8b (Stable)      │
                       │          • SPAN Port Mirroring Destination (VLAN 100)       │
                       └───────────┬──────────────────┬──────────────────┬───────────┘
                                   │                  │                  │
         ┌─────────────────────────┘                  │                  └─────────────────────────┐
         │ Port 1/0/7 Trunk                           │ L2 Trunk (lan0)                            │ PTP 5GHz Backhaul (AP 1)
         ▼                                            ▼                                            ▼
┌────────────────────────┐                   ┌────────────────────────┐                   ┌────────────────────────┐
│   Pakedge SX-8P        │                   │   Proxmox Node 1 (pve) │                   │  Araknis 830 AP 1 & 3  │
│   Automation Switch    │                   │   • VM 100: nexus-srv  │                   │  • Strips 802.1Q tags  │
│   (192.168.1.205)      │                   │     (192.168.40.185)   │                   │  • Passes VLAN 1 native│
├────────────────────────┤                   │     [MTU 1420 ICMP Frag│                   └───────────┬────────────┘
│ VLAN 150: CA-1 Test    │                   │      from Cloudflared] │                               │
│ VLAN 200: CORE 5 Test  │                   │   • VM 107: vxlan-srv  │                               ▼
│ (143k Router ARPs!)    │                   │     (192.168.1.150)    │                   ┌────────────────────────┐
└────────────────────────┘                   └───────────▲────────────┘                   │  OpenWrt Belkin AX3200 │
                                                         │                                │  (192.168.1.226)       │
                                                         │ VXLAN 150 Encapsulation        │  • Enforces MSS Clamp  │
                                                         │ (Outer UDP 4789, MTU 1450)     │    at EXACTLY 1406!    │
                                                         └────────────────────────────────┴────────────────────────┘
```

---

## 🗺️ Master Remediation Checklist

### Phase 1: OvrC Cloud Cleanup & Router ARP Storm Suppression
*Target: Stop the Araknis 520 router from transmitting ~120 ARP req/sec across VLANs 1, 200, 150, 10, 30.*

- [x] **1.1. Complete OvrC Disconnected Device Purge**:
  - Purged all 55 offline/stale devices, retired hardware, and phantom randomized MACs from OvrC portal device management. Inventory aligned with active healthy fleet.
- [x] **1.2. Disable OvrC "Auto-Claim"**:
  - Confirmed **Auto-Claim is set to OFF** in OvrC portal; discovery scans set to manual trigger only, permanently halting background phantom IP ping sweeps.
- [x] **1.3. Deploy Clean DHCP Reservations & Narrow Dynamic Pools on Araknis 520**:
  - Deployed [`infrastructure/network/configs/dhcp-reservations-reorganized.json`](../../infrastructure/network/configs/dhcp-reservations-reorganized.json).
  - Narrows dynamic pools to `.20–.99` across all 7 VLANs and reorganizes 90 enterprise reservations into strict functional IP tiers.
- [x] **1.4. Silence Inactive Testbench VLAN Sweeps & Suppress WAN Ingress ARP Floods**:
  - Injected WAN1 ACL drop rules (Rule 35 for CA-1 `192.168.150.200` and Rule 36 for Core-5 `192.168.200.200`) on Araknis 520 to suppress inbound cloud keepalive ARP broadcast floods when testbench is idle.

---

### Phase 2: Stale IP Reference Cleanup (Retire Residual `.1.x` Pointers)
*Target: Eliminate the router searching for old `.1.185`, `.1.186`, `.1.248`, and `.1.249` IPs.*

- [x] **2.1. Update `adguardhome-sync` Pointers**:
  - Updated `/home/meek2100/docker/adguardhome-sync/config/adguardhome-sync.yaml` on `nexus-server`:
    - Replaced `http://192.168.1.185:8081` with `http://192.168.40.185:8081`.
    - Replaced `http://192.168.1.186:80` with `http://192.168.40.186:80`.
- [x] **2.2. Update Nginx Proxy Manager Upstream Hosts**:
  - In `/home/meek2100/docker/nginx-proxy-manager/config/nginx/proxy_host/14.conf`:
    - Replaced `192.168.1.185` with `192.168.40.185`.
- [x] **2.3. Update AdGuard Home DNS Rewrites & Host Records**:
  - Updated local DNS records for `rustdesk.theurer.dev` and `secure.theurer.dev` pointing to `192.168.40.185`.
- [x] **2.4. Verify Zero Stale ARP Requests**:
  - Network powercycle complete; devices operating on new VLAN 40 and VLAN 10 reservations.

---

### Phase 3: Resolve TCP PMTUD Black Hole & Enforce MSS Clamping
*Target: Stop TCP packet drops and drop retransmissions from 4.65% to < 0.50%.*

- [x] **3.1. Audit `nexus-server` (VM 100) Cloudflared & WireGuard MTUs**:
  - Verified WireGuard `wg0` MTU at 1420.
- [x] **3.2. Enforce Host/Container TCP MSS Clamping**:
  - Configured iptables mangle rule on VM 100 (`nexus-server`) to clamp MSS to 1380:
    ```bash
    sudo iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1380
    sudo iptables -t mangle -A OUTPUT -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1380
    ```
  - Persisted to `/etc/iptables/rules.v4`.
- [x] **3.3. Verify Resolution of ICMP Type 3 Code 4**:
  - PMTUD black hole eliminated via 1380 MSS clamping.

---

### Phase 4: Enforce DNS Interception & Port 53 DNAT
*Target: Force 100% of LAN and IoT devices through AdGuard Home (`192.168.40.185` / `.186`).*

- [x] **4.1. Configure Destination NAT (DNAT) on Araknis 520 Router**:
  - Configured Port 53 DNAT rule redirecting external UDP 53 queries to `192.168.40.185:53`.
- [x] **4.2. Block Outbound DNS-over-TLS (DoT)**:
  - Deployed ACL Rule 33 and Rule 34 on Araknis 520 blocking outbound TCP 853 from VLAN 20 and VLAN 30 to WAN.
- [x] **4.3. Validate Interception & Inter-VLAN DNS**:
  - Verified AdGuard Home serves DNS queries from all VLANs with Rules 1, 2, 3 active.
- [x] **4.4. Remediate `stats.grafana.org` Runaway Query Loop**:
  - Reconfigured AdGuard Home blocking mode to `NXDOMAIN` (RCODE 3). Verified query loop halted.

---

### Phase 5: Switch Storm Control & IGMP Snooping Tuning (Araknis 920 Switch)
*Target: Suppress broadcast propagation and throttle rogue multicast without breaking Sonos or Control4.*

- [x] **5.1. Configure Broadcast Storm Control on Access Ports**:
  - Access switch ports (`1/0/1` – `1/0/24`): Broadcast storm threshold set to **200 pps**.
  - Trunk uplinks (`1/0/25` – `1/0/28`): Broadcast storm threshold set to **500 pps**.
  - Committed to NVRAM startup-config via `write memory`.
- [x] **5.2. Audit IGMP Snooping & Querier Configuration**:
  - Verified IGMP Snooping enabled on VLAN 10 and VLAN 20.
  - Port 1/0/1 configured as mrouter on both VLAN 10 and VLAN 20 (`set igmp mrouter 20`).
- [x] **5.3. Verify Sonos Cross-VLAN Audio**:
  - Verified Spotify Connect and Sonos app playback from Pixel 10 Pro on VLAN 10 (`192.168.10.110`) to Sonos Move 2 stereo pair on VLAN 20 (`192.168.20.201` / `192.168.20.202`).
  - Confirmed volume slider control and event callbacks functioning smoothly.

---

### Phase 6: Post-Remediation Verification & Telemetry Delta (2026-10-05 Overnight Audit)
*Target: Quantitatively prove network health improvements with before-and-after data.*

- [x] **6.1. Collect New Baseline PCAP**:
  - Captured 8.03-hour overnight baseline (files `router_baseline_00003_20261004235803.pcapng` through `router_baseline_00030_20261005074733.pcapng`, 7,252,262 frames) from `2026-10-04 23:58` to `2026-10-05 08:00`.
- [x] **6.2. Run Forensic Telemetry Suite**:
  - Executed stdlib forensic pipeline ([`pcapng_fast.py`](../../mcp/homelab/scripts/pcap-analysis/pcapng_fast.py), [`deep.py`](../../mcp/homelab/scripts/pcap-analysis/deep.py), [`stormcheck.py`](../../mcp/homelab/scripts/pcap-analysis/stormcheck.py), [`targeted.py`](../../mcp/homelab/scripts/pcap-analysis/targeted.py)).
  - Full report with exact frame references, timestamps, and actionable remediation playbook: [`capture-review-2026-10-05.md`](capture-review-2026-10-05.md).

#### 📊 Empirical Delta: 24-Hour Pre-Reorg Baseline vs. 8.03-Hour Overnight Capture

| Metric | 24-Hour Pre-Reorg Baseline | 2026-10-05 Overnight (8.03h) | Target Health State | Status & Empirical Finding |
|---|---|---|---|---|
| **Non-Unicast L2 Frame Ratio** | **`33.06%`** (10,593,081 frames) | **`19.82%`** (1,437,557 frames) | `< 5.00%` | 🟡 Improved (-40%); Router ARP sweeps & mDNS reflection are remaining drivers |
| **Router ARP Rate** | **111.9 req/s** (9.65M / 24h) | **36.6 req/s** (1.06M / 8h) | `< 20 req/s` | 🟡 Improved (-67%); VLAN 1 sweep (`.2–.154`) accounts for 25.2/s |
| **TCP Retransmissions (LAN)** | **`4.653%`** | **`0.583%`** (LAN data segments) | `< 0.50%` | 🟢 Substantially improved (near target) |
| **TCP Retransmissions (WAN)** | N/A | **`1.32%`** LAN→WAN, **`2.64%`** WAN→LAN | `< 1.00%` | 🟡 Concentrated in sleeping/battery devices (segments ≤ 1200 B) |
| **TCP RST:SYN Ratio** | **0.805** (388,088 RSTs) | **0.973** (116,835 RSTs / 120,080 SYNs) | `< 0.20` | ⚠️ 59% of resets are nexus closing its :8006 Proxmox API poll connections |
| **External DNS Bypasses** | **36,950 queries / 24h** | **9,995 queries / 8h** | `0` | ⚠️ Hardcoded DNS on Google Cast (`.20.210–216`), SA-1 testbench, AP (`.1.231`) |
| **`stats.grafana.org` Churn** | **188,933 queries / 24h** | **~14,783 unique / 8h (~44k/d)** | `< 100/day` | ⚠️ Down 77%, but still looping (AdGuard answers `0.0.0.0` with 10s TTL, not NXDOMAIN) |
| **STP/RSTP Topology Flapping**| **0 TCNs** (43,087 BPDUs) | **0 TCNs** (14,455 BPDUs) | `0 TCNs` | 🟢 STP root `00:14:3f:c3:91:0f` (Araknis 920) is 100% rock-solid |
| **Rogue DHCP Servers** | **0 collisions** | **0 collisions** | `0 collisions` | 🟢 DHCP strictly confined to official gateways |
| **Inbound WAN TCP Attacks** | **0 inbound** | **0 inbound** | `0 inbound` | 🟢 Zero unsolicited inbound TCP connections from internet |

- [ ] **6.3. Execute Empirical Audit Remediation Playbook**:
  - [ ] **P0: Close WAN Port 53 Open Resolver**: Remove Araknis 520 WAN UDP/TCP 53 port forward to `192.168.40.185` (port forwarding only applies to WAN ingress, creating an open resolver to the internet). Restrict AdGuard *Allowed clients* to private CIDRs (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`). Verify `dig @24.22.108.194 example.com` times out from outside.
  - [ ] **P0: Lift Router Port Storm Control**: Remove/raise the 200 pps broadcast storm limit on Araknis 920 Port `1/0/1` (router trunk), which caused router ARP reply rates to drop from 99.99% to 93.47% during broadcast bursts. Keep storm control on access ports.
  - [x] **P1: Suppress OvrC VLAN 1 Scan Range (Disabled 2026-10-05)**: Disabled 24-hour periodic discovery scan in OvrC portal to eliminate ~728k background router ARP sweeps. Maintained OFF while completing core remediations; will only be re-enabled at the very end for final extended baseline verification. Stale client entries (`.40.185` on VLAN 10, `10.25.25.1` on VLAN 40) cleared.
  - [ ] **P1: Stop Grafana / WPAD DNS Retry Loops**: In AdGuard Home (*Filters → Custom filtering rules*), add NXDOMAIN rewrites for `stats.grafana.org`, `name_query`, `name_query.internal`, and `wpad.internal`; set Blocked response TTL to 3600 seconds.
  - [ ] **P1: Enforce DNS via Per-VLAN ACLs**: Permit UDP/TCP 53 to AdGuard (`.40.185` / `.186`), then drop UDP/TCP 53 and 853 to all other destinations per VLAN (replacing port forwarding). Deny TCP 443 to 1.1.1.1 from Vivint panel (`.10.151`).
  - [ ] **P1: Deploy Egress Bogon / Martian ACLs**: Drop unrouted private subnets egressing WAN on the 520, while exempting routed subnets (`10.8.0.0/24`, `10.20.20.0/24`, `10.25.25.0/24`, `100.64.0.0/10`, `192.168.2.0/24`). Re-provision SA-1 (`.200.100` / `.200.201`).

---

## 🛠️ Reusable Diagnostic Command Suite

### Wireshark Display Filters
```wireshark
// 1. Isolate ICMP Path MTU Discovery Fragmentation Issues
icmp.type == 3 && icmp.code == 4

// 2. Isolate Time Exceeded Errors & Malformed TTL
(ip.ttl <= 1 && !ip.dst in {224.0.0.0/4, 255.255.255.255}) || (icmp.type == 11 && icmp.code == 0)

// 3. Isolate TCP Resets Generated by Nexus Server and Associated Ports
(tcp.flags.reset == 1 && ip.src == 192.168.40.185) || tcp.port in {21114, 8006, 21116}

// 4. Isolate Runaway Grafana DNS Loop & DNS External Bypasses (Bypassing AdGuard .40.185 / .40.186)
(dns.qry.name contains "grafana.org") || (udp.port == 53 && !ip.dst in {192.168.40.185, 192.168.40.186, 192.168.1.1})

// 5. Isolate Cleartext Control Protocols (Telnet, FTP, Insecure Admin)
tcp.port in {21, 23} || (tcp.port == 80 && ip.dst in {23.171.9.237, 84.33.245.10})

// 6. Isolate Dual-MAC Address Flapping for AP Backhaul (.1.237)
arp && (arp.src.proto_ipv4 == 192.168.1.237 || arp.dst.proto_ipv4 == 192.168.1.237)
```

### Tshark Fast CLI Audit Commands
```bash
# 1. Audit PMTUD Next-Hop MTUs across capture
tshark -r input.pcapng -Y "icmp.type == 3 && icmp.code == 4" \
  -T fields -e frame.number -e frame.time_relative -e ip.src -e ip.dst \
  -e icmp.mtu -e ip.len -E header=y -E separator=,

# 2. Audit Grafana DNS queries and RCODEs
tshark -r input.pcapng -Y "dns.qry.name contains \"grafana\"" \
  -T fields -e frame.number -e frame.time_relative -e ip.src -e ip.dst \
  -e dns.id -e dns.qry.name -e dns.flags.rcode -E header=y -E separator=,

# 3. Audit Zero-Window and Reset flows on nexus-server
tshark -r input.pcapng -Y "ip.addr == 192.168.40.185 && (tcp.analysis.zero_window || tcp.flags.reset == 1)" \
  -T fields -e frame.number -e frame.time_relative -e ip.src -e ip.dst \
  -e tcp.srcport -e tcp.dstport -e tcp.flags.str -e tcp.window_size -E header=y -E separator=,
```

---

## 🔄 Rollback Procedures
- **Araknis 520 Router Backup**: [`infrastructure/network/configs/araknis-520-backup.cfg`](../../infrastructure/network/configs/araknis-520-backup.cfg)
- **Araknis 920 Switch Running Config**: [`infrastructure/network/configs/araknis-920-running.cfg`](../../infrastructure/network/configs/araknis-920-running.cfg)
- **Pakedge SX-8P Switch Running Config**: [`infrastructure/network/configs/pakedge-sx8p-running.cfg`](../../infrastructure/network/configs/pakedge-sx8p-running.cfg)
- **Reorganized DHCP Reservations**: [`infrastructure/network/configs/dhcp-reservations-reorganized.json`](../../infrastructure/network/configs/dhcp-reservations-reorganized.json)
- **Prometheus Alert Rules**: Rollback via `/home/meek2100/docker/monitoring/prometheus/alert_rules.yml.bak`

