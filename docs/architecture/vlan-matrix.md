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
| **150** | `CA-1 Test` | `192.168.150.0/24` | `192.168.150.1` | Isolated Lab | `1.1.1.1`, `1.0.0.1` | Control4 CA-1 Automation Controller lab network (OvrC location `CA1 Test`; tunneled via `vxlan150` on VM 107; trunked to Pakedge SX-8P on SW920 Port 1/0/7) |
| **175** | `Ryff Standalone Test`| `192.168.175.0/24` | `192.168.175.1` | Isolated Lab | `192.168.40.185`, `192.168.40.186` | Triad SA1 Streaming Amp / Ryff audio test network (OvrC location `Ryff Standalone Test`; SW920 Port 1/0/5 access VLAN 175) |
| **200** | `Core-5 Test` | `192.168.200.0/24` | `192.168.200.1` | Isolated Lab | `1.1.1.1`, `1.0.0.1` | Control4 CORE 5 Flagship Automation Controller testing and multi-room AVoIP (OvrC location `Core5 Test`; SW920 Port 1/0/8 access VLAN 200) |
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

The router evaluates **36 granular rules** (see full rule list in [`network-implementation-plan.md`](../roadmaps/network-implementation-plan.md#1-araknis-520-router-access-control-lists-acl-hierarchy)):

1. **DNS & Security (Rules 1–6)**: Permits UDP/TCP 53, HTTPS DoH (443), and DoQ (853) to/from AdGuard Primary (`192.168.40.185`) and Secondary (`192.168.40.186`).
2. **Automation & Smart Home (Rules 7–10)**: Permits IoT & Media to Control4 CA-10 (`192.168.10.200`), and IoT to Home Assistant / Homebridge (`192.168.40.249`).
3. **Mainsail 3D Printing (Rules 11–14, 16, 20–21)**: Permits bidirectional traffic between Mainsail (`192.168.30.90`) and Trusted LAN (`192.168.10.0/24`), Management (`192.168.1.0/24`), and Servers (`192.168.40.0/24`) for Moonraker API (7125), HTTP (80), and SSH (22).
4. **Media & Entertainment (Rules 15, 17)**: Permits Media (VLAN 20) to Plex (`192.168.40.247:32400`) and Home Assistant (`192.168.40.249:8123`).
5. **Sonos Bidirectional Inter-VLAN (Rules 18–19)**: Permits All Traffic between tightened Sonos block (`192.168.20.201–192.168.20.205`) and Trusted LAN (`192.168.10.0/24`), enabling SSDP/mDNS discovery, TCP 1400 control, and reverse UPnP event callbacks without dropouts.
6. **Testbench mDNS Isolation (Rules 22–25)**: Explicitly drops mDNS (UDP 5353) to/from VLAN 150 (CA-1 Test) and VLAN 200 (Core-5 Test) to prevent Bonjour repeater hostname leaks.
7. **Strict Isolation & Segmentation (Rules 26–32)**: Explicitly denies all other cross-VLAN initiation:
   - IoT (VLAN 30) BLOCKED to Management, Trusted LAN, Guest/Media, and Servers.
   - Guest/Media (VLAN 20) BLOCKED to Management, Trusted LAN, and Servers.
8. **DNS Hardening (Rules 33–34)**: Blocks outbound DNS-over-TLS (TCP 853) on VLAN 20 and VLAN 30 to prevent devices from bypassing AdGuard Home filtering.
9. **WAN Ingress Keepalive Suppression (Rules 35–36)**: Drops inbound WAN1 cloud sweeps destined for idle testbench controllers (`192.168.150.200` CA-1 and `192.168.200.200` Core-5), silencing 5.25M router ARP broadcast floods.
10. **Device Internet Quarantining (Rule 37)**: Drops outbound WAN internet from Downstairs Guest TV TCL Roku (`192.168.20.240`), preventing lockups and mandatory Roku cloud login prompts while allowing local streaming via Chromecast (`192.168.20.231`).

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
   - **IGMP Snooping & Querier**: Enable IGMP Snooping on VLAN 10, 20, and 40. Configure the Araknis 920 switch as the **IGMP Querier** for these VLANs.
   - **Multicast-to-Unicast**: Enable Multicast-to-Unicast conversion on the Araknis 830 APs. This prevents high-frequency discovery multicasts from degrading 2.4 GHz and 5 GHz wireless throughput.

---

## 🛣️ Router Static Routes on Araknis 520

To prevent asymmetric routing blackholes and allow WireGuard and Tailscale to function as out-of-band administrative backdoors across all VLANs:

| Route Name | Destination Subnet | Subnet Mask | Gateway / Next Hop | VLAN Interface | Purpose |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **`Tailscale-Subnet`** | `100.64.0.0` | `255.192.0.0` (`/10`) | `192.168.40.185` | `VLAN 40` | Direct return path for un-NATted Tailscale clients, enabling real client IP logging in AdGuard Home. |
| **`WireGuard-Subnet`** | `10.8.0.0` | `255.255.255.0` (`/24`) | `192.168.40.185` | `VLAN 40` | Guaranteed return path for WireGuard administrative backdoor traffic without relying on host MASQUERADE. |

---

## 🛑 Zero-Lockout Implementation Ordering
When applying ACL rules in the Araknis 520 router GUI:
1. **First**: Apply Rule 1 (`ALLOW-VLAN40-ALL`) to protect management ingress.
2. **Second**: Apply Rule 2 (`ALLOW-VLAN10-LAN`).
3. **Third**: Apply DNS and Home Assistant exemption rules (Rules 3, 4, 5, 6).
4. **Finally**: Apply Deny/Block rules (Rules 7 and 8) for VLAN 30 and VLAN 20.
