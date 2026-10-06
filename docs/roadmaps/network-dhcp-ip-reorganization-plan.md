# 🌐 Network DHCP Reorganization, IP Tiering & Sonos Inter-VLAN Roadmap

This authoritative implementation plan defines the complete architecture, IP tiering schema, device migration mappings, and step-by-step execution runbook for reorganizing all homelab subnets and resolving Sonos cross-VLAN control across the **Araknis 520 router** (`192.168.1.1` / `192.168.10.1`) and **Araknis 920 switch** (`192.168.1.215`).

---

## 🎯 Executive Summary & Objectives

1. **Resolve Sonos Inter-VLAN Discovery & Control**:
   - Enable reliable control of Sonos speakers residing on **VLAN 20 (Guest/AV)** from personal devices on **VLAN 10 (Main - Trusted)**.
   - Eliminate multicast frame drops on the Araknis 920 switch and leverage native mDNS reflection while keeping router UPnP IGD strictly disabled.
2. **Implement Enterprise Subnet Tiering Across All 7 VLANs**:
   - Shift dynamic DHCP client pools from `.100–.254` to `.20–.99` across all subnets.
   - Establish dedicated, predictable functional IP tiers for workstations, smart home hubs, cameras, printers, AV controllers, and hypervisors.
3. **Consolidate Device Clusters for Narrow, Hardened ACLs**:
   - Group Sonos speakers into a compact sequential block (`192.168.20.201–.203`) to clamp router ACL Rule 18 down from an 86-host leaky range to exactly 3 hosts.
   - Cluster Control4 automation controllers (`192.168.10.200–.208`), Google Cast devices (`192.168.20.210–.217`), Smart TVs (`192.168.20.230–.237`), and network printers (`192.168.10.180–.182`).
4. **Account for Offline & Testbench Hardware Discovered in OvrC**:
   - Explicitly reserve and map offline testbench controllers (Triad SA1, Core 5, EA-1, Core Lite), physical security gear (Control4 DS2 Video Doorbell, Vivint Pro Outdoor Camera ODC350), IP PDUs (WattBox 12-outlet), and smart appliances (Midea AC, Moen valves) to prevent IP collisions when they wake up.
5. **Lay Foundation for Future Zero-Trust Network Architecture (ZTNA)**:
   - Dynamic leases in `.20–.99` become the default "unverified/transient" tier.
   - Authoritative reservations in `.100–.239` identify verified, inventory-controlled assets.
6. **Zero Physical Touching of Devices**:
   - All end devices (phones, tablets, printers, cameras, Sonos speakers, TVs) remain on standard DHCP without touching local static IP configurations.

---

## 🔬 Root Cause Analysis: Why Sonos Control Failed from VLAN 10

### 1. Araknis 920 Switch Dropping SSDP (Missing Static MRouter on Port 1/0/1)
- **Mechanism**: The 920 switch operates as an active IGMP Querier on VLAN 10 and VLAN 20 (`set igmp querier 10/20`, IP `192.168.1.215`). Because the switch itself generates IGMP general queries, it **never dynamically learns** an upstream multicast router on trunk port `1/0/1` (the link to the Araknis 520 router).
- **Symptom**: `show igmpsnooping mrouter vlan 10` and `vlan 20` were confirmed **EMPTY**.
- **Impact**: Multicast discovery packets (`239.255.255.250:1900` SSDP) transmitted by the Sonos app on VLAN 10 were snooped by the switch and forwarded *only* to subscribed ports within VLAN 10. They were **never forwarded up port 1/0/1 to the router**, preventing the router from ever seeing the discovery requests.
- **Remediation**: Execute `set igmp mrouter interface 1/0/1` on the switch for both VLAN 10 and VLAN 20.

### 2. Router UPnP IGD Remains Strictly Disabled (Zero-Trust Security Standard)
- **Security Reality**: On edge routers, the `enableUPnP` setting controls the **UPnP Internet Gateway Device (IGD)** daemon (`miniupnpd`). UPnP IGD allows unauthenticated LAN clients to dynamically punch open inbound port-forwarding holes on the public WAN interface without administrator consent. This is a severe, well-documented security exposure (e.g. CallStranger CVE-2020-12695, unauthenticated port mapping).
- **Sonos Architectural Reality**: Sonos **does NOT require UPnP IGD**. Sonos is an internal audio streaming ecosystem; it never requests or needs inbound WAN port forwarding from the public internet. Modern Sonos (S2) discovers speakers via **mDNS / Bonjour** (`_sonos._tcp.local` on `224.0.0.251:5353`), which the Araknis 520 router **already natively repeats** (`enableBonjour: true`).
- **Policy Invariant**: `enableUPnP: false` will **REMAIN DISABLED** on the Araknis 520 router. Sonos discovery is achieved via native mDNS reflection + 920 switch static mrouter forwarding on Port 1/0/1, keeping the WAN perimeter 100% locked down.

### 3. ACL Rule 18 Clamped to Leaky Slice & Rule 31 Inter-VLAN Drop
- **Mechanism**:
  - Router Rule 18 (`Sonos to Trusted LAN`) permitted `192.168.20.140–192.168.20.225 -> 192.168.10.1–254`.
  - Router Rule 31 denies all `192.168.20.1–254 -> 192.168.10.1–254`.
- **Impact**: Return UPnP HTTP event callbacks (TCP ports 3400/3500) from speakers or media services outside that arbitrary slice were dropped. Furthermore, the rule was unnecessarily wide (86 addresses) for 3 physical speakers.
- **Remediation**: Reassign Sonos speakers to sequential IPs `192.168.20.201–.203` and clamp Rule 18 source range to `192.168.20.201–192.168.20.205`.

### 4. Why PIM-SM on the Switch Was Rejected
- An external AI suggested moving Inter-VLAN routing to the Araknis 920 switch with PIM-SM.
- **Why this fails**: Sonos SSDP M-SEARCH frames are transmitted with **`TTL = 1`**. RFC 1812 mandates that any L3 routing hop (switch or router) decrements TTL to 0 and drops the packet. An L3 switch interface cannot route TTL=1 frames without an application-layer SSDP proxy/bidi-repeater.
- **Security hazard**: Enabling L3 routing on the switch bypasses all 32 stateful firewall rules on the 520 router, exposes trusted VLAN 10 directly to IoT/guest networks, and creates asymmetric routing loops with WAN traffic.

---

## 🏛️ Enterprise Subnet Tiering Architecture

Every `/24` subnet across the homelab adopts this standardized allocation schema:

```
+-----------------------------------------------------------------------------------+
| .1        | .2 - .19      | .20 - .99    | .100 - .149   | .150 - .179 | .180 - .199 | .200 - .239 | .240 - .254  |
| Gateway   | Low Reserved  | Dynamic DHCP | Workstations  | Smart Hubs, | Network     | Specialized | Hypervisors, |
| (520 Rtr) | (VIPs/VRRP)   | (Transient/  | & Personal    | Security &  | Printers    | AV & Ctrl   | Infrastructure|
|           |               |  Guest Pool) | Devices       | Cameras     |             | (Sonos/C4)  | & Server VMs |
+-----------------------------------------------------------------------------------+
```

### Tier Descriptions & Policies

| Range | Tier Name | Purpose & Allocation Policy | DHCP Mechanism |
| :--- | :--- | :--- | :--- |
| **`.1`** | **Default Gateway** | Araknis 520 Router interface IP on this VLAN. | Static on router |
| **`.2 – .19`** | **Low Reserved** | Network appliances, future VRRP/CARP virtual IPs, secondary gateways. | Static / Reserved |
| **`.20 – .99`** | **Dynamic DHCP Pool** | Transient clients, guest devices, new unverified endpoints. 80 available addresses per subnet. Future zero-trust quarantine zone. | Dynamic Pool (Router) |
| **`.100 – .149`** | **Workstations & Personal** | Primary desktop PCs, laptops, mobile phones, iPads, Mac Minis, consoles. | DHCP Reservation |
| **`.150 – .179`** | **Smart Hubs, Security & Cameras** | Hue bridges, Vivint panels/cameras, Luma NVRs, WattBox PDUs, intercoms. | DHCP Reservation |
| **`.180 – .199`** | **Network Printers** | 2D label printers, laser printers, multifunction document copiers. | DHCP Reservation |
| **`.200 – .239`** | **Specialized AV & Automation** | Control4 controllers (CA-10, Core-1, Core-3, Core-5, EA-1, Core Lite), Sonos speakers, Google Cast, TVs. | DHCP Reservation |
| **`.240 – .254`** | **Infrastructure & Hypervisors** | Proxmox hosts (`pve`, `pve2`, `pve3`), core switches, APs, server VMs. | DHCP Reservation / Static |

> [!NOTE]
> **Out-of-Pool DHCP Reservations**: The Araknis 520 router natively supports DHCP reservations configured outside the dynamic range. Setting the dynamic pool to `.20–.99` allows all reserved infrastructure and personal devices (`.100–.254`) to receive deterministic addresses via DHCP without consuming pool leases or triggering IP conflicts.

---

## 🗺️ Master IP Migration & Reservation Matrix

### 1. VLAN 10 — Main / Trusted LAN (`192.168.10.0/24`)
*Dynamic DHCP Pool: `192.168.10.20 – 192.168.10.99`*

| Device Name | MAC Address | Current IP | Proposed IP | Functional Tier | Notes & Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Araknis 520 Gateway** | — | `192.168.10.1` | `192.168.10.1` | Gateway | Primary interface |
| **Desktop PC (011PRD Wired)** | `A0:29:19:8F:5D:45` | `192.168.1.117` | `192.168.10.102` | Workstations | Aligns wired NIC with Netgear port 2 (VLAN 10) |
| **Desktop PC (011PRD Wi-Fi)** | `F4:46:37:7A:6A:7A` | `192.168.10.118` | `192.168.10.103` | Workstations | Sequential with wired NIC |
| **Mac Mini** | `14:98:77:3E:4E:8D` | `192.168.10.126` | `192.168.10.104` | Workstations | Workstation block |
| **Pixel 10 Pro** | `6E:72:FF:20:9B:AA` | `192.168.10.40` | `192.168.10.110` | Personal Mobile | Live Wi-Fi MAC updated |
| **Kimber iPhone** | `66:AF:7A:CC:EB:E4` | `192.168.10.123` | `192.168.10.111` | Personal Mobile | Mobile phone block |
| **Kimber iPad** | `96:5D:E6:EE:4E:5B` | `192.168.10.124` | `192.168.10.112` | Personal Mobile | Tablet block |
| **Kimber iPad Pro** | `BA:07:67:57:ED:7D` | `192.168.10.124` | `192.168.10.113` | Personal Mobile | Distinct MAC from OvrC |
| **Darin iPhone** | `F0:C3:71:4A:8A:27` | `192.168.10.45` | `192.168.10.114` | Personal Mobile | Mobile phone block |
| **iPhone Client 1** | `EE:A8:80:16:D5:A9` | `192.168.10.42` | `192.168.10.115` | Personal Mobile | Guest / family mobile |
| **iPhone Client 2** | `32:C2:B9:5F:40:56` | `192.168.10.64` | `192.168.10.116` | Personal Mobile | Guest / family mobile |
| **Pakedge Lab AP Client** | `90:A7:C1:4B:1D:71` | `192.168.10.41` | `192.168.10.117` | Work Testbench | Pakedge test host |
| **Nintendo Switch 1** | `A4:C1:E8:13:20:48` | `192.168.10.127` | `192.168.10.130` | Consoles | Handheld gaming block |
| **Nintendo Switch 2** | `98:E2:55:3D:C4:B9` | `192.168.10.132` | `192.168.10.131` | Consoles | Handheld gaming block |
| **Nex Playground** | `48:5C:2C:8C:43:7C` | `192.168.10.65` | `192.168.10.132` | Consoles | Active console in Living Room |
| **Philips Hue Bridge** | `EC:B5:FA:8D:E0:05` | `192.168.10.101` | `192.168.10.150` | Smart Hubs | Smart home lighting bridge |
| **Vivint Security Panel** | `88:6A:E3:D8:EB:1C` | `192.168.10.108` | `192.168.10.151` | Security | Primary security panel |
| **Vivint Outdoor Cam (ODC350)**| `84:EB:3E:39:08:27` | `192.168.1.112` | `192.168.10.152` | Security | Pro outdoor camera (from OvrC) |
| **Control4 DS2 Door Station** | `7C:1E:B3:F0:26:55` | `192.168.10.182` | `192.168.10.156` | Access Control | 2N Video Intercom / Doorbell |
| **Luma Bridge** | `D4:6A:91:19:00:54` | `192.168.10.121` | `192.168.10.160` | Surveillance | Luma ecosystem camera bridge |
| **Luma X20 Cam 1** | `D4:6A:91:9C:00:67` | `192.168.10.103` | `192.168.10.161` | Surveillance | IP camera sequential block |
| **Luma X20 Cam 2** | `D4:6A:91:9C:00:8A` | `192.168.10.104` | `192.168.10.162` | Surveillance | IP camera sequential block |
| **Luma X20 Cam 3** | `D4:6A:91:9C:00:69` | `192.168.10.105` | `192.168.10.163` | Surveillance | IP camera sequential block |
| **Wattbox WB-800 PDU** | `14:3F:C3:02:25:71` | `192.168.10.170` | `192.168.10.170` | Power Mgmt | 12-Outlet IP PDU (controls bench) |
| **Splatoon Label Printer** | `88:A2:9E:14:32:76` | `192.168.10.64` | `192.168.10.180` | Printers | Moved out of dynamic pool |
| **HP LaserJet Web** | `F8:0D:AC:D9:32:47` | `192.168.10.195` | `192.168.10.181` | Printers | Update Prometheus line 313 |
| **Brother QL-1110NWB (Wired)**| `00:80:77:5C:F6:11`| `192.168.10.196` | `192.168.10.182` | Printers | Update Prometheus line 318 |
| **Control4 CA-10 Director** | `00:0F:FF:20:74:D0` | `192.168.10.200` | `192.168.10.200` | Automation | Master Automation Director |
| **Control4 T5 Touchscreen** | `00:0F:FF:0B:39:4E` | `192.168.10.201` | `192.168.10.201` | Automation | 8" In-Wall Desk Panel |
| **Control4 Core-1** | `00:0F:FF:0C:31:E8` | `192.168.10.35` | `192.168.10.202` | Automation | Update Prometheus line 291 |
| **Control4 Core-3** | `00:0F:FF:9F:0C:72` | `192.168.10.153` | `192.168.10.203` | Automation | Update Prometheus line 296 |
| **Control4 Core-5** | `00:0F:FF:0B:31:AF` | `192.168.10.181` | `192.168.10.204` | Automation | Master Core-5 controller (from OvrC) |
| **Control4 EA-1** | `00:0F:FF:93:1C:56` | `192.168.10.213` | `192.168.10.205` | Automation | Single-room controller (from OvrC) |
| **Control4 Core Lite** | `00:0F:FF:0B:35:E9` | `192.168.10.220` | `192.168.10.206` | Automation | Secondary controller (from OvrC) |
| **Triad SA1 Streaming Amp** | `00:0F:FF:9F:33:63` | `192.168.10.138` | `192.168.10.207` | Automation | Triad streaming amp (from OvrC) |
| **Control4 T4 10" Tabletop** | `58:D5:0A:A1:79:0A` | `192.168.20.163` | `192.168.10.208` | Automation | Moved from VLAN 20 to Director VLAN 10 |

---

### 2. VLAN 20 — Guest / AV / Media (`192.168.20.0/24`)
*Dynamic DHCP Pool: `192.168.20.20 – 192.168.20.99`*

| Device Name | MAC Address | Current IP | Proposed IP | Functional Tier | Notes & Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Araknis 520 Gateway** | — | `192.168.20.1` | `192.168.20.1` | Gateway | No change |
| **Samsung Galaxy S9** | `3A:BF:95:75:C9:57` | `192.168.20.71` | `192.168.20.101` | Guest Mobile | Moved from VLAN 10 to Insomniac_Guest |
| **Lenovo Yoga Tab 3 Plus** | `48:88:CA:E1:BA:DD` | `192.168.20.30` | `192.168.20.102` | Guest Mobile | Moved from VLAN 10 to Insomniac_Guest |
| **Guest Mobile Device 1** | `56:81:3E:71:AF:5F` | `192.168.20.82` | `192.168.20.103` | Guest Mobile | Guest wireless endpoint |
| **Guest Mobile Device 2** | `BA:98:6B:7F:13:B7` | `192.168.20.90` | `192.168.20.104` | Guest Mobile | Guest wireless endpoint |
| **Control4 Halo Touch Remote** | `50:26:EF:26:C9:AD` | `192.168.20.87` | `192.168.20.120` | Remotes & Acc | Wi-Fi remote on Insomniac_Guest |
| **Control4 Halo Tactile Remote** | `24:CD:8D:6F:FD:A0` | `192.168.20.34` | `192.168.20.121` | Remotes & Acc | Wi-Fi remote on Insomniac_Guest |
| **Control4 SR-260 Remote** | `34:15:13:D2:BD:1E` | `192.168.20.85` | `192.168.20.122` | Remotes & Acc | Wi-Fi remote on Insomniac_Guest |
| **Hatch Rest+ Sound Machine** | `24:62:AB:BD:94:8C` | `192.168.20.44` | `192.168.20.125` | Smart Nursery | Moved to Insomniac_Guest |
| **Sonos Move 2 (Living Room 1)**| `74:CA:60:24:40:BE`| `192.168.20.223` | `192.168.20.201` | Sonos Block | Target of ACL Rule 18 |
| **Sonos Move 2 (Living Room 2)**| `74:CA:60:24:4A:50`| `192.168.20.143` | `192.168.20.202` | Sonos Block | Target of ACL Rule 18 |
| **Sonos Roam 2 (Office)** | `C4:38:75:C6:54:A4`| `192.168.20.205` | `192.168.20.203` | Sonos Block | Target of ACL Rule 18 |
| *[Reserved for Sonos expansion]* | — | — | `192.168.20.204–.209`| Sonos Block | Reserved for future speakers |
| **Guest Bedroom Speaker** | `F4:F5:D8:D9:B2:6A` | `192.168.20.106` | `192.168.20.210` | Google Cast | Audio speaker cluster |
| **Garage Speaker** | `F4:F5:D8:BD:4E:60` | `192.168.20.121` | `192.168.20.211` | Google Cast | Audio speaker cluster |
| **Primary Bedroom Speaker** | `F4:F5:D8:A6:88:D0` | `192.168.20.230` | `192.168.20.212` | Google Cast | Audio speaker cluster |
| **Emmy's Bedroom Speaker** | `E4:F0:42:0E:43:98` | `192.168.20.202` | `192.168.20.213` | Google Cast | Moved away from .202 to avoid Sonos clash |
| **Emmy's Bathroom Speaker** | `48:D6:D5:73:61:91` | `192.168.20.137` | `192.168.20.214` | Google Cast | Offline 13 days (from OvrC) |
| **Kitchen Display (Nest Hub)**| `7C:D9:5C:7C:92:F6` | `192.168.20.220` | `192.168.20.215` | Google Cast | Smart display cluster |
| **Emmy's Landing Display** | `1C:F2:9A:35:AF:30` | `192.168.20.186` | `192.168.20.216` | Google Cast | Smart display cluster |
| **Office Display (Nest Hub)** | `7C:D9:5C:7D:BE:0A` | `192.168.20.245` | `192.168.20.217` | Google Cast | Offline 21 days (from OvrC) |
| **Living Room TV (Chromecast)**| `14:C1:4E:BC:1C:B6`| `192.168.20.116` | `192.168.20.230` | Smart Displays | TV streaming cluster (Living Room) |
| **Downstairs Guest TV (Chromecast)**| `BC:DF:58:65:5A:32` | `192.168.20.236` | `192.168.20.231` | Smart Displays | Media streamer on Downstairs Guest TV |
| **Sewing Room TV (Chromecast)** | `20:1F:3B:34:8F:1A` | `192.168.1.137` | `192.168.20.232` | Smart Displays | Chromecast with Google TV (Upstairs Sewing Room) |
| **Office TV** | `BC:DF:58:60:0F:2E` | `192.168.1.28` | `192.168.20.233` | Smart Displays | Offline 2 months (from OvrC) |
| **Primary Bedroom TV (Chromecast)**| `B8:7B:D4:DD:25:03` | `192.168.1.37` | `192.168.20.234` | Smart Displays | Chromecast with Google TV (Primary Bedroom) |
| **Primary Bedroom TV (Samsung)** | `7C:0A:3F:90:8A:6E` | `192.168.20.183` | `192.168.20.235` | Smart Displays | Samsung Smart TV (Primary Bedroom) |
| **Living Room TV (Samsung)** | `54:3A:D6:53:6A:8E` | `192.168.20.222` | `192.168.20.236` | Smart Displays | Samsung Smart TV (Living Room) |
| **Sewing Room TV (Samsung)** | `C4:73:1E:24:DE:15` | `192.168.20.203` | `192.168.20.237` | Smart Displays | Samsung Smart TV (Upstairs Sewing Room) |
| **Downstairs Guest TV (TCL Roku)** | `78:93:C3:32:A2:C9` | `192.168.20.53` | `192.168.20.240` | Smart Displays | TCL TV with built-in Roku (WAN BLOCKED via ACL Rule 37) |
| **Guest Dynamic Wireless** | *(Dynamic)* | `.20.100–.254` | `192.168.20.20–.99` | Guest Dynamic | Isolated from internal subnets |

---

### 3. VLAN 30 — IoT / Home Automation / 3D Printing (`192.168.30.0/24`)
*Dynamic DHCP Pool: `192.168.30.20 – 192.168.30.99`*

| Device Name | MAC Address | Current IP | Proposed IP | Functional Tier | Notes & Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Araknis 520 Gateway** | — | `192.168.30.1` | `192.168.30.1` | Gateway | No change |
| **Mainsail 3D Printer (RPi)**| `E4:5F:01:78:DF:81` | `192.168.30.90` | `192.168.30.90` | 3D Printing | Maintained at `.30.90` (Klipper/Moonraker Rules 11-14) |
| **ecobee Smart Thermostat** | `44:61:32:51:14:7E` | `192.168.30.167` | `192.168.30.150` | Climate Control | HVAC thermostat |
| **Midea Air Conditioning** | `F0:C9:D1:8A:E0:01` | `192.168.1.49` | `192.168.30.155` | Climate Control | Smart AC unit (from OvrC) |
| **Apple "Office" Hub** | `90:DD:5D:E1:E5:FE` | `192.168.30.127` | `192.168.30.160` | Smart Hubs | Thread / HomeKit border router |
| **Laird Connectivity Module**| `C0:EE:40:70:BC:9D` | `192.168.30.163` | `192.168.30.163` | Smart Modules | Wireless bridge module |
| **Moen Smart Water Valve 1** | `D0:B0:CD:03:2C:88` | `192.168.30.180` | `192.168.30.170` | Utilities | Smart water shutoff (from OvrC) |
| **Moen Smart Water Valve 2** | `D0:B0:CD:03:C9:54` | `192.168.30.194` | `192.168.30.171` | Utilities | Smart faucet / shutoff (from OvrC) |
| **Roborock Robotic Vacuum** | `24:9E:7D:58:58:32` | `192.168.30.108` | `192.168.30.175` | Appliances | Smart cleaning appliance |
| **GE Smart Appliance 1** | `D8:28:C9:75:63:F6` | `192.168.30.106` | `192.168.30.176` | Appliances | Smart home appliance |
| **GE Smart Appliance 2** | `D8:28:C9:61:57:A5` | `192.168.30.137` | `192.168.30.177` | Appliances | Smart home appliance |
| **Tuya Smart Light 1** | `FC:3C:D7:0F:E0:84` | `192.168.30.64` | `192.168.30.180` | Smart Lighting | Contiguous Tuya block (.180–.184) |
| **Tuya Smart Light 2** | `FC:3C:D7:10:A4:93` | `192.168.30.44` | `192.168.30.181` | Smart Lighting | Contiguous Tuya block (.180–.184) |
| **Tuya Smart Light 3** | `FC:3C:D7:10:D7:47` | `192.168.30.77` | `192.168.30.182` | Smart Lighting | Contiguous Tuya block (.180–.184) |
| **Tuya Smart Light 4** | `FC:3C:D7:11:19:D6` | `192.168.30.75` | `192.168.30.183` | Smart Lighting | Contiguous Tuya block (.180–.184) |
| **Tuya Smart Light 5** | `FC:3C:D7:12:CE:8C` | `192.168.30.45` | `192.168.30.184` | Smart Lighting | Contiguous Tuya block (.180–.184) |
| **Rachio 3 Smart Sprinkler** | `70:74:14:C0:2C:6A` | `192.168.30.34` | `192.168.30.190` | Irrigation | Smart sprinkler controller |
| **Moen Flo Smart Water Shutoff**| `3C:E4:B0:85:D4:F6`| `192.168.30.83` | `192.168.30.191` | Utilities | Smart whole-home shutoff |
| **Chamberlain MyQ Smart Garage**| `2C:D2:6B:86:D7:61`| `192.168.30.95` | `192.168.30.192` | Access Control | Smart garage hub |
| **Smart Appliance MXCHIP** | `04:78:63:3E:F9:25` | `192.168.30.63` | `192.168.30.193` | Appliances | Smart appliance Wi-Fi module |
| **IoT Dynamic Clients** | *(Dynamic)* | `.30.100–.254` | `192.168.30.20–.99` | IoT Dynamic | Transient smart plugs, unassigned |

---

### 4. VLAN 1 — Management LAN (`192.168.1.0/24`)
*Dynamic DHCP Pool: `192.168.1.20 – 192.168.1.99`*

| Device Name | MAC Address | Current IP | Proposed IP | Functional Tier | Notes & Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Araknis 520 Router** | `14:3F:C3:91:0F:8A` | `192.168.1.1` | `192.168.1.1` | Gateway | Untagged management interface |
| **Uctronics PoE Adapter (RPi)** | `00:E0:4C:36:06:63` | `192.168.1.91` | `192.168.1.150` | Appliances | Moved out of dynamic pool |
| **vxlan-server (VM 107 br0)** | `36:CF:D5:50:A0:FC` | `192.168.1.150` | `192.168.1.151` | Infrastructure | Sequential with networking VMs |
| **Binary MoIP 4K Controller** | `D4:6A:91:62:A2:7E` | `192.168.1.137` | `192.168.1.155` | AV Infrastructure | B-900-MOIP 4K controller (from OvrC) |
| **Pakedge SX-8P Switch** | `90:A7:C1:9E:D9:26` | `192.168.1.205` | `192.168.1.205` | Switching | Managed testbench switch |
| **Araknis 920 Switch** | `14:3F:C3:91:0F:8B` | `192.168.1.215` | `192.168.1.215` | Switching | RSTP root & core L2 switch |
| **Netgear GS108Ev2 Switch** | `84:1B:5E:98:F1:F4` | `192.168.1.220` | `192.168.1.220` | Switching | Office distribution switch |
| **OpenWrt Belkin (br-lan)** | `E8:9F:80:50:58:2F` | `192.168.1.226` | `192.168.1.226` | Routing | Primary bridge backhaul |
| **OpenWrt Belkin (wl1-sta0)** | `E8:9F:80:50:58:32` | `192.168.1.225` | `192.168.1.225` | Routing | Wi-Fi repeater failover |
| **Araknis 830-AP (House Front)**| `14:3F:C3:E8:B9:93` | `192.168.1.231` | `192.168.1.231` | Wi-Fi Access | Master AP |
| **Araknis 830-AP (House Back)** | `14:3F:C3:E8:B9:A2` | `192.168.1.236` | `192.168.1.236` | Wi-Fi Access | Secondary AP |
| **Araknis 830-AP (Office Bridge)**| `14:3F:C3:E8:B9:20` | `192.168.1.237` | `192.168.1.237` | Wi-Fi Access | Dedicated 5GHz PTP bridge |
| **pve2 (Awow Mini PC)** | `38:F7:CD:C1:67:E0` | `192.168.1.240` | `192.168.1.240` | Hypervisors | Proxmox Node 2 |
| **PBS Backup VM** | `BC:24:11:3E:06:69` | `192.168.1.244` | `192.168.1.244` | Infrastructure | Proxmox Backup Server |
| **pve3 (HP EliteDesk)** | `8C:DC:D4:3E:A7:D8` | `192.168.1.245` | `192.168.1.245` | Hypervisors | Proxmox Node 3 |
| **pve (Dell Precision 5520)** | `9C:EB:E8:96:11:44` | `192.168.1.250` | `192.168.1.250` | Hypervisors | Proxmox Node 1 |
| **pve-wireshark (DA200)** | `00:24:9B:55:A0:49` | `192.168.1.251` | `192.168.1.251` | Observability | Dedicated SPAN capture bridge |

---

### 5. VLAN 40 — Servers, DNS & Storage (`192.168.40.0/24`)
*Dynamic DHCP Pool: `192.168.40.20 – 192.168.40.99`*

| Device Name | MAC Address | Current IP | Proposed IP | Functional Tier | Notes & Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Araknis 520 Gateway** | — | `192.168.40.1` | `192.168.40.1` | Gateway | No change |
| **Virtual TAP Interface Host** | `02:F5:58:97:8E:88` | `192.168.40.155` | `192.168.40.155` | Testing | Virtual / container TAP interface |
| **Debian 12 Testing VM** | `BC:24:11:5B:43:43` | `192.168.40.165` | `192.168.40.165` | Testing VMs | No change |
| **Minecraft Docker VM (109)** | `BC:24:11:17:C9:60` | `192.168.40.175` | `192.168.40.175` | Docker VMs | No change |
| **Docker Dev & Testing VM** | `BC:24:11:17:B9:4F` | `192.168.40.176` | `192.168.40.176` | Docker VMs | No change |
| **nexus-server (pve VM 100)** | `BC:24:11:97:EB:DB` | `192.168.40.185` | `192.168.40.185` | Core Services | Primary DNS & NPM (no change) |
| **nexus-server2 (pve3 VM 100)**| `BC:24:11:BB:08:AD` | `192.168.40.186` | `192.168.40.186` | Core Services | Secondary DNS (no change) |
| **discovery-server (pve2 VM 100)**| `BC:24:11:EF:2D:13`| `192.168.40.246` | `192.168.40.246` | Storage / WAN2 | Also `10.25.25.246` |
| **media-server (pve VM 103)** | `BC:24:11:40:7F:72` | `192.168.40.247` | `192.168.40.247` | Media VM | Plex & QuickSync |
| **nas-server (pve3 VM 101)** | `BC:24:11:1A:56:46` | `192.168.40.248` | `192.168.40.248` | NAS VM | OpenMediaVault & `10.25.25.248` |
| **luna-server (pve VM 102)** | `BC:24:11:B7:CF:A3` | `192.168.40.249` | `192.168.40.249` | Smart Home VM | Home Assistant & SPAN sniffer |

---

### 6. VLAN 150 & VLAN 200 — Work Automation Lab / Testbenches
*Dynamic DHCP Pools: `192.168.150.20–.99` and `192.168.200.20–.99`*

| Device Name | MAC Address | Current IP | Proposed IP | Subnet / VLAN | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Araknis 520 Gateway** | — | `192.168.150.1` | `192.168.150.1` | VLAN 150 | No change |
| **ca1-000FFF51922F** | `00:0F:FF:51:92:2F` | `192.168.150.200` | `192.168.150.201` | VLAN 150 | Standardized into .200-.239 tier |
| **core3-000FFF0C347F** | `00:0F:FF:0C:34:7F` | `192.168.150.150` | `192.168.150.203` | VLAN 150 | Standardized into .200-.239 tier |
| **Araknis 520 Gateway** | — | `192.168.200.1` | `192.168.200.1` | VLAN 200 | No change |
| **Josh.ai System** | `F8:8A:3C:70:A3:DE` | `192.168.200.151` | `192.168.200.151` | VLAN 200 | Voice automation server (from OvrC) |
| **SA-1 (Ryff Test Controller)** | `00:0F:FF:0C:41:CA` | `192.168.200.100` | `192.168.200.201` | VLAN 200 | Standardized into .200-.239 tier |
| **ea3-000FFF928C21** | `00:0F:FF:92:8C:21` | `192.168.200.150` | `192.168.200.202` | VLAN 200 | Standardized into .200-.239 tier |
| **core5-000FFF0C33AE** | `00:0F:FF:0C:33:AE` | `192.168.200.200` | `192.168.200.205` | VLAN 200 | Standardized into .200-.239 tier |

---

## 🔒 ACL Firewall Rule Alignment (Araknis 520 Router)

### Rule 18: Sonos Return Control to Trusted LAN
- **Current Rule 18**:
  - Name: `Sonos to Trusted LAN`
  - Action: `Allow`
  - Source: `192.168.20.140 – 192.168.20.225` (86 addresses)
  - Destination: `192.168.10.1 – 192.168.10.254`
  - Service: `Any`
- **Hardened Proposed Rule 18**:
  - Name: `Sonos to Trusted LAN`
  - Action: `Allow`
  - Source: **`192.168.20.201 – 192.168.20.205`** (Clamped strictly to the 3 Sonos speakers + expansion room)
  - Destination: `192.168.10.1 – 192.168.10.254`
  - Service: `Any` (or TCP 3400, 3401, 3500, UDP 1900)

### Rules 7 & 8: Control4 Automation Access
- Because Control4 controllers and touchscreens are strictly bounded in **`192.168.10.200 – 192.168.10.208`**, any inter-VLAN control rules from touchscreens, mobile apps, or smart remotes can target this exact 9-address block instead of sprawling across unpredictable IPs.

---

## 🔄 Upstream Monitoring & Service Dependencies

When IP addresses are updated on the router, the following GitOps files and services must be synchronized:

### 1. Prometheus Scrape Configuration (`prometheus.yml`)
File: `infrastructure/docker-stacks/nexus-server/71-monitoring/prometheus/prometheus.yml`

```yaml
# Update lines 291 & 296 for Control4:
- targets:
  - http://192.168.10.200        # ca10-director (unchanged)
  labels:
    service: 'control4-ca10-director'
    category: 'control4'
- targets:
  - http://192.168.10.202        # core1 (changed from .10.35)
  labels:
    service: 'control4-core1'
    category: 'control4'
- targets:
  - http://192.168.10.203        # core3 (changed from .10.153)
  labels:
    service: 'control4-core3'
    category: 'control4'

# Update lines 313 & 318 for Printers:
- targets:
  - http://192.168.10.181/DevMgmt/ProductStatusDyn.xml  # hp-laserjet-web (changed from .10.195)
  labels:
    service: 'hp-laserjet-web'
    category: 'printer'
- targets:
  - http://192.168.10.182        # brother-printer-web (changed from .10.196)
  labels:
    service: 'brother-printer-web'
    category: 'printer'
```

### 2. Grafana Dashboards
- `infrastructure/docker-stacks/nexus-server/71-monitoring/grafana/dashboards/control4-smarthome-iot.json`:
  - Update instance filters matching `192.168.10.35` $ightarrow$ `192.168.10.202` and `192.168.10.153` $ightarrow$ `192.168.10.203`.

---

## 📋 Master Implementation Tracking Checklist

### Phase 0: Pre-Flight State Capture & Backups
*Ensure instant 100% rollback capability before modifying any configuration.*
- [x] **0.1. Export Live Araknis 520 Configuration**:
  - Run MCP tool `backup_araknis_router()` to save current encrypted binary blob to `infrastructure/network/configs/araknis-520-backup-pre-reorg.cfg`.
- [x] **0.2. Export Live Araknis 920 Running-Config**:
  - Run MCP tool `backup_araknis_switch()` to capture running configuration (`araknis-920-running-pre-reorg-20261004_171711.cfg`).
- [x] **0.3. Snapshot Current DHCP Reservations & ACLs**:
  - Dumped `/config/lan/dhcp-reservation`, `/config/lan/subnets`, and `/config/acls` to timestamped JSON files in `infrastructure/network/configs/`.

---

### Phase 1: Monitoring Suspension (Suppress Alert Storm)
*Prevent Prometheus and Alertmanager from firing false-positive alerts while devices renew leases.*
- [x] **1.1. Pause Prometheus Scrapes on Stack 71**:
  - Silenced Alertmanager for target group `category =~ "control4|printer|sonos"`. (Silences naturally expired post-reboot with 0 active alerts).

---

### Phase 2: Araknis 520 Router Reconfiguration
*Execute via REST API scripts (`manage-araknis-router.py`).*
- [x] **2.1. Update Dynamic DHCP Ranges to `.20–.99`**:
  - Updated `startIp` and `endIp` on LAN subnets for VLANs 1, 10, 20, 30, 40, 150, 200.
  - Verified gateway IP (`.1`) and subnet mask (`255.255.255.0`) remain intact.
- [x] **2.2. Push Reorganized DHCP Reservations JSON**:
  - Applied the updated complete reservation payload containing all 90 grouped devices (`dhcp-reservations-reorganized.json`).
- [x] **2.3. Confirm UPnP IGD Remains Disabled (`enableUPnP: false`)**:
  - Verified `/api/cgi-bin/v2/config/firewall` maintains `enableUPnP: false` to guarantee zero unauthenticated WAN port openings.
  - Verified `enableBonjour: true` remains active for native mDNS reflection across VLANs.
- [x] **2.4. Tighten ACL Rule 18**:
  - Updated Rule 18 source range to `192.168.20.201 - 192.168.20.205`.

---

### Phase 3: Araknis 920 Switch Multicast Router Configuration
*Execute via FASTPATH SSH engine (`manage-araknis-switch.py`).*
- [x] **3.1. Configure Static Multicast Router Interface on Trunk Port 1/0/1**:
  - Executed `set igmp mrouter 20` on Port 1/0/1. Confirmed Port 1/0/1 in both VLAN 10 and VLAN 20 mrouter tables.
- [x] **3.2. Persist Switch Configuration**:
  - Executed `write memory` / saved to NVRAM startup-config.
- [x] **3.3. Verify MRouter Port Presence**:
  - Verified `show igmpsnooping mrouter vlan 10` and `show igmpsnooping mrouter vlan 20` list Port `1/0/1` as active mrouter port.

---

### Phase 4: GitOps & Monitoring Updates
- [x] **4.1. Update `prometheus.yml` Targets**:
  - Applied new IPs for Control4 Core-1 (`.10.202`), Core-3 (`.10.203`), HP (`.10.181`), and Brother (`.10.182`).
- [x] **4.2. Update Grafana Dashboard Panels**:
  - Synchronized JSON dashboard definitions with new Prometheus instance labels.
- [x] **4.3. Commit Changes to GitOps Repository**:
  - Committed documentation, configuration JSONs, and Prometheus configs to Git (`commit 25b3520`, `5249763`).

---

### Phase 5: Client Lease Refresh & End-to-End Verification
- [x] **5.1. Refresh Sonos Speaker DHCP Leases**:
  - Network powercycle complete; Sonos Move 2 adopted `192.168.20.201` and `192.168.20.202`.
- [x] **5.2. Refresh Control4 Controller DHCP Leases**:
  - Control4 Core-5 adopted `192.168.10.204`, T5 Touchscreen adopted `192.168.10.201`.
- [x] **5.3. Refresh Network Printer DHCP Leases**:
  - HP LaserJet (`192.168.10.181`) and Brother Printer (`192.168.10.182`) adopted new IPs; verified printing and HTTP management active.
- [x] **5.4. Verify Sonos App Discovery from VLAN 10**:
  - Verified Spotify Connect and Sonos app discovery, playback, and volume control from Pixel 10 Pro on VLAN 10 (`192.168.10.110`) to Move 2 on VLAN 20 (`192.168.20.201` / `192.168.20.202`).
- [x] **5.5. Verify Packet Capture (Zero Dropped SSDP)**:
  - Ensured SSDP/mDNS traverses Port 1/0/1 and reverse UPnP event callbacks function seamlessly.

---

### Phase 6: Monitoring Resumption & Health Verification
- [x] **6.1. Resume Prometheus Scrapes**:
  - Updated `prometheus.yml` on `nexus-server` and restarted container.
- [x] **6.2. Verify Blackbox Probes**:
  - Confirmed all **60/60 Prometheus scrape targets are UP (100% healthy)**.
- [x] **6.3. Confirm Zero Alerting**:
  - Alertmanager clean with 0 active alerts for core infrastructure.

---

## 🛑 Rollback Runbook (Emergency Procedures)

If any unforeseen connectivity failure occurs during execution, execute the following steps in reverse order:

1. **Revert Switch MRouter**:
   - On 920 switch interface 1/0/1: `no set igmp mrouter interface`, `write memory`.
2. **Restore 520 Router Configuration**:
   - Run MCP tool `restore_araknis_router("infrastructure/network/configs/araknis-520-backup-pre-reorg.cfg")`.
   - The router will reload the pre-migration binary config blob within 45 seconds.
3. **Revert Prometheus Config**:
   - `git checkout HEAD -- infrastructure/docker-stacks/nexus-server/71-monitoring/prometheus/prometheus.yml`.
   - Restart Prometheus container.
