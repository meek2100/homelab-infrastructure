# 🏁 Homelab Network Remediation & DHCP Reorganization: Milestone Checkpoint

**Date**: 2026-10-10 (Updated following complete IP/MAC audit, VLAN 20 trunk remediation, and full fleet synchronization)  
**Status**: 🟢 Core Network & Fleet 100% Stabilized & Synchronized — Ready for Part 8

---

## 📊 High-Level Task Status & Execution Summary

| Task ID | Description | Status | Verification & Target State |
| :--- | :--- | :---: | :--- |
| **`TASK_001`** | Pre-Flight Snapshots & Safety Blueprints | 🟢 **COMPLETED** | Saved `araknis-520-backup-pre-reorg.cfg`, `araknis-920-running-pre-reorg.cfg`, and timestamped JSON state files. |
| **`TASK_002`** | Monitoring Alert Silences | 🟢 **COMPLETED** | 2-hour active silences in Alertmanager for Control4, Sonos, and printers expired cleanly. Alert rules adjusted to `5m` duration to eliminate transient Wi-Fi alerts. |
| **`TASK_003`** | OvrC & WAN Ingress Dropping | 🟢 **COMPLETED** | Rules 35 & 36 added on Araknis 520 dropping WAN sweeps to `.150.200` & `.200.200`. OvrC 24-hr auto-claim/scan disabled on 2026-10-05 to eliminate ARP sweep noise. |
| **`TASK_004`** | Enterprise Subnet Tiering & DHCP | 🟢 **COMPLETED** | All 7 VLAN dynamic ranges set to `.20–.99`. **106 authoritative reservations** reconciled from `.agents/lan-audit.csv` into `dhcp-reservations-reorganized.json` and `canonical-lan-fleet.json`. Deployed live to Araknis 520 router NVRAM via API with HTTP 200 OK. |
| **`TASK_005`** | Firewall Hardening & DNS Interception | 🟢 **VERIFIED RESOLVED** | Rule 18 clamped to `.20.201–.205`. Rules 33 & 34 block DoT. UPnP disabled. **VERIFIED 2026-10-08**: Queried live Araknis 520 `/config/port-forwarding` via API. The WAN UDP/TCP 53 forward was deleted by the user. Only WireGuard (UDP 51820) remains forwarded. Port 53 open resolver risk is closed. |
| **`TASK_006`** | Switch Multicast Router & Storm Control | 🟢 **COMPLETED** | `set igmp mrouter 20` active on Port 1/0/1. **RESOLVED 2026-10-08**: Broadcast storm control disabled globally on Araknis 920 switch (`no storm-control broadcast` saved to `startup-config`). Eliminated AP frame drops (~50k dropped packets), immediately restoring Pixel 10 Wi-Fi speed and instant Control4 local app connectivity. |
| **`TASK_007`** | DNS Runaway Loop Remediation | 🟢 **VERIFIED RESOLVED** | AdGuard Home sync and NPM host 14 updated to `.40.185`/`.40.186`. **VERIFIED 2026-10-08**: User deployed native AdGuard DNS rewrite rules. Live query testing confirms:<br>• `stats.grafana.org` -> **NXDOMAIN (RCODE 3)**<br>• `stats.grafana.org.internal` -> **NXDOMAIN (RCODE 3)**<br>• `geo.hivebedrock.cloud` -> CNAME `minecraftconnect.secure.theurer.dev` -> `192.168.40.175`<br>Both primary (`.40.185`) and secondary (`.40.186`) DNS resolvers return clean RCODE 3, stopping the 44k/day loop. |
| **`TASK_008`** | TCP PMTUD & Host MSS Clamping | ⚪ **RE-EVALUATED / UNNECESSARY** | Forensic review showed 0/85,111 nexus SYNs carrying MSS 1380 (all 1460). Only 12 ICMP frag-needed packets observed across 8 hours (none for nexus TCP). Clamping is not active and not needed. |
| **`TASK_009`** | GitOps Monitoring Targets Alignment | 🟢 **COMPLETED** | Prometheus targets and Grafana dashboards updated for Core-1/3 and network printers (`commit 25b3520` & `commit 5249763`). |
| **`TASK_010`** | Device Lease Renewals & Functional Testing | 🟢 **COMPLETED** | Sonos Move 2 & Roam 2 inter-VLAN discovery (SSDP/mDNS), playback, and volume control verified from VLAN 10. Vivint panel SDDP active on Port 1902. Google TV remote / cast multicast operational without packet drops. **RESOLVED 2026-10-10**: Fixed missing VLAN 20 trunking on SW920 Port 1/0/2 and PVE Node 1 `lan0`; wired Apple TV on Netgear Port 3 immediately received its VLAN 20 lease (`192.168.20.160`). |
| **`TASK_011`** | Observability Resume & 60/60 Audit | 🟢 **COMPLETED** | Stack 71 updated and healthy on `nexus-server`; Prometheus at 60/60 UP (100% healthy); Alertmanager probe alerts resolved. |
| **`TASK_012`** | Post-Remediation PCAP Telemetry Delta | 🟢 **COMPLETED** | Telemetry engine executed across capture archives (`router_baseline_*.pcapng`). Confirmed: ICMP MTU drops = 0; STP TCNs = 0; legacy printer & controller ARPs eradicated; headless capture engine streaming ~48MB chunks reliably to `/mnt/n/wireshark-captures`. |
| **`TASK_013`** | Final Fleet Aggregation & Operational Sign-off | 🟢 **COMPLETED** | Authoritative IP/MAC synchronization complete: 106 DHCP reservations active in router NVRAM; 104 persistent clients with tag taxonomy synced to AdGuard Home; 32 device names/rooms aligned in live Snap One OvrC Cloud via FastMCP tools; Araknis 920 & 520 configs saved and backed up to GitOps. |

---

## 🔌 Recommended Powercycle Boot Sequence

1. **Araknis 520 Router**: Power on first; wait 2 minutes for WAN negotiation, LAN subnets, and DHCP reservations to initialize.
2. **Araknis 920 Switch & Netgear Switch**: Power on core switches; verify Port 1/0/1 link is up.
3. **Araknis 830 APs & Proxmox Hypervisors (`pve`, `pve2`, `pve3`)**: Boot APs and server hosts so core DNS and admin services become ready.
4. **End Devices, Smart Home & AV (Sonos, Control4, TVs, Printers)**: Power up end clients to adopt their clean `.20–.99` dynamic leases and reserved static IPs.

---

## 🔬 Next Steps: Proceeding to Part 8

1. **Part 8: Compute Platform Review & Resource Optimization**
   - Review hypervisor workloads across `pve` (Precision 5520), `pve2` (Awow), and `pve3` (HP EliteDesk).
   - Audit CPU/RAM allocation, VM disk sizing, storage pools, and power profiles.
   - Verify Proxmox Backup Server (PBS) automation schedules and deduplication metrics.
