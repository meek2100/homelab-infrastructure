# 🏷️ Homelab 9-VLAN Segmentation Matrix

This document provides the authoritative network segmentation specification for the homelab, defined on the **Araknis 520 Dual-WAN Router**, distributed via 802.1Q trunks on the **Araknis 920 Switch**, and broadcast via **Araknis 830 APs**.

---

## 📋 VLAN Allocation Table

| VLAN ID | Official Name | Subnet | Gateway (Araknis 520) | Security Zone | DNS Servers (DHCP Option 6) | Primary Purpose & Device Scope |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | `Management` | `192.168.1.0/24` | `192.168.1.1` | Trusted | `192.168.40.185`, `192.168.40.186` | Hypervisors (`pve` .250, `pve2` .240, `pve3` .245), switches (Araknis 920 `.215`, Netgear `.220`, Pakedge SX-8P `.205`), APs (`.231`, `.236`, `.237`), OpenWrt (`.226` / `.225`), PBS (`.244`), router GUI (`secure.theurer.dev`) |
| **10** | `Main - Trusted` | `192.168.10.0/24` | `192.168.10.1` | Trusted | `192.168.40.185`, `192.168.40.186` | Primary workstations, personal laptops, smartphones, trusted family devices |
| **20** | `Guest - Media` | `192.168.20.0/24` | `192.168.20.1` | Semi-Isolated | `192.168.40.185`, `192.168.40.186` | Guest Wi-Fi clients, smart TVs, Apple TV, media streamers (isolated from LAN) |
| **30** | `Isolated - IOT` | `192.168.30.0/24` | `192.168.30.1` | Untrusted | `192.168.40.185`, `192.168.40.186` | Smart plugs, smart bulbs, Wi-Fi sensors, Tuya/ESPHome/Shelly devices (no return LAN access) |
| **40** | `Servers - Admin` | `192.168.40.0/24` | `192.168.40.1` | Protected Server | `192.168.40.185`, `192.168.40.186` | Core identity & server infrastructure: Primary DNS/NPM (`.185`), Secondary DNS (`.186`), Home Automation (`.249`), NAS Admin (`.248`) |
| **100** | `Wireshark - Debug` | Dynamic / Sniff | - | Inspection | `192.168.40.185`, `192.168.40.186` | Dedicated network traffic inspection, SPAN mirror destination, and packet capture analysis |
| **150** | `CA-1 Test` | `192.168.150.0/24` | `192.168.150.1` | Isolated Lab | `192.168.40.185`, `192.168.40.186` | Control4 CA-1 Automation Controller lab network (OvrC location `CA1 Test`; tunneled via `vxlan150` on VM 107; trunked to Pakedge SX-8P on SW920 Port 1/0/7) |
| **175** | `Ryff Standalone Test`| `192.168.175.0/24` | `192.168.175.1` | Isolated Lab | `192.168.40.185`, `192.168.40.186` | Triad SA1 Streaming Amp / Ryff audio test network (OvrC location `Ryff Standalone Test`; SW920 Port 1/0/5 access VLAN 175) |
| **200** | `Core-5 Test` | `192.168.200.0/24` | `192.168.200.1` | Isolated Lab | `192.168.40.185`, `192.168.40.186` | Control4 CORE 5 Flagship Automation Controller testing and multi-room AVoIP (OvrC location `Core5 Test`; SW920 Port 1/0/8 access VLAN 200) |
| **WAN2** | `Storage & WAN2` | `10.25.25.0/24` | `10.25.25.1` | Dedicated Transit | Local / Unbound | Dedicated WAN2 internet egress for `discovery-server` (`.246`) and L2 line-rate storage to `nas-server` (`.248`) |

---

## ☁️ OvrC Cloud Location Mapping

| OvrC Location Name | OvrC Location ID | Target Subnet / VLAN | Scope & Purpose |
| :--- | :--- | :--- | :--- |
| **Theurer Home** | `67acffbe603da2cec1e44bc0` | VLAN 1, 10, 20, 30, 40 | Main Homelab & Residential Network Fleet (83 devices) |
| **CA1 Test** | `6abaa48bd63369a5ab17f7bb` | VLAN 150 (`192.168.150.0/24`) | Control4 CA-1 Controller Testbench (`00:0F:FF:51:92:2F`) |
| **Ryff Standalone Test** | `6ac3c311513ad591c2c579d9` | VLAN 175 (`192.168.175.0/24`) | Triad SA1 Streaming Amp Ryff Testbench (`00:0F:FF:0C:41:CA`) |
| **Core5 Test** | `6a3a51c86985286df96ff09d` | VLAN 200 (`192.168.200.0/24`) | Control4 Core-5 Flagship Controller Testbench (`00:0F:FF:0C:33:AE`) |
| *Nicola Home* | `67c75f3c260e087d0a02ba18` | External / Remote | **EXCLUDED** (External client/dealer location, not part of this homelab repo) |

---

## 🔒 Inter-VLAN Access Control & Security Policies

```text
┌────────────────────────────────────────────────────────────────────────┐
│  TIER 1: VLAN 40 (Admin & Servers: WireGuard, Tailscale, Proxmox VMs)  │
│  ► ALLOWED to initiate traffic to EVERY VLAN (1, 10, 20, 30, Storage)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│  TIER 2: VLAN 10 (Main Trusted: Your Workstations, Laptops, Phones)   │
│  ► ALLOWED to initiate to: VLAN 40 (Servers/NAS) and VLAN 30 (IoT)     │
│  ► ALLOWED to initiate to: VLAN 20 (Sonos/Media Control) & VLAN 1 (Mgmt)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│  TIER 3: VLAN 30 (Isolated IoT: Smart Plugs, Cameras, 3D Printers)    │
│  ► BLOCKED from initiating to VLAN 1, VLAN 10, and VLAN 40*            │
│  ► ALLOWED to Internet (WAN) for cloud sync                            │
│  ► EXEMPTION: DNS (UDP/TCP 53) to 192.168.40.185 & 192.168.40.186       │
│  ► EXEMPTION: Home Assistant (TCP 8123) to 192.168.40.30               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│  TIER 4: VLAN 20 (Guest - Media: Guest Wi-Fi, Apple TVs, Sonos)        │
│  ► BLOCKED from initiating to VLAN 1, VLAN 10*, and VLAN 40            │
│  ► ALLOWED to Internet (WAN) for Spotify/media streaming               │
│  ► EXEMPTION: DNS (UDP/TCP 53) to 192.168.40.185 & 192.168.40.186       │
│  ► EXEMPTION: Sonos Event Callbacks (TCP 3400/3401/3500) to VLAN 10     │
└────────────────────────────────────────────────────────────────────────┘
```

### 📋 Authoritative Inter-VLAN ACL Rule Hierarchy (Araknis 520 Router)

The router evaluates **39 granular rules** (see full rule list in [`network-implementation-plan.md`](../roadmaps/network-implementation-plan.md#1-araknis-520-router-access-control-lists-acl-hierarchy)):

1. **DNS & Security (Rules 1, 3–7)**: Permits UDP/TCP 53, HTTPS DoH (443), and DoQ (853) across LAN (`Any -> Any` for Rule 1 so hardcoded `8.8.8.8`/`8.8.4.4`/`1.1.1.1`/`1.0.0.1` queries routed to `nexus-server` `192.168.40.185` are answered locally by AdGuard Home) and to/from AdGuard Primary (`192.168.40.185`) and Secondary (`192.168.40.186`).
2. **Inter-VLAN NTP Redundancy (Rule 2)**: Permits UDP 123 across all VLANs to both Primary (`192.168.40.185`) and Secondary (`192.168.40.186`) Chrony NTP servers.
3. **Automation & Smart Home (Rules 8–11)**: Permits IoT & Media to Control4 CA-10 (`192.168.10.200`), and IoT to Home Assistant / Homebridge (`192.168.40.249`).
4. **Mainsail 3D Printing Least-Privilege (Rules 12–14, 16–19)**: Permits strictly scoped inbound traffic to Mainsail (`192.168.30.90`) from Trusted LAN (`192.168.10.0/24`), Management (`192.168.1.0/24`), and Servers (`192.168.40.0/24`) for HTTP (port 80), Moonraker (port 7125), and SSH (port 22). Outbound initiation from Mainsail to Trusted LAN and Management is dropped; stateful return packets flow via conntrack.
5. **Media & Entertainment (Rules 15, 20)**: Permits Media (VLAN 20) to Plex (`192.168.40.247:32400`) and Home Assistant (`192.168.40.249:8123`).
6. **Media & Control4 Remotes Bidirectional Inter-VLAN (Rules 21–22)**: Permits All Traffic between the reserved Media & Control4 Remote tier (`192.168.20.120–192.168.20.240`: Control4 T4/Halo/Neeo `.20.120–.123`, Sonos `.20.201–.203`, Google Home/Nest `.20.210–.217`, Apple TV `.20.220–.221`, Google TV/Chromecast/Samsung TV `.20.230–.237`) and Trusted LAN (`192.168.10.0/24`), while untrusted guest DHCP devices (`192.168.20.20–192.168.20.119`) remain isolated by Rule 32.
7. **Testbench mDNS & Inter-Zone Isolation (Rules 23–26 & v2 VLAN Zones)**: Explicitly drops mDNS (UDP 5353) to/from VLAN 150 (CA-1 Test) and VLAN 200 (Core-5 Test), and blocks VLAN 175 (`Ryff Standalone Test`) and VLAN 200 (`Core-5 Test`) from initiating inter-zone traffic into VLAN 10 (`interZoneTo: []` for Zone 10).
8. **Strict Isolation & Segmentation (Rules 27–33)**: Explicitly denies all other cross-VLAN initiation:
   - IoT (VLAN 30) BLOCKED to Management, Trusted LAN, Guest/Media, and Servers (Rules 27–30).
   - Guest/Media (VLAN 20) BLOCKED to Management, Trusted LAN, and Servers (Rules 31–33).
9. **DNS Hardening & Local Interception (Rules 34–36, 39)**: Blocks outbound DNS-over-TLS (TCP 853) on VLAN 20 (Rule 34) and VLAN 30 (Rule 36), and blocks outbound WAN DNS (UDP 53) on VLAN 20 (Rule 35) and globally (Rule 39), while static routes (`8.8.8.8/32`, `8.8.4.4/32`, `1.1.1.1/32`, `1.0.0.1/32` -> `192.168.40.185`) transparently route hardcoded Google/Cloudflare DNS queries to AdGuard Home without timeouts.
10. **WAN Ingress Keepalive Suppression (Rules 37–38)**: Drops inbound WAN1 cloud sweeps destined for idle testbench controllers (`192.168.150.200` CA-1 and `192.168.200.200` Core-5), silencing 5.25M router ARP broadcast floods.
11. **Global WAN DNS Enforcement (Rule 39)**: Drops all outbound UDP 53 to WAN1 (`Deny | In: LAN -> Out: WAN1 | Svc: DNS | Src: Any -> Dst: Any`), completely sealing external DNS bypasses and forcing all network clients across all VLANs through AdGuard Home (`192.168.40.185` / `192.168.40.186`).


> [!NOTE]
> **24-Hour Empirical Packet Validation (2026-10-03)**:
> Ingestion of 32,038,778 packets over 23.97 continuous hours across all 109 ring-buffer captures confirmed **100% boundary integrity**:
> - **VLAN 30 (IoT)**: 0 packets initiated to VLAN 10 or VLAN 1.
> - **VLAN 20 (Guest Media)**: 0 packets initiated to VLAN 1 or VLAN 40; inter-VLAN flows strictly confined to legitimate Sonos-to-Control4 CA-10 communications under Rules 18–19.
> - **Testbench Ingress Gap**: Remediated via Rules 35 & 36 dropping inbound cloud sweeps on WAN1.

---

## 🎵 Sonos & Spotify Connect Configuration Rules

1. **Intra-VLAN Streaming (Phones & Sonos both on VLAN 20)**:
   - **Client Isolation (AP / Station Isolation)** on the Araknis 830 APs and 920 switch must be **DISABLED** for the VLAN 20 SSID. If enabled, the AP prevents wireless phones from directly discovering and streaming to Sonos speakers on the same subnet.
   - VLAN 20 must have DNS port 53 access to `192.168.40.185` and `192.168.40.186` so the speaker can resolve `spotify.com` and cloud streaming servers directly.

2. **Cross-VLAN Streaming (Phones on VLAN 10, Sonos on VLAN 20)**:
   - **Multicast Discovery**: The Araknis 520 router must have **mDNS / SSDP Reflection (IGMP Proxy)** enabled between VLAN 10 and VLAN 20:
     - `224.0.0.251:5353/udp` (mDNS / Spotify Connect / AirPlay)
     - `239.255.255.250:1900/udp` (SSDP / Sonos device discovery)
   - **Sonos Event Subscription Callback (TCP 3400/3401/3500)**:
     - When a phone on VLAN 10 sends a play command to Sonos (port 1400/tcp), Sonos accepts it and **initiates an inbound connection back to the phone on TCP port 3400/3401 or 3500** to push track progress and volume updates.
     - Rule 6 (`ALLOW-SONOS-CALLBACK`) permits this exact return traffic, preventing volume slider freezing and connection drops.

3. **Switch & AP Multicast Performance Tuning (Araknis 920 Switch & 830 APs)**:
   - **IGMP Snooping & Querier**: Enable IGMP Snooping on VLAN 1, 10, 20, 30, and 40. Configure the Araknis 920 switch as the **IGMP Querier** for these VLANs (`address 192.168.1.215`).
   - **Static Multicast Router (mrouter) on AP Trunk Ports**: Configure `set igmp mrouter 10` and `set igmp mrouter 20` on switchports `1/0/3` (Front AP) and `1/0/4` (Back AP). This guarantees that both APs receive mDNS (`224.0.0.251`) and SSDP (`239.255.255.250`) without IGMP snooping pruning, enabling seamless cross-VLAN Spotify Connect and native Sonos app discovery.
   - **Multicast-to-Unicast**: Enable Multicast-to-Unicast conversion on the Araknis 830 APs. This prevents high-frequency discovery multicasts from degrading 2.4 GHz and 5 GHz wireless throughput.

---

## 🛣️ Router Static Routes on Araknis 520

To prevent asymmetric routing blackholes and allow WireGuard and Tailscale to function as out-of-band administrative backdoors across all VLANs:

| Route Name | Destination Subnet | Subnet Mask | Gateway / Next Hop | VLAN Interface | Purpose |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **`Tailscale-Subnet`** | `100.64.0.0` | `255.192.0.0` (`/10`) | `192.168.40.185` | `VLAN 40` | Direct return path for un-NATted Tailscale clients, enabling real client IP logging in AdGuard Home. |
| **`WireGuard-Subnet`** | `10.8.0.0` | `255.255.255.0` (`/24`) | `192.168.40.185` | `VLAN 40` | Guaranteed return path for WireGuard administrative backdoor traffic without relying on host MASQUERADE. |
| **`Google-DNS-1`** | `8.8.8.8` | `255.255.255.255` (`/32`) | `192.168.40.185` | `VLAN 40` | Transparently routes hardcoded Google DNS (`8.8.8.8`) queries from Google Home/Cast/TV devices to AdGuard Home on `nexus-server` (`lo` alias). |
| **`Google-DNS-2`** | `8.8.4.4` | `255.255.255.255` (`/32`) | `192.168.40.185` | `VLAN 40` | Transparently routes hardcoded Google DNS (`8.8.4.4`) queries from Google Home/Cast/TV devices to AdGuard Home on `nexus-server` (`lo` alias). |
| **`Cloudflare-DNS-1`** | `1.1.1.1` | `255.255.255.255` (`/32`) | `192.168.40.185` | `VLAN 40` | Transparently routes hardcoded Cloudflare DNS (`1.1.1.1`) queries to AdGuard Home on `nexus-server` (`lo` alias). |
| **`Cloudflare-DNS-2`** | `1.0.0.1` | `255.255.255.255` (`/32`) | `192.168.40.185` | `VLAN 40` | Transparently routes hardcoded Cloudflare DNS (`1.0.0.1`) queries to AdGuard Home on `nexus-server` (`lo` alias). |

---

## 🛑 Zero-Lockout Implementation Ordering
When applying ACL rules in the Araknis 520 router GUI:
1. **First**: Apply Rule 1 (`ALLOW-VLAN40-ALL`) to protect management ingress.
2. **Second**: Apply Rule 2 (`ALLOW-VLAN10-LAN`).
3. **Third**: Apply DNS and Home Assistant exemption rules (Rules 3, 4, 5, 6).
4. **Finally**: Apply Deny/Block rules (Rules 7 and 8) for VLAN 30 and VLAN 20.
