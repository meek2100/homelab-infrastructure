# 🏷️ Homelab 8-VLAN Segmentation Matrix

This document provides the authoritative network segmentation specification for the homelab, defined on the **Araknis 520 Dual-WAN Router**, distributed via 802.1Q trunks on the **Araknis 920 Switch**, and broadcast via **Araknis 830 APs**.

---

## 📋 VLAN Allocation Table

| VLAN ID | Official Name | Subnet | Gateway (Araknis 520) | Security Zone | DNS Servers (DHCP Option 6) | Primary Purpose & Device Scope |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | `Management` | `192.168.1.0/24` | `192.168.1.1` | Trusted | `192.168.40.185`, `192.168.40.186` | Hypervisors (`pve` .250, `pve2` .240, `pve3` .245), switches (`.215`), APs (`.237`), OpenWrt (`.225`), router GUI (`secure.theurer.dev`) |
| **10** | `Main - Trusted` | `192.168.10.0/24` | `192.168.10.1` | Trusted | `192.168.40.185`, `192.168.40.186` | Primary workstations, personal laptops, smartphones, trusted family devices |
| **20** | `Guest - Media` | `192.168.20.0/24` | `192.168.20.1` | Semi-Isolated | `192.168.40.185`, `192.168.40.186` | Guest Wi-Fi clients, smart TVs, Apple TV, media streamers (isolated from LAN) |
| **30** | `Isolated - IOT` | `192.168.30.0/24` | `192.168.30.1` | Untrusted | `192.168.40.185`, `192.168.40.186` | Smart plugs, smart bulbs, Wi-Fi sensors, Tuya/ESPHome/Shelly devices (no return LAN access) |
| **40** | `Servers - Admin` | `192.168.40.0/24` | `192.168.40.1` | Protected Server | `192.168.40.185`, `192.168.40.186` | Core identity & server infrastructure: Primary DNS/NPM (`.185`), Secondary DNS (`.186`), NAS Admin (`.248`), `pve2` (`.240`) |
| **100** | `Wireshark - Debug` | Dynamic / Sniff | - | Inspection | `192.168.40.185`, `192.168.40.186` | Dedicated network traffic inspection, SPAN mirror destination, and packet capture analysis |
| **150** | `CA-1 Test` | Dynamic / Test | - | Isolated Lab | `192.168.40.185`, `192.168.40.186` | Control4 CA-1 Automation Controller lab network (tunneled to OpenWrt via `vxlan150` on VM 107) |
| **200** | `Core-5 Test` | Dynamic / Test | - | Isolated Lab | `192.168.40.185`, `192.168.40.186` | Control4 CORE 5 Flagship Automation Controller testing and multi-room AVoIP integration |
| **WAN2** | `Storage & WAN2` | `10.25.25.0/24` | `10.25.25.1` | Dedicated Transit | Local / Unbound | Dedicated WAN2 internet egress for `discovery-server` (`.246`) and L2 line-rate storage to `nas-server` (`.248`) |

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
     - An explicit ACL rule must permit: `Source VLAN 20 (Sonos IPs) ──► Destination VLAN 10 (TCP 3400, 3401, 3500)`.

---

## 🛣️ Router Static Routes on Araknis 520

To prevent asymmetric routing blackholes and allow WireGuard and Tailscale to function as out-of-band administrative backdoors across all VLANs:

| Route Name | Destination Subnet | Subnet Mask | Gateway / Next Hop | VLAN Interface | Purpose |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **`Tailscale-Subnet`** | `100.64.0.0` | `255.192.0.0` (`/10`) | `192.168.40.185` | `VLAN 40` | Direct return path for un-NATted Tailscale clients, enabling real client IP logging in AdGuard Home. |
| **`WireGuard-Subnet`** | `10.8.0.0` | `255.255.255.0` (`/24`) | `192.168.40.185` | `VLAN 40` | Guaranteed return path for WireGuard administrative backdoor traffic. |

---

## 🛑 Zero-Lockout Implementation Ordering
When applying ACL rules in the Araknis 520 router GUI:
1. **First**: Apply Rule 1 (`Permit VLAN 40 to ALL VLANs`) to protect management ingress.
2. **Second**: Apply Rule 2 (`Permit VLAN 10 to VLAN 40, VLAN 30, and VLAN 20`).
3. **Third**: Apply DNS and Home Assistant exemption rules for VLAN 30 and VLAN 20.
4. **Finally**: Apply Deny/Block rules for VLAN 30 and VLAN 20.
