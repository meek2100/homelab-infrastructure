# Homelab Workspace Rules & Operating Guidelines

## Core Operating Boundaries

### Always Do
- **Zero-Trust Secrets**: Encrypt all credentials using SOPS + age (`*.enc.yaml`, key in `homelab-infrastructure.key`). Redact keys in logs.
- **MCP Interface First**: All committed automation, backups, restores, and telemetry must run via FastMCP tools in `.venv`. Committed scripts must reside under `mcp/homelab/scripts/` and map to FastMCP tools.
- **Local Scratch & Exploration**: Ad-hoc scripts, prototypes, WIP tests, or temporary dumps MUST stay in `.agents/scripts/` (untracked) and never committed to Git.
- **QGA Binary Safety**: When extracting files via `qm guest exec`, base64-encode (`base64 -w 0`) inside the VM to prevent JSON parser data corruption.
- **Base64 Payload Streaming**: Encode payloads before piping to `qm guest exec` (`echo '<b64>' | base64 -d > target`).
- **File Metadata & Permissions**: Capture and restore file ownership and modes (`stat -c '%a:%u:%g'`).
- **Background Command Execution**: When `run_command` waits for user approval, let it wait. Do NOT kill or poll.
- **Non-Destructive Testing**: Always run verification with `--dry-run` or `--diff-only` before applying changes.

### Ask First
- Applying live network changes (Araknis ACLs/VLANs, Netgear NSDP, OpenWrt routes).
- Starting, stopping, rebooting, or rolling back any VM or LXC container.
- Pruning Docker containers, volumes, or snapshots.
- Deploying or re-deploying Portainer stacks on live VMs.

### Never Do
- Never commit plaintext secrets, `.key`, `.pem`, `.env`, or unencrypted credentials to Git.
- Never create or commit standalone scripts outside of `mcp/homelab/scripts/`.
- Never run Docker inside unprivileged LXC containers (use full VMs to avoid overlay2 bugs).
- Never form a Proxmox VE cluster (hosts MUST remain standalone to prevent quorum failures).
- Never run commands requiring `sudo`/root or interactive TTY prompts yourself; hand them to the user.
- Never write directly to Netgear SPI flash without prior verification.

---

## Infrastructure Topology & Architecture

- **Hypervisors (Standalone PVE 9.1.1 Nodes)**:
  - `pve` (`192.168.1.250`, Dell Precision 5520): VMs 100 (`nexus`), 102 (`luna`), 103 (`media`), 107 (`vxlan`), 109 (`minecraft`). iGPU passed to VM 103.
  - `pve2` (`192.168.1.240` & `10.25.25.240`, Awow Mini PC): VM 100 (`discovery-server`). Only `vmbr0` and `vmbr1` (no VLAN sub-interfaces).
  - `pve3` (`192.168.1.245` & `10.25.25.245`, HP EliteDesk): VM 100 (`nexus-server2`), VM 101 (`nas-server`), LXC 105 (`pbs-server` on `192.168.1.244` / `10.25.25.244`).
- **Network Segmentation & Routing**:
  - `192.168.1.0/24`: Primary Management & Egress LAN (VLAN 1).
  - `10.25.25.0/24`: Private High-Speed NAS/SAN Network (`vmbr1` across nodes, NAS `10.25.25.248`, PBS `10.25.25.244`).
  - Active VLANs: 1 (Default), 10 (Office/Trusted), 20 (Audio/Video), 30 (Automation), 40 (Servers/Admin), 100 (Guest), 150 (Camera/IoT), 200 (VoIP/Streaming). *VLAN 50 abolished.*
  - DNS Servers: Primary `192.168.40.185` (`nexus-server`), Secondary `192.168.40.186` (`nexus-server2`).
  - DD-WRT Routers: Aurora `10.25.25.1`, Luna `10.20.20.1` (SSH user `root` with `ddwrt_id_ed25519`).

---

## Operational Verification & Fleet Commands

All operations run from project root (`/home/agentsvc/repos/homelab-infrastructure`):

```bash
# 1. Fleet Drift & State Verification (Diff only)
.venv/bin/python3 mcp/homelab/scripts/sync-live-fleet.py --diff-only

# 2. Rebuild Master Stack Catalog (91 Portainer stacks, 188 services)
.venv/bin/python3 -c "from mcp.homelab.server import generate_stack_index; print(generate_stack_index())"

# 3. Network Matrix & ACL Audit (Verify all VLAN routes & ICMP/TCP)
.venv/bin/python3 mcp/homelab/scripts/verify-network-matrix.py --profile comprehensive

# 4. Netgear GS108Ev2 Switch Audit (NSDP via OpenWrt L2 bridge relay)
.venv/bin/python3 mcp/homelab/scripts/manage-netgear-switch.py --relay 192.168.1.226 status

# 5. Full Infrastructure Backup Routine (Zero-trust capture)
.venv/bin/python3 -c "
from mcp.homelab.server import *
backup_araknis_router(); backup_araknis_switch(); backup_netgear_switch()
backup_pakedge_switch(); backup_openwrt(); backup_ddwrt('aurora'); backup_ddwrt('luna')
sync_fleet(apply=True); backup_apt_packages(); sync_wireshark_capture()
"
```

---

## Authoritative Documentation Reference

- **Full Documentation Index**: [`docs/README.md`](docs/README.md)
- **FastMCP Tools Reference (20 Action-Oriented Tools)**: [`docs/runbooks/mcp-tools-reference.md`](docs/runbooks/mcp-tools-reference.md)
- **Network Topology & Hardware Details**: [`docs/architecture/network-topology.md`](docs/architecture/network-topology.md)
- **VLAN Matrix & 36 Live ACL Rules**: [`docs/architecture/vlan-matrix.md`](docs/architecture/vlan-matrix.md)
- **OS Network Interfaces & Routing**: [`docs/architecture/network-interfaces-map.md`](docs/architecture/network-interfaces-map.md)
- **Network Automation & NSDP Specs**: [`docs/runbooks/network-automation.md`](docs/runbooks/network-automation.md) & [`docs/specifications/netgear-gs108ev2-nsdp.md`](docs/specifications/netgear-gs108ev2-nsdp.md)
- **Bare-Metal Recovery Guide**: [`docs/runbooks/recovery-walkthrough.md`](docs/runbooks/recovery-walkthrough.md)
- **Proxmox Backup Server Architecture**: [`docs/runbooks/proxmox-backup-server.md`](docs/runbooks/proxmox-backup-server.md)
- **FastMCP Tool Implementation**: [`mcp/homelab/server.py`](mcp/homelab/server.py) (20 consolidated tools cataloged)
