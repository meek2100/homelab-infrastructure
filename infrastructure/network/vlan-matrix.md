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

## 🔒 Inter-VLAN Firewall Boundaries

```text
[Main - Trusted (VLAN 10)] ───────────────► ALL VLANs (Unrestricted Outbound)
[Management (VLAN 1)]      ───────────────► ALL VLANs (Unrestricted Outbound)
[Servers - Admin (VLAN 40)] ──────────────► Only Established/Related to other VLANs
[Isolated - IOT (VLAN 30)]  ─────────X───► Blocked to VLAN 1, 10, 20, 40 (Internet Only + DNS 53 to .185/.186)
[Guest - Media (VLAN 20)]  ─────────X───► Blocked to VLAN 1, 10, 40 (Internet Only + DNS 53 to .185/.186)
```

1. **DNS Enforcement (Port 53)**:
   - All VLANs are allowed to reach `192.168.40.185` (Primary) and `192.168.40.186` (Secondary) on UDP/TCP port 53.
   - Any external DNS query attempting to reach hardcoded resolvers (e.g. `8.8.8.8`) is captured and redirected to `192.168.40.185`.

2. **Inbound Application Ingress (Port 80/443)**:
   - All VLANs are allowed to reach Nginx Proxy Manager at `192.168.40.185` on ports 80 and 443 to access reverse-proxied applications (e.g. `wireshark.secure.theurer.dev`, `portainer.secure.theurer.dev`).

3. **Smart Home Home Assistant Traversal**:
   - `luna-server` (`homeassistant`) initiates outbound connections into `Isolated - IOT` (VLAN 30) to control Zigbee/Z-Wave bridges and smart devices.
   - Return traffic is permitted via stateful inspection (`ESTABLISHED,RELATED`). IoT devices cannot initiate unsolicited connections back into server administration or management subnets.
