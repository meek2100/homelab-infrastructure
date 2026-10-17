# 📡 Enterprise PCAP Network Telemetry & Diagnostic Report
**Files Analyzed**: `31 capture(s)` | **Total Packets**: `3,000,000` | **Data Volume**: `472.87 MB` | **Span**: `5.45h` (`152.86 pkts/s`)

## 📊 Executive Health Scorecard
- **Non-Unicast L2 Frame Ratio**: **`9.86%`** ✅ *(Healthy)*
- **Router ARP Requests**: `76,779` (Gratuitous: `105`)
- **STP / RSTP Topology Flapping**: **`0 TCNs`** (`1,974 BPDUs`) ✅ *(Stable)*
- **Rogue DHCP Detection**: **`8 servers observed`** (`192.168.30.1, 192.168.10.1, 192.168.175.1, 192.168.20.1, 192.168.200.1, 192.168.1.1, 192.168.40.1, 192.168.150.1`) ✅ *(Verified)*

## 🏷️ Layer 2 Framing, ARP & Spanning Tree Health
- **Unicast Frames**: `2,704,109` | **Broadcast**: `60,478` | **Multicast**: `235,413`
### Top ARP Queriers:
  - `192.168.10.1` (VLAN 10 (Main Trusted)): **`19,476` requests**
  - `192.168.20.1` (VLAN 20 (Guest Media)): **`16,760` requests**
  - `192.168.1.1` (VLAN 1 (Mgmt)): **`11,320` requests**
  - `192.168.10.200` (VLAN 10 (Main Trusted)): **`9,252` requests**
  - `192.168.30.1` (VLAN 30 (Isolated IoT)): **`8,801` requests**
  - `192.168.40.1` (VLAN 40 (Servers Admin)): **`4,794` requests**
  - `192.168.200.1` (VLAN 200 (Core-5 Test)): **`1,301` requests**
  - `192.168.175.1` (VLAN 175 (Ryff Test)): **`970` requests**
### Top Unanswered or Targeted ARP IPs:
  - `192.168.10.206`: `2,770` queries
  - `192.168.10.207`: `2,734` queries
  - `192.168.10.160`: `2,279` queries
  - `192.168.10.205`: `2,118` queries
  - `192.168.10.204`: `2,047` queries
  - `192.168.1.205`: `1,355` queries
  - `192.168.20.202`: `996` queries
  - `192.168.20.201`: `995` queries
### 🚨 Multi-MAC IP Detection (Flapping / BSSID / Probes):
  - `192.168.1.237` claimed by MACs: `36:3f:c3:e8:b9:23, 14:3f:c3:e8:b9:20`
  - `0.0.0.0` claimed by MACs: `00:0f:ff:0b:31:af, d4:6a:91:9c:00:69, d4:6a:91:9c:00:67, 7c:1e:b3:f0:26:55, d4:6a:91:9c:00:8a, 00:0f:ff:51:92:2f`

## 🛣️ 802.1Q VLAN Matrix & Routing Flows
| VLAN ID | Packets | Volume (MB) | Share % | Security Zone |
| :--- | :--- | :--- | :--- | :--- |
| **VLAN 1 (Untagged)** | `1,661,861` | `198.05` | `55.4%` | Verified |
| **VLAN 40** | `572,985` | `138.11` | `19.1%` | Verified |
| **VLAN 10** | `404,075` | `72.53` | `13.47%` | Verified |
| **VLAN 20** | `200,618` | `35.54` | `6.69%` | Verified |
| **VLAN 30** | `66,499` | `12.94` | `2.22%` | Verified |
| **VLAN 175** | `51,329` | `8.29` | `1.71%` | Verified |
| **VLAN 200** | `21,952` | `3.77` | `0.73%` | Verified |
| **VLAN 150** | `20,681` | `3.65` | `0.69%` | Verified |

### Top Inter-Subnet / Routed Flows:
- `VLAN 1 (Mgmt)` ➔ `VLAN 40 (Servers Admin)`: **`107.63 MB`**
- `Public WAN` ➔ `VLAN 1 (Mgmt)`: **`97.26 MB`**
- `VLAN 40 (Servers Admin)` ➔ `VLAN 1 (Mgmt)`: **`38.54 MB`**
- `VLAN 20 (Guest Media)` ➔ `VLAN 10 (Main Trusted)`: **`24.73 MB`**
- `VLAN 1 (Mgmt)` ➔ `Public WAN`: **`23.39 MB`**
- `VLAN 40 (Servers Admin)` ➔ `Public WAN`: **`18.27 MB`**
- `Public WAN` ➔ `VLAN 40 (Servers Admin)`: **`18.03 MB`**
- `VLAN 10 (Main Trusted)` ➔ `VLAN 40 (Servers Admin)`: **`15.98 MB`**
- `Public WAN` ➔ `VLAN 10 (Main Trusted)`: **`12.73 MB`**
- `VLAN 40 (Servers Admin)` ➔ `VLAN 10 (Main Trusted)`: **`12.31 MB`**
- `VLAN 10 (Main Trusted)` ➔ `Public WAN`: **`11.76 MB`**
- `VLAN 10 (Main Trusted)` ➔ `VLAN 20 (Guest Media)`: **`11.12 MB`**
- `VLAN 30 (Isolated IoT)` ➔ `VLAN 40 (Servers Admin)`: **`10.83 MB`**
- `VLAN 10 (Main Trusted)` ➔ `Multicast/Broadcast`: **`6.53 MB`**
- `VLAN 20 (Guest Media)` ➔ `Multicast/Broadcast`: **`4.79 MB`**

## ⚡ Transport Health & TCP Link Stability
- **TCP Handshakes**: SYN `30,426` | SYN-ACK `21,946` | FIN `42,743`
- **TCP Connection Resets (RST)**: **`18,254`** (RST:SYN Ratio: `0.6`)
### Top TCP RST Sources:
  - `192.168.40.185` (VLAN 40 (Servers Admin)): `12,550` resets
  - `146.235.203.133` (Public WAN): `1,324` resets
  - `35.212.229.212` (Public WAN): `1,182` resets
  - `192.168.1.215` (VLAN 1 (Mgmt)): `528` resets
  - `192.168.10.110` (VLAN 10 (Main Trusted)): `267` resets
  - `192.168.10.103` (VLAN 10 (Main Trusted)): `266` resets
  - `192.168.175.201` (VLAN 175 (Ryff Test)): `215` resets
  - `192.168.10.95` (VLAN 10 (Main Trusted)): `204` resets
### ICMP Diagnostic Telemetry:
  - **Echo Request**: `9,154` frames
  - **Port Unreachable**: `4,058` frames
  - **Echo Reply**: `3,976` frames
  - **Host Unreachable**: `272` frames
  - **TTL Expired**: `16` frames
  - **3/4**: `4` frames

## 🔍 Core Services: DNS & DHCP Auditing
### Contacted DNS Resolvers:
  - `192.168.40.185` (VLAN 40 (Servers Admin)): `16,885` queries
  - `1.1.1.1` (Public WAN): `3,347` queries
  - `8.8.8.8` (Public WAN): `2,801` queries
  - `192.168.40.186` (VLAN 40 (Servers Admin)): `2,452` queries
  - `192.168.1.1` (VLAN 1 (Mgmt)): `2,139` queries
  - `94.140.14.140` (Public WAN): `1,215` queries
  - `9.9.9.9` (Public WAN): `1,214` queries
  - `1.0.0.1` (Public WAN): `327` queries
### ⚠️ External DNS Leakers (Bypassing AdGuard Home):
  - Client `192.168.1.236` ➔ Resolver `1.1.1.1`: **`1,730` queries**
  - Client `192.168.1.236` ➔ Resolver `8.8.8.8`: **`1,711` queries**
  - Client `192.168.40.185` ➔ Resolver `1.1.1.1`: **`750` queries**
  - Client `192.168.40.185` ➔ Resolver `9.9.9.9`: **`714` queries**
  - Client `192.168.40.185` ➔ Resolver `94.140.14.140`: **`714` queries**
  - Client `192.168.40.186` ➔ Resolver `94.140.14.140`: **`501` queries**
  - Client `192.168.40.186` ➔ Resolver `1.1.1.1`: **`501` queries**
  - Client `192.168.40.186` ➔ Resolver `9.9.9.9`: **`500` queries**
### Top Queried Domains:
  - `stats.grafana.org`: `7,872` queries
  - `stats.grafana.org.internal`: `7,872` queries
  - `www.google.com`: `6,493` queries
  - `cloudflare-dns.com`: `3,644` queries
  - `name_query`: `1,512` queries
  - `otlp.nr-data.net`: `1,488` queries
  - `name_query.internal`: `1,484` queries
  - `cloud.ovrc.com`: `1,040` queries

## 🔒 Security & Protocol Hygiene
### Insecure Cleartext Protocols:
  - **HTTP**: `49,377` frames
### Top Public WAN Egress Destinations:
  - `54.68.202.150`: `95,727` packets
  - `185.199.108.154`: `49,798` packets
  - `172.217.112.4`: `11,298` packets
  - `172.217.118.4`: `10,535` packets
  - `172.217.116.4`: `10,308` packets
  - `35.212.229.212`: `8,658` packets
