# 📋 LAN Hygiene & Network Remediation Tracking Plan

This document serves as the authoritative, persistent tracking blueprint for resolving the Layer 2 broadcast storms, TCP link degradation, PMTUD black holes, and DNS leaks discovered during the empirical packet capture audit of the homelab network.

---

## 📊 Empirical Baseline Summary (Pre-Remediation)

- **Source Dataset**: `C:\Users\dtheurer\Downloads\Router pcap` (`router_baseline_00140` through `00144`)
- **Packets Ingested**: `1,444,810 packets` (`193.16 MB`, ~1 hour baseline)
- **Telemetry Engine**: [`scripts/analyze_lan_pcap.py`](../../scripts/analyze_lan_pcap.py)

| Metric | Measured Baseline | Target Health State | Severity | Primary Root Cause |
|---|---|---|---|---|
| **Non-Unicast L2 Frame Ratio** | **`34.36%`** | `< 5.00%` | 🚨 CRITICAL | Router ARP storm & unpruned mDNS/SSDP |
| **Router ARP Flooding** | **`480,665 frames`** (peak 734/s) | `< 20,000 frames` (< 50/s) | 🚨 CRITICAL | OvrC scanning 66 dead MACs; dead IP reservations |
| **TCP Retransmission Rate** | **`4.653%`** (67,231 pkts) | `< 0.50%` | 🚨 DEGRADED | L2 congestion + PMTUD tunnel black hole |
| **ICMP MTU Exceeded (Type 3 Code 4)**| **8 events** (from `192.73.240.128`) | 0 events | ⚠️ ELEVATED | `nexus-server` (VM 100) 1500 MTU vs 1420 tunnel |
| **DNS External Bypasses** | **1,597 queries** (to 8.8.8.8, 1.1.1.1)| 0 queries | ⚠️ LEAK | Hardcoded IoT/smart device DNS bypassing AdGuard |
| **STP/RSTP Topology Flapping** | **0 TCNs** (1,881 BPDUs) | 0 TCNs | ✅ STABLE | STP root `14:3f:c3:91:0f:8b` is rock-solid |
| **Rogue DHCP Servers** | **0 dual-offer collisions** | 0 collisions | ✅ STABLE | DHCP DORA is clean across all VLANs |

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

- [ ] **1.1. Complete OvrC Disconnected Device Purge**:
  - Reference checklist: [`ovrc-cleanup-checklist.md`](file:///mnt/c/Users/dtheurer/Downloads/Router%20pcap/ovrc-cleanup-checklist.md).
  - Delete all 66 devices disconnected > 1 month (old Nintendo consoles, retired touchscreens, deprecated Raspberry Pis).
- [ ] **1.2. Disable OvrC "Auto-Claim"**:
  - In OvrC portal, toggle **Auto-Claim OFF** to permanently prevent phantom devices from being re-added to continuous ping sweeps.
- [ ] **1.3. Deploy Clean DHCP Reservations & Narrow Dynamic Pools on Araknis 520**:
  - Deploy [`infrastructure/network/configs/dhcp-reservations-reorganized.json`](../../infrastructure/network/configs/dhcp-reservations-reorganized.json) as specified in [`network-dhcp-ip-reorganization-plan.md`](network-dhcp-ip-reorganization-plan.md).
  - Eliminates stale `.1.137` ARP sweeps by moving Binary MoIP to `.1.155` and TV to `.20.232`, retains verified active hardware like T5 touchscreen at `192.168.10.201`, and narrows dynamic pools to `.20–.99`.
- [ ] **1.4. Silence Inactive Testbench VLAN Sweeps**:
  - On VLAN 150 (`CA-1 Test`) and VLAN 200 (`Core-5 Test`), disable automated polling while test equipment is powered down.

---

### Phase 2: Stale IP Reference Cleanup (Retire Residual `.1.x` Pointers)
*Target: Eliminate the router searching for old `.1.185`, `.1.186`, `.1.248`, and `.1.249` IPs.*

- [ ] **2.1. Update `adguardhome-sync` Pointers**:
  - Edit `/home/meek2100/docker/adguardhome-sync/config/adguardhome-sync.yaml` on `nexus-server` / `nexus-server2`:
    - Replace `http://192.168.1.185:8081` with `http://192.168.40.185:8081`.
    - Replace `http://192.168.1.186:80` with `http://192.168.40.186:80`.
- [ ] **2.2. Update Nginx Proxy Manager Upstream Hosts**:
  - In `/home/meek2100/docker/nginx-proxy-manager/config/nginx/proxy_host/14.conf`:
    - Replace `set $server "192.168.1.185";` with `"192.168.40.185";`.
- [ ] **2.3. Update AdGuard Home DNS Rewrites**:
  - Remove stale rewrite entries in `nexus-server` AdGuard config pointing `secure.theurer.dev` to `192.168.1.185` (now on `192.168.40.185` or direct router IP `192.168.1.1`).
- [ ] **2.4. Verify Zero Stale ARP Requests**:
  - Run a quick 1-minute capture to confirm 0 ARP requests for `192.168.1.185`, `.186`, `.248`, `.249`.

---

### Phase 3: Resolve TCP PMTUD Black Hole & Enforce MSS Clamping
*Target: Stop TCP packet drops and drop retransmissions from 4.65% to < 0.50%.*

- [ ] **3.1. Audit `nexus-server` (VM 100) Cloudflared & WireGuard MTUs**:
  - Check interface MTUs inside VM 100: `ip link show`.
  - WireGuard interface (`wg0`) should be set to MTU `1420`.
- [ ] **3.2. Enforce Host/Container TCP MSS Clamping**:
  - Configure iptables mangle rule on VM 100 (`nexus-server`) to clamp MSS to 1380 for all tunnel traffic:
    ```bash
    sudo iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1380
    sudo iptables -t mangle -A OUTPUT -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1380
    ```
  - Persist via `iptables-persistent` or docker daemon network configuration.
- [ ] **3.3. Verify Resolution of ICMP Type 3 Code 4**:
  - Monitor with `analyze_lan_pcap.py` to confirm zero new ICMP Fragmentation Needed packets from `192.73.240.128`.

---

### Phase 4: Enforce DNS Interception & Port 53 DNAT
*Target: Force 100% of LAN and IoT devices through AdGuard Home (`192.168.40.185` / `.186`).*

- [ ] **4.1. Configure Destination NAT (DNAT) on Araknis 520 Router**:
  - Rule: If Destination Port == `UDP/53` or `TCP/53` AND Destination IP != `192.168.40.185` and != `192.168.40.186`:
    - Action: Redirect / DNAT to `192.168.40.185:53`.
- [ ] **4.2. Block Outbound DNS-over-TLS (DoT)**:
  - On IoT (VLAN 30) and Guest/Media (VLAN 20), add an egress firewall rule blocking outbound port `TCP 853` to prevent devices from using encrypted DNS to evade AdGuard Home filters.
- [ ] **4.3. Validate Interception**:
  - Execute a test query from a client: `nslookup google.com 8.8.8.8` and verify it appears in AdGuard query logs on `nexus-server`.

---

### Phase 5: Switch Storm Control & IGMP Snooping Tuning (Araknis 920 Switch)
*Target: Suppress broadcast propagation and throttle rogue multicast without breaking Sonos or Control4.*

- [ ] **5.1. Configure Broadcast Storm Control on Access Ports**:
  - Access switch ports (`1/0/1` – `1/0/24`): Set broadcast storm threshold to **200 pps** (or 1%).
  - Trunk uplinks (`1/0/25` – `1/0/28`): Cap broadcast rate at **500 pps**.
- [ ] **5.2. Audit IGMP Snooping & Querier Configuration**:
  - Ensure IGMP Snooping is ENABLED on VLAN 10 (`Main - Trusted`) and VLAN 20 (`Guest - Media`).
  - Verify Araknis 920 FASTPATH switch is designated as the active **IGMP Querier** with an query interval of 125s.
- [ ] **5.3. Verify Sonos Cross-VLAN Audio**:
  - Test Spotify Connect and Sonos app playback from phone on VLAN 10 to Sonos speaker on VLAN 20.
  - Confirm volume sliders and event callbacks (TCP 3400/3500) function seamlessly.

---

### Phase 6: Post-Remediation Verification & Telemetry Delta
*Target: Quantitatively prove network health improvements with before-and-after data.*

- [ ] **6.1. Collect New 1-Hour Baseline PCAP**:
  - Capture new ring-buffer slices on the router trunk or SPAN mirror port (`ens19` on `luna-server`).
- [ ] **6.2. Run Telemetry Engine**:
  ```bash
  python3 scripts/analyze_lan_pcap.py /path/to/new_capture.pcapng --json /tmp/post_remediation.json --md /tmp/post_remediation.md
  ```
- [ ] **6.3. Confirm Target Exit Criteria**:
  - [ ] Non-unicast frame ratio drops from 34.36% to **< 5.0%**.
  - [ ] Router ARP rate drops from 734/s burst to **< 20/s**.
  - [ ] TCP retransmission rate drops from 4.65% to **< 0.50%**.
  - [ ] External DNS leak drops from 1,597 queries to **0**.
  - [ ] 0 ICMP MTU Fragmentation events.

---

## 🔄 Rollback Procedures
- **OvrC / Router Config**: Backup snapshot exists at [`infrastructure/network/configs/araknis-520-backup.cfg`](../../infrastructure/network/configs/araknis-520-backup.cfg).
- **Switch Config**: Backup snapshot exists at [`infrastructure/network/configs/araknis-920-running.cfg`](../../infrastructure/network/configs/araknis-920-running.cfg).
- **Prometheus Alert Rules**: Rollback via `/home/meek2100/docker/monitoring/prometheus/alert_rules.yml.bak`.
