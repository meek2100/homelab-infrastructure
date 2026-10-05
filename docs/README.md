# 📚 Homelab Infrastructure Documentation Library

This directory serves as the centralized, authoritative documentation library for all physical hosts, virtual machines, networking hardware, and automated GitOps tooling across the homelab infrastructure.

---

## 📂 Documentation Catalog

```text
docs/
├── README.md                                    # Master Table of Contents & Navigation Index
│
├── architecture/                                # Core System & Network Topologies
│   ├── network-topology.md                      # Dual-WAN, Araknis router/switch/APs, hypervisor bridges, split-horizon DNS
│   ├── vlan-matrix.md                           # Master 8-VLAN table, subnet CIDRs, DHCP pools, 36 live interzone ACL rules
│   └── network-interfaces-map.md                # Empirical OS interfaces, bridges (vmbr0/1), and routing tables (Hosts, VMs, LXC 105)
│
├── runbooks/                                    # Operational Runbooks & Disaster Recovery Playbooks
│   ├── network-automation.md                    # Headless Netgear NSDP commands (via OpenWrt L2 relay) & live Wireshark sniffer ops
│   ├── proxmox-backup-server.md                 # PBS deployment (LXC 105), 10.25.25.0/24 SAN transport, CBT incremental backups
│   ├── recovery-walkthrough.md                  # Bare-metal host and VM restoration sequencing via homelab MCP tools
│   ├── security-backup-guide.md                 # SOPS + age encryption standards, key management, and secrets hygiene
│   ├── gitops-drills-and-secret-rotation.md     # GitOps disaster recovery drills, state diff verification, and SOPS key rotation
│   └── vivint-panel-mdns-acl.md                 # Vivint Smart Home panel cross-VLAN mDNS reflection & firewall rules
│
├── specifications/                              # Hardware Protocols & Technical Specs
│   └── netgear-gs108ev2-nsdp.md                 # 715-line headless NSDP protocol specification, framing, and pure-Python driver
│
└── roadmaps/                                    # Engineering Roadmaps, Checkpoints & Forensic Audits
    ├── network-implementation-plan.md           # Multi-phase network audit milestones, status matrix, and verification logs
    ├── network-reorganization-progress-checkpoint.md # Execution checkpoint for VLAN re-alignment and IP renumbering
    ├── network-dhcp-ip-reorganization-plan.md   # Master IP reservation plan (pools .20–.99 across 7 VLANs)
    ├── lan-hygiene-pcap-remediation-plan.md     # Broadcast storm mitigation, mDNS isolation, and ARP hygiene
    └── capture-review-2026-10-05.md             # Forensic PCAP deep-dive, open resolver remediation, and CA-10 metrics loop
```

---

## 📑 Section Overview

### 🏛️ 1. Architecture
Authoritative ground-truth definitions for physical and logical topology:
* [network-topology.md](architecture/network-topology.md): Physical hardware layout, Araknis 520 router, Araknis 920 switch, Araknis 830 Wi-Fi 7 APs, office wireless bridge, dual-WAN routing, and split-horizon DNS.
* [vlan-matrix.md](architecture/vlan-matrix.md): Master 8-VLAN segmentation matrix (VLANs 1, 10, 20, 30, 40, 100, 150, 200), CIDR allocations, DHCP scope options, and 36 live inter-VLAN firewall ACL rules.
* [network-interfaces-map.md](architecture/network-interfaces-map.md): Empirical operating system audit of all network interfaces, bridges (`vmbr0`, `vmbr1`), MAC addresses, and routing tables across Proxmox hosts, virtual machines, and LXC 105.

### 🛠️ 2. Runbooks
Step-by-step operational and disaster-recovery execution guides:
* [network-automation.md](runbooks/network-automation.md): Single-click runnable commands for headless Netgear GS108Ev2 switch management via Layer 2 NSDP relays (OpenWrt `192.168.1.226` / PVE `192.168.1.250`) and live Wireshark SPAN sniffer diagnostics.
* [proxmox-backup-server.md](runbooks/proxmox-backup-server.md): Proxmox Backup Server (LXC 105 on `pve3`) architecture, fast `10.25.25.244` SAN transport, CBT incremental backups, and verification drills.
* [recovery-walkthrough.md](runbooks/recovery-walkthrough.md): End-to-end bare-metal recovery sequence detailing the 4 phases: Host bootstrapping, host config restoration, VM bootstrapping, and Docker stack ignition via FastMCP tools.
* [security-backup-guide.md](runbooks/security-backup-guide.md): Standard operating procedures for encrypting secrets with SOPS + age, managing master keys, and ensuring zero unencrypted credentials enter Git.
* [gitops-drills-and-secret-rotation.md](runbooks/gitops-drills-and-secret-rotation.md): Verification drills, staging dry-runs, and procedure for rotating SOPS encryption keys across all 50 encrypted stack files.
* [vivint-panel-mdns-acl.md](runbooks/vivint-panel-mdns-acl.md): Step-by-step firewall and mDNS gateway rules for isolating Vivint Smart Home panels into VLAN 150 while enabling local app control.

### 🔬 3. Hardware Specifications
Low-level protocol specifications, register maps, and hardware reverse engineering:
* [netgear-gs108ev2-nsdp.md](specifications/netgear-gs108ev2-nsdp.md): Complete technical specification of the Netgear Switch Discovery Protocol (NSDP) for headless switches, covering UDP 63321/63322 transport dynamics, 32-byte header framing, TLV registers, SPI NOR flash persistence risks, and native Python driver implementation.

### 🗺️ 4. Roadmaps & Forensic Reviews
Project tracking, execution checkpoints, and deep-packet inspection audits:
* [network-implementation-plan.md](roadmaps/network-implementation-plan.md): Comprehensive implementation plan tracking Phases 1, 2, and 3 across network segmentation, Araknis hardware, Netgear GitOps, Wireshark SPAN sniffer, and observability stacks.
* [network-reorganization-progress-checkpoint.md](roadmaps/network-reorganization-progress-checkpoint.md): Checkpoint tracking task execution for VLAN migration, IP renumbering, and router ACL deployment.
* [network-dhcp-ip-reorganization-plan.md](roadmaps/network-dhcp-ip-reorganization-plan.md): Specification for static DHCP reservations, dynamic pool bounds (.20–.99), and DNS hostnames.
* [lan-hygiene-pcap-remediation-plan.md](roadmaps/lan-hygiene-pcap-remediation-plan.md): Remediation tasks for reducing multicast noise, ARP storms, and rogue DHCP leaks.
* [capture-review-2026-10-05.md](roadmaps/capture-review-2026-10-05.md): Deep-dive forensic PCAP analysis revealing live network behaviors, external port 53 WAN forwarding remediation, and Control4 CA-10 metrics loops.
