# 🚀 Mission Accomplished: Proxmox Agentic Backup & Recovery System

## 🚨 The Bare-Metal Recovery Playbook
If a node experiences a catastrophic disk failure, follow these exact manual steps *before* handing control over to the MCP AI Agent. This sequence is rigorously ordered to prevent dependency failures.

### Phase 1: Host Bootstrapping (Manual)
1. **Base Installation**: Install a fresh copy of Proxmox 9.x (e.g. 9.1.1) onto the new drive. You must set the exact same Hostname and IP address as before.
2. **SSH Authorization**: From the machine running the AI, run `ssh-copy-id root@<PROXMOX_IP>`. If you skip this, the AI cannot connect to the new OS to run restore scripts!
3. **Storage Pool Recreation**: Recreate any ZFS or LVM pools in the Proxmox UI using their exact original names (e.g., `local-lvm`, `shared-nas`). If the pool names do not exist, VMs will fail to attach disks when the AI restores them.
4. **Decryption Key**: Ensure your `homelab-infrastructure.key` is placed in the root of this repository so the AI can decrypt Docker `.env` and SOPS secret files.
 
### Phase 2: Host Restoration (AI)
1. **AI Intervention**: Ask the AI to run `restore_host_configs` and `restore_host`. The AI will securely restore your network bridges, Proxmox storage pool mappings, and all VM hardware definitions from the Git repository.
 
### Phase 3: VM Bootstrapping (Manual)
Your VMs will now physically appear in the Proxmox UI, but their virtual disks will be empty! You must manually:
1. Detach and remove the missing OS disk in the VM's Hardware tab.
2. Attach a fresh Hard Disk and mount a Linux ISO.
3. Install the base OS (e.g., Ubuntu 22.04 / 24.04).
4. Run `apt update && apt install qemu-guest-agent -y && systemctl enable --now qemu-guest-agent`. **(Critical: The AI cannot communicate with the VM without this agent running!)**
 
### Phase 4: VM & Docker Restoration (AI)
Ask the AI to execute the following tools in this **exact order**:
1. **`restore_apt_packages`**: The AI will first reinstall Docker, Nginx, and all other base software. *(This must run first so the software actually exists on disk!)*
2. **`restore_vm`**: The AI will inject your SSL certs, `.db` databases, custom Nginx routes, and `chmod/chown` ownership metadata. *(Running this second ensures default software configs are successfully overwritten!)*
3. **`restore_stacks`**: The AI will decrypt your SOPS secrets using `homelab-infrastructure.key`, write your `docker-compose.yml` files, and ignite all your Docker containers!

### Phase 5: Edge Router Rapid Disaster Recovery (OpenWrt & DD-WRT)
If an edge router suffers a corrupted flash, failed upgrade, or hardware replacement:

1. **OpenWrt AX3200 (`192.168.1.226`) Rapid Rollback (< 60s)**:
   - Decrypt the `/overlay` snapshot:
     ```bash
     sops --decrypt infrastructure/network/openwrt/dr_snapshots/openwrt-ax3200-overlay-upper.tar.enc.bin > /tmp/overlay.tar.gz
     ```
   - Stream directly into the router's `/overlay` partition and reboot:
     ```bash
     ssh root@192.168.1.226 "tar -xz -C /overlay -f -" < /tmp/overlay.tar.gz && ssh root@192.168.1.226 "reboot"
     ```
   - Alternatively, flash the standard sysupgrade archive:
     ```bash
     sops --decrypt infrastructure/network/openwrt/dr_snapshots/openwrt-sysupgrade-backup.tar.enc.bin | ssh root@192.168.1.226 "sysupgrade -r -"
     ```

2. **DD-WRT Aurora (`10.25.25.1`, WAN 2 / `pve2` Gateway)**:
   - Restore binary NVRAM via DD-WRT CLI:
     ```bash
     sops --decrypt infrastructure/network/ddwrt/aurora/dr_snapshots/aurora-nvram-backup.enc.bin | ssh root@10.25.25.1 "cat > /tmp/nvram.bin && nvram restore /tmp/nvram.bin && nvram commit && reboot"
     ```
   - Restore the full `/opt` USB filesystem:
     ```bash
     sops --decrypt infrastructure/network/ddwrt/aurora/dr_snapshots/aurora-opt-complete.tar.enc.bin | ssh root@10.25.25.1 "tar -xz -C / -f -"
     ```

3. **DD-WRT Luna (`10.20.20.1`, Upstream Gateway)**:
   - Restore binary NVRAM:
     ```bash
     sops --decrypt infrastructure/network/ddwrt/luna/dr_snapshots/luna-nvram-backup.enc.bin | ssh root@10.20.20.1 "cat > /tmp/nvram.bin && nvram restore /tmp/nvram.bin && nvram commit && reboot"
     ```
 
---
 
We have successfully evolved your repository from a static "hard copy" backup into a modern, highly-readable **Active Agentic Backup System**.
 
## 1. 📂 The GitOps Restructuring
All configuration and state files have been organized out of legacy directories into a structured, human-readable GitOps layout.
 
> [!SUCCESS] Human-Readable Server Organization & Master Index
> - `infrastructure/vms/pve-100-nexus-server/drift`
> - `infrastructure/vms/pve-102-luna-server/drift`
> - `infrastructure/docker-stacks/media-server/82/`
> - **Full Service Mapping**: See [`infrastructure/docker-stacks/STACK-INDEX.md`](../../infrastructure/docker-stacks/STACK-INDEX.md) to instantly locate any of the 91 stacks by app name (e.g., Plex, Home Assistant, AdGuard Home).
 
## 2. 🧠 The Homelab Infrastructure MCP Server
A custom Python Model Context Protocol (MCP) server is located in `mcp/homelab/` and configured locally in `.agents/mcp_config.json`.

- **Total Tools Provided**: 20 action-oriented FastMCP tools (covering hypervisor discovery, VM lifecycle, container restoration, network switching, routing, streaming PCAP telemetry, and external health audits).
- **Execution Architecture**: All python scripts are cleanly encapsulated inside `mcp/homelab/scripts/` running under `.venv`.


### 🛡️ Ironclad Architectural Fixes
During development, we uncovered and eliminated several critical blindspots:
- **Binary Corruption**: Added `base64` wrappers inside `qm guest exec` so SQLite `.db` Docker files transfer perfectly.
- **Permissions Drops**: Engineered a `permissions.json` injection using `stat` so Docker containers don't crash from `root:root` ownership drift.
- **Git Push Jams**: Excluded `.rustup` and `.cargo` binary drift to keep GitHub pushes lightweight and fast.
- **Hardcoded Fragility**: Removed all hardcoded IP addresses from bash scripts, replacing them with dynamic GitOps auto-discovery.
