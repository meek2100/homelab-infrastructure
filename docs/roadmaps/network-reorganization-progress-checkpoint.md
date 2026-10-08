# 🏁 Homelab Network Remediation & DHCP Reorganization: Milestone Checkpoint

**Date**: 2026-10-08 (Updated following live verification of WAN port-forward removal & DNS rewrites)  
**Status**: 🟢 Core Network Stabilized — WAN 53 Closed; DNS Rewrites Active (NXDOMAIN Confirmed); IP/MAC Reconciliation In Progress via `Home-Lan-Audit.xlsx`

---

## 📊 High-Level Task Status & Execution Summary

| Task ID | Description | Status | Verification & Target State |
| :--- | :--- | :---: | :--- |
| **`TASK_001`** | Pre-Flight Snapshots & Safety Blueprints | 🟢 **COMPLETED** | Saved `araknis-520-backup-pre-reorg.cfg`, `araknis-920-running-pre-reorg.cfg`, and timestamped JSON state files. |
| **`TASK_002`** | Monitoring Alert Silences | 🟢 **COMPLETED** | 2-hour active silences in Alertmanager for Control4, Sonos, and printers expired cleanly. Alert rules adjusted to `5m` duration to eliminate transient Wi-Fi alerts. |
| **`TASK_003`** | OvrC & WAN Ingress Dropping | 🟢 **COMPLETED** | Rules 35 & 36 added on Araknis 520 dropping WAN sweeps to `.150.200` & `.200.200`. OvrC 24-hr auto-claim/scan disabled on 2026-10-05 to eliminate ARP sweep noise. |
| **`TASK_004`** | Enterprise Subnet Tiering & DHCP | 🟡 **AUDIT IN PROGRESS** | All 7 VLAN dynamic ranges set to `.20–.99`. 90+ static reservations in router NVRAM. **Current step**: Final IP/MAC reconciliation against user's authoritative `Home-Lan-Audit.xlsx` before pushing to AdGuard Home. |
| **`TASK_005`** | Firewall Hardening & DNS Interception | 🟢 **VERIFIED RESOLVED** | Rule 18 clamped to `.20.201–.205`. Rules 33 & 34 block DoT. UPnP disabled. **VERIFIED 2026-10-08**: Queried live Araknis 520 `/config/port-forwarding` via API. The WAN UDP/TCP 53 forward was deleted by the user. Only WireGuard (UDP 51820) remains forwarded. Port 53 open resolver risk is closed. |
| **`TASK_006`** | Switch Multicast Router & Storm Control | 🟢 **REMEDIATED** | `set igmp mrouter 20` active on Port 1/0/1. **CORRECTED**: Port 1/0/1 storm control relaxed/removed (`no storm-control broadcast` staged in `araknis-920-running.cfg`) preventing router ARP drops. APs/CA-10 ports tuned to 1000 pps. |
| **`TASK_007`** | DNS Runaway Loop Remediation | 🟢 **VERIFIED RESOLVED** | AdGuard Home sync and NPM host 14 updated to `.40.185`/`.40.186`. **VERIFIED 2026-10-08**: User deployed native AdGuard DNS rewrite rules. Live query testing confirms:<br>• `stats.grafana.org` -> **NXDOMAIN (RCODE 3)**<br>• `stats.grafana.org.internal` -> **NXDOMAIN (RCODE 3)**<br>• `geo.hivebedrock.cloud` -> CNAME `minecraftconnect.secure.theurer.dev` -> `192.168.40.175`<br>Both primary (`.40.185`) and secondary (`.40.186`) DNS resolvers return clean RCODE 3, stopping the 44k/day loop. |
| **`TASK_008`** | TCP PMTUD & Host MSS Clamping | ⚪ **RE-EVALUATED / UNNECESSARY** | Forensic review showed 0/85,111 nexus SYNs carrying MSS 1380 (all 1460). Only 12 ICMP frag-needed packets observed across 8 hours (none for nexus TCP). Clamping is not active and not needed. |
| **`TASK_009`** | GitOps Monitoring Targets Alignment | 🟢 **COMPLETED** | Prometheus targets and Grafana dashboards updated for Core-1/3 and network printers (`commit 25b3520` & `commit 5249763`). |
| **`TASK_010`** | Device Lease Renewals & Functional Testing | 🟢 **COMPLETED** | Sonos Move 2 & Roam 2 inter-VLAN discovery (SSDP/mDNS), playback, and volume control verified from VLAN 10. Vivint panel SDDP active on Port 1902. Google TV remote / cast multicast operational without packet drops. |
| **`TASK_011`** | Observability Resume & 60/60 Audit | 🟢 **COMPLETED** | Stack 71 updated and healthy on `nexus-server`; Prometheus at 60/60 UP (100% healthy); Alertmanager probe alerts resolved. |
| **`TASK_012`** | Post-Remediation PCAP Telemetry Delta | 🟢 **COMPLETED** | Telemetry engine executed across capture archives (`router_baseline_*.pcapng`). Confirmed: ICMP MTU drops = 0; STP TCNs = 0; legacy printer & controller ARPs eradicated; headless capture engine streaming ~48MB chunks reliably to `/mnt/n/wireshark-captures`. |
| **`TASK_013`** | Final Aggregation & Operational Sign-off | ⏸️ **PAUSED** | Awaiting completion of the IP/MAC table verification from user's `Home-Lan-Audit.xlsx`. Once synchronized across router, switches, OvrC, and AdGuard Home, Part 8 can officially begin. |

---

## 🔌 Recommended Powercycle Boot Sequence

1. **Araknis 520 Router**: Power on first; wait 2 minutes for WAN negotiation, LAN subnets, and DHCP reservations to initialize.
2. **Araknis 920 Switch & Netgear Switch**: Power on core switches; verify Port 1/0/1 link is up.
3. **Araknis 830 APs & Proxmox Hypervisors (`pve`, `pve2`, `pve3`)**: Boot APs and server hosts so core DNS and admin services become ready.
4. **End Devices, Smart Home & AV (Sonos, Control4, TVs, Printers)**: Power up end clients to adopt their clean `.20–.99` dynamic leases and reserved static IPs.

---

## 🔬 Next Milestone Actions Prior to Part 8

1. **Authoritative IP/MAC Synchronization (`TASK_004` & `TASK_013`)**:
   - Complete verification of `Home-Lan-Audit.xlsx`.
   - Update `dhcp-reservations-reorganized.json` and sync to AdGuard Home persistent clients via `sync-adguard-clients.py`.
   - Verify alignment across router, switches, OvrC, and AdGuard Home.
2. **Proceed to Part 8 (Compute Platform Review & Resource Optimization)**.
