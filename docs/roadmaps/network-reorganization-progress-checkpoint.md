# 🏁 Homelab Network Remediation & DHCP Reorganization: Milestone Checkpoint

**Date**: 2026-10-04  
**Status**: Post-Powercycle Verification Complete (Tasks 001–011 Complete; Prometheus 60/60 UP; Sonos/Printers/RustDesk Verified)

---

## 📊 High-Level Task Status & Execution Summary

| Task ID | Description | Status | Verification & Target State |
| :--- | :--- | :---: | :--- |
| **`TASK_001`** | Pre-Flight Snapshots & Safety Blueprints | 🟢 **COMPLETED** | Saved `araknis-520-backup-pre-reorg.cfg`, `araknis-920-running-pre-reorg.cfg`, and timestamped JSON state files. |
| **`TASK_002`** | Monitoring Alert Silences | 🟢 **COMPLETED** | 2-hour active silences in Alertmanager for Control4, Sonos, and printers (now cleanly expired; 0 active alerts). |
| **`TASK_003`** | OvrC & WAN Ingress Dropping | 🟢 **COMPLETED** | Rules 35 & 36 added on Araknis 520 dropping WAN sweeps to `.150.200` & `.200.200`. OvrC Auto-Claim disabled. |
| **`TASK_004`** | Enterprise Subnet Tiering & DHCP | 🟢 **COMPLETED** | All 7 VLAN dynamic ranges updated to `.20–.99`; 90 static reservations applied to router NVRAM; 77 clients verified active. |
| **`TASK_005`** | Firewall Hardening & DNS Interception | 🟢 **COMPLETED** | Clamped Rule 18 down to `.20.201–.205`; Rules 33 & 34 block DoT; Port 53 DNAT active; UPnP disabled. |
| **`TASK_006`** | Switch Multicast Router & Storm Control | 🟢 **COMPLETED** | `set igmp mrouter 20` on Port 1/0/1; Storm control active (200 pps access, 500 pps trunk); `write memory` confirmed. |
| **`TASK_007`** | DNS Runaway Loop Remediation | 🟢 **COMPLETED** | AdGuard Home NXDOMAIN rule verified (`RCODE: 3`); container `adguardhome-sync` and NPM host 14 updated to `.40.185`/`.40.186`. |
| **`TASK_008`** | TCP PMTUD & Host MSS Clamping | 🟢 **COMPLETED** | TCPMSS clamped to 1380 on FORWARD and OUTPUT; saved to `/etc/iptables/rules.v4` on `nexus-server`. |
| **`TASK_009`** | GitOps Monitoring Targets Alignment | 🟢 **COMPLETED** | Prometheus targets and Grafana dashboards updated for Core-1/3 and printers (`commit 25b3520` & `commit 5249763`). |
| **`TASK_010`** | Device Lease Renewals & Functional Testing | 🟢 **COMPLETED** | Global powercycle complete; Sonos Move 2 discovery, playback & volume slider verified; HP & Brother printers verified; RustDesk relay verified. |
| **`TASK_011`** | Observability Resume & 60/60 Audit | 🟢 **COMPLETED** | Stack 71 updated and restarted on `nexus-server`; Prometheus reached **60/60 UP (100% healthy)**. |
| **`TASK_012`** | Post-Remediation PCAP Telemetry Delta | ⏳ **PENDING** | Capture analysis via `scripts/analyze_lan_pcap.py` to confirm non-unicast frame ratio < 5.0% and ARP rate < 20/s. |
| **`TASK_013`** | Final Aggregation & Operational Sign-off | ⏳ **PENDING** | Final delivery sign-off report. |

---

## 🔌 Recommended Powercycle Boot Sequence

1. **Araknis 520 Router**: Power on first; wait 2 minutes for WAN negotiation, LAN subnets, and DHCP reservations to initialize.
2. **Araknis 920 Switch & Netgear Switch**: Power on core switches; verify Port 1/0/1 link is up.
3. **Araknis 830 APs & Proxmox Hypervisors (`pve`, `pve2`, `pve3`)**: Boot APs and server hosts so core DNS and admin services become ready.
4. **End Devices, Smart Home & AV (Sonos, Control4, TVs, Printers)**: Power up end clients to adopt their clean `.20–.99` dynamic leases and reserved static IPs.
