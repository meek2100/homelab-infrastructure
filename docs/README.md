# 📚 Homelab Infrastructure Documentation Library

This directory serves as the centralized, authoritative documentation library for all physical hosts, virtual machines, networking hardware, and automated GitOps tooling across the homelab infrastructure.

---

## 📂 Documentation Catalog

```text
docs/
├── README.md                              # Master Table of Contents & Navigation Index
│
├── architecture/                          # Core System & Network Topologies
│   ├── network-topology.md                # Authoritative Dual-WAN, Araknis router/switch/APs, hypervisor bridges, DNS
│   ├── vlan-matrix.md                     # Authoritative 8-VLAN table, subnet CIDRs, DHCP pools, interzone firewall rules
│   └── network-interfaces-map.md          # Physical & virtual interface map and routing tables across pve, pve2, pve3
│
├── runbooks/                              # Operational Runbooks & Disaster Recovery Playbooks
│   ├── network-automation.md              # 1-click Netgear NSDP commands, L2 relay execution, live Wireshark sniffer ops
│   ├── recovery-walkthrough.md            # Bare-metal host and VM restoration sequencing via homelab MCP tools
│   └── security-backup-guide.md           # SOPS + age encryption standards, key management, and secrets hygiene
│
├── specifications/                        # Hardware Protocols & Technical Specs
│   └── netgear-gs108ev2-nsdp.md           # 715-line headless NSDP protocol specification, framing, C/Go/Python layouts
│
└── roadmaps/                              # Engineering Roadmaps & Verification Logs
    └── network-implementation-plan.md     # Multi-phase network audit milestones, status matrix, and verification logs
```

---

## 📑 Section Overview

### 🏛️ 1. Architecture
Authoritative ground-truth definitions for physical and logical topology:
* [network-topology.md](architecture/network-topology.md): Physical hardware layout, Araknis 520 router, Araknis 920 switch, Araknis 830 Wi-Fi 7 APs, office wireless bridge, dual-WAN routing, and split-horizon DNS.
* [vlan-matrix.md](architecture/vlan-matrix.md): Master 8-VLAN segmentation matrix (VLANs 1, 10, 20, 30, 40, 100, 150, 200), CIDR allocations, DHCP scope options, and inter-VLAN firewall access matrices.
* [network-interfaces-map.md](architecture/network-interfaces-map.md): Empirical operating system audit of all network interfaces, bridges (`vmbr0`, `vmbr1`), MAC addresses, and routing tables across Proxmox hosts and virtual machines.

### 🛠️ 2. Runbooks
Step-by-step operational and disaster-recovery execution guides:
* [network-automation.md](runbooks/network-automation.md): Single-click copy/paste runnable commands for headless Netgear GS108Ev2 switch management via Layer 2 NSDP relays (OpenWrt `192.168.1.226` / PVE `192.168.1.250`) and live Wireshark SPAN sniffer diagnostics.
* [recovery-walkthrough.md](runbooks/recovery-walkthrough.md): End-to-end bare-metal recovery sequence detailing the 4 phases: Host bootstrapping, host config restoration, VM bootstrapping, and Docker stack ignition via FastMCP tools.
* [security-backup-guide.md](runbooks/security-backup-guide.md): Standard operating procedures for encrypting secrets with SOPS + age, managing master keys, and ensuring zero unencrypted credentials enter Git.

### 🔬 3. Hardware Specifications
Low-level protocol specifications, register maps, and hardware reverse engineering:
* [netgear-gs108ev2-nsdp.md](specifications/netgear-gs108ev2-nsdp.md): Complete technical specification of the Netgear Switch Discovery Protocol (NSDP) for headless switches, covering UDP 63321/63322 transport dynamics, 32-byte header framing, TLV registers, SPI NOR flash persistence risks, and C/Go/Python protocol clients.

### 🗺️ 4. Roadmaps
Project tracking and audit verification records:
* [network-implementation-plan.md](roadmaps/network-implementation-plan.md): Comprehensive implementation plan tracking Phases 1, 2, and 3 across network segmentation, Araknis hardware, Netgear GitOps, Wireshark SPAN sniffer, and observability stacks.
