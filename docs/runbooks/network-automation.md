# 🛠️ Homelab Network Automation & Netgear NSDP Script Runbook

This runbook contains single-click copy/paste commands for managing the Netgear GS108Ev2 switch and the Wireshark headless SPAN capture daemon.

---

## 📂 Quick Script Reference Matrix

| Script Path | Purpose | Execution Host | Network Context |
| :--- | :--- | :---: | :---: |
| [`mcp/homelab/scripts/probe-netgear-l2.sh`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/probe-netgear-l2.sh) | Direct NSDP discovery & telemetry probe via L2 relay | `personal-ai` | Relays via OpenWrt or PVE on VLAN 1 |
| [`mcp/homelab/scripts/inspect-nsdp-live.sh`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/inspect-nsdp-live.sh) | Parse live NSDP frames recorded from Windows ProSAFE in Wireshark tmpfs | `personal-ai` | Queries VM 102 via `pve` |
| [`mcp/homelab/scripts/manage-netgear-switch.py`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/manage-netgear-switch.py) | Full switch status, port link matrix, CRC error stats, and JSON backup export | `personal-ai` / `pve` | Native / L2 SSH Relay |
| [`mcp/homelab/scripts/get-wireshark-status.py`](file:///home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/get-wireshark-status.py) | Inspect ens19 SPAN counters, Wireshark container, and NAS archive | `personal-ai` | Queries VM 102 via `pve` |

---

## 🚀 Execution Runbook

### 1. Probe Netgear Switch via OpenWrt Router (Direct Office Desk L2 Hop)
Sends an authentic NSDP Read Request to `192.168.1.220` using Belkin AX3200 OpenWrt (`192.168.1.226` on `br-lan`) as the Layer 2 adjacent relay.

```bash
./mcp/homelab/scripts/probe-netgear-l2.sh 192.168.1.220 192.168.1.226
```

---

### 2. Probe Netgear Switch via Proxmox PVE (Hypervisor L2 Hop)
Sends an authentic NSDP Read Request to `192.168.1.220` using Proxmox `pve` (`192.168.1.250` on `vmbr0`) as the Layer 2 adjacent relay.

```bash
./mcp/homelab/scripts/probe-netgear-l2.sh 192.168.1.220 192.168.1.250
```

---

### 3. Query Live Switch Status & Full Port Diagnostics
Queries port link states, negotiated speeds, duplex, byte counters, and CRC error statistics using SOPS-encrypted credentials.

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py status
```

*(For raw JSON output:)*
```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py status --json
```

---

### 4. Export Netgear Configuration Backup (GitOps)
Pulls system info, ports, statistics, PVIDs, and VLAN settings via NSDP, synchronizing both:
- Structured telemetry snapshot: `infrastructure/network/configs/netgear-gs108e-backup.json`
- Authentic binary configuration: `infrastructure/network/configs/netgear-gs108e-backup.cfg` (matching official ProSAFE Plus backup format)

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py backup
```

---

### 5. Inspect Live Captured ProSAFE Frames from Wireshark
Parses the active in-memory pcapng file inside the `wireshark` container on `luna-server` (VM 102), showing Manager MAC, Switch MAC, Opcode, Sequence, and TLV registers recorded from your Windows ProSAFE session.

```bash
./mcp/homelab/scripts/inspect-nsdp-live.sh
```

---

### 6. Wireshark Sniffer Live Status (Stack 48)
Queries `luna-server` (VM 102) to inspect the SPAN capture interface (`ens19`), container state, and recent archive files on the NAS.

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py status
```

---

### 7. Provision 802.1Q VLAN & Assign Port PVIDs
Atomically configures 802.1Q VLAN membership (Tagged `T`, Untagged `U`) and assigns Port VLAN IDs.
*Port 8 (uplink) is automatically protected against management lockout.*

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py set-vlan --vid 10 --tagged 8 --untagged 1,2 --pvid 1,2
```

*(Example for IoT VLAN 30 on ports 3 and 4 with trunk uplink on port 8:)*
```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py set-vlan --vid 30 --tagged 8 --untagged 3,4 --pvid 3,4
```

---

### 8. Delete an 802.1Q VLAN
Deletes a secondary VLAN and reverts any ports assigned to it back to PVID 1. *(VLAN 1 is protected and cannot be deleted.)*

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py delete-vlan --vid 10
```

---

### 9. Configure Port Default VLAN ID (PVID)
Updates the ingress untagged VLAN classification (PVID) for a specific physical port.

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py set-pvid --port 2 --pvid 10
```

---

### 10. Configure Port Administrative State & Speed
Enables or disables a physical port, or locks speed and duplex negotiation (`auto`, `10h`, `10f`, `100h`, `100f`, `1000f`).
*Port 8 (uplink) cannot be disabled without `--force-uplink`.*

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py set-port --port 2 --admin disable
```

*(To re-enable and set to Auto-negotiation:)*
```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py set-port --port 2 --admin enable --speed auto
```

---

### 11. Configure Hardware Features (IGMP & Loop Detection)
Enables or disables hardware IGMP snooping (`0x2000`) and loop detection (`0x9000`).

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py set-feature --igmp enable --loop-detection enable
```

---

### 12. Verify Live Switch State Against GitOps Baseline
Performs an audit comparing live switch hardware state against `infrastructure/network/configs/netgear-gs108e-backup.json` to detect any configuration drift.

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py verify
```

---

### 13. Restore Configuration from Backup
Restores the Netgear switch configuration directly from the official ProSAFE `.cfg` binary backup or JSON snapshot.

```bash
python3 mcp/homelab/scripts/manage-netgear-switch.py restore --file infrastructure/network/configs/netgear-gs108e-backup.cfg --confirm
```

---

## 🏛️ Ground-Truth Technical Reference

### Netgear GS108Ev2 Hardware & Protocol Invariants
- **Firmware**: `1.00.12`
- **Management Interface**: Headless. **No HTTP/HTTPS web daemon, no SSH, no Telnet, no SNMP.**
- **Protocol**: **NSDP (Netgear Switch Discovery Protocol)** over UDP.
- **Port Mapping**: Client source port **63321** <-> Switch destination port **63322**.
- **Switch MAC**: `84:1b:5e:98:f1:f4` (Captured from live Wireshark session).
- **Manager MAC**: Physical MAC of the managing computer interface on VLAN 1.
- **Layer 2 Requirement**: NSDP frames use local MAC broadcast and unicast within `192.168.1.0/24` (VLAN 1). Switches discard packets if the manager IP is not in the same subnet (`UAPI_LoginSwitch: can not login current switch, the manager and switch IP are not in the same subnet`).
- **32-Byte Header Framing**:
  - `0x01` (Version 1)
  - `0x01` (Read Request) / `0x02` (Read Response) / `0x03` (Write Request) / `0x04` (Write Response)
  - `0x0000` (Result Code OK)
  - `0x00000000` (Reserved)
  - Bytes 8-13: Manager MAC (NIC MAC of host)
  - Bytes 14-19: Switch MAC (`84:1b:5e:98:f1:f4`)
  - `0x0000` (Alignment)
  - `0x0001` (Sequence Counter)
  - `NSDP` (`0x4E534450` Signature)
  - Trailing null padding
- **Authentication**: XOR cipher with static key `NtgrSmartSwitchRock` stored in TLV `0x000A`. Login uses Opcode `0x03` (Write Request).
- **End-of-Message Delimiter**: Mandatory trailing 4 bytes: `0xFFFF0000`.

### Key Register Space (TLVs)
| TLV Tag | Description | Size / Format |
| :---: | :--- | :--- |
| `0x0001` | Switch Model Name | ASCII string (`GS108Ev2`) |
| `0x0003` | Host / Device Name | ASCII string |
| `0x0004` | Switch MAC Address | 6 bytes binary (`84:1b:5e:98:f1:f4`) |
| `0x0006` | IPv4 Address | 4 bytes binary (`192.168.1.220`) |
| `0x0007` | Subnet Netmask | 4 bytes binary (`255.255.255.0`) |
| `0x0008` | Default Gateway | 4 bytes binary (`192.168.1.1`) |
| `0x000A` | Authentication Password | XOR cipher payload (`NtgrSmartSwitchRock`) |
| `0x000D` | Firmware Bank 1 Version | ASCII string (`1.00.12`) |
| `0x000E` | Firmware Bank 2 Version | ASCII string |
| `0x0014` | Auth Session Challenge | 4 bytes binary (`0x00000001`) |
| `0x0C00` | Port Link & Speed Matrix | 3 bytes per port in v2 (Port ID, Speed Code, Duplex Status) |
| `0x1000` | Port Statistics Counters | 49 bytes per port in v2 (`>BQQQQQQ`: Port ID, Rx/Tx Octets, Packets, CRC, Drops) |
| `0x6000` | Physical Port Count | 1 byte binary (`0x08` = 8 ports) |
| `0x7400` | Capability Feature Mask | 8 bytes binary (`0x000000087ffcffff`) |
| `0x7800` | System Status & Serial | 21 bytes binary payload |
| `0x2800` | 802.1Q VLAN Memberships | Dynamic membership table |
| `0x2900` | Port Default PVID Assignment | 16 bytes (2 bytes per port * 8 ports) |
