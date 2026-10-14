# 🛡️ Proxmox Backup Server (PBS) Architecture & Implementation Runbook

This runbook outlines the authoritative architecture and deployment playbook for transitioning from legacy, isolated Proxmox `vzdump` backups to a centralized **Proxmox Backup Server (PBS)** datastore.

---

## 🏛️ Ground-Truth Architecture & Network Topology

```text
 ┌──────────────────────┐          ┌──────────────────────┐
 │   pve (Node 1)       │          │   pve2 (Node 2)      │
 │ Dell Precision 5520  │          │ Awow AK34Pro Mini PC │
 │ IP: 10.25.25.250     │          │ IP: 10.25.25.240     │
 └──────────┬───────────┘          └──────────┬───────────┘
            │                                 │
            │ QEMU Fast CBT Incremental       │ QEMU Fast CBT Incremental
            │ (VLAN 10.25.25.0/24 SAN)        │ (VLAN 10.25.25.0/24 SAN)
            ▼                                 ▼
 ┌────────────────────────────────────────────────────────────┐
 │               pve3 (HP EliteDesk Node 3)                   │
 │                                                            │
 │  ┌────────────────────────┐    ┌────────────────────────┐  │
 │  │      nas-server        │    │ Proxmox Backup Server  │  │
 │  │   (OpenMediaVault)     │    │   (PBS Core CT 105)    │  │
 │  │   IP: 10.25.25.248     │    │   IP: 10.25.25.244     │  │
 │  └────────────────────────┘    └───────────┬────────────┘  │
 │                                            │               │
 │               ┌────────────────────────────▼─────────┐     │
 │               │  Local Backup Datastore Pool (ZFS)   │     │
 │               └──────────────────────────────────────┘     │
 └────────────────────────────────────────────────────────────┘
```

### Key Architectural Guardrails
1. **Network Transport**: All backup traffic from `pve`, `pve2`, and `pve3` flows exclusively across the **`10.25.25.0/24` dedicated high-speed SAN network** (`vmbr1`), completely air-gapped from the house LAN (`192.168.1.0/24`) and router ACLs.
2. **QEMU Changed Block Tracking (CBT)**: VMs track dirty disk blocks in memory. Subsequent daily backups only read and transmit modified chunks, dropping runtimes from 45 minutes to **10–30 seconds**.
3. **Chunk-Level Deduplication**: Data is split into 4MB SHA-256 content-addressed chunks. Common OS disks across Ubuntu and Debian VMs are stored only once, saving **75–90% disk space**.
4. **Single-File Restore**: Allows extracting individual configuration files, SQLite databases, or directories directly within the Proxmox GUI without restoring full 50GB virtual disks.

---

## 🚀 Step-by-Step Deployment Runbook

### Step 1: Install Proxmox Backup Server on Node 3 (`pve3`)

Because `pve3` hypervisor runs Debian 13 (Trixie), PBS was deployed inside a dedicated, lightweight LXC container (CT 105) to isolate host packaging. *(Note: CT 105 initially ran Debian 12 Bookworm with PBS 3.4, and was upgraded to PBS 4.2 on Debian 13 on 2026-09-30; the initial deployment pattern remains identical)*:

```bash
# 1. Download Debian 12 container template on pve3
pveam update
TEMPLATE=$(pveam available | grep -o 'debian-12-standard_[^ ]*' | head -n 1)
pveam download local "$TEMPLATE"

# 2. Provision PBS Container (CT 105)
pct create 105 "local:vztmpl/$TEMPLATE" \
  --hostname pbs-server \
  --ostype debian \
  --cores 2 \
  --memory 2048 \
  --swap 1024 \
  --storage local-lvm \
  --rootfs local-lvm:16 \
  --net0 name=eth0,bridge=vmbr0,ip=192.168.1.244/24,gw=192.168.1.1 \
  --net1 name=eth1,bridge=vmbr1,ip=10.25.25.244/24 \
  --nameserver "192.168.1.1 1.1.1.1" \
  --onboot 1 \
  --unprivileged 0 \
  --features nesting=1

# 3. Bind mount host backup storage and launch
mkdir -p /mnt/pve/backup/pbs-datastore
pct set 105 -mp0 /mnt/pve/backup,mp=/backup
pct start 105

# 4. Install PBS inside container (pct enter 105)
pct enter 105
echo "deb http://download.proxmox.com/debian/pbs bookworm pbs-no-subscription" > /etc/apt/sources.list.d/pbs-no-subscription.list
wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg
apt update && apt install -y proxmox-backup-server
systemctl status proxmox-backup proxmox-backup-proxy
```


*The PBS Web Management UI will now be available at:* `https://192.168.1.244:8007` (or `https://10.25.25.244:8007`) using your `root` Linux credentials.

---

### Step 2: Initialize the Backup Datastore inside CT 105

Create the dedicated datastore pool inside the container on the bind-mounted disk:

```bash
# Inside CT 105 (pct enter 105):
mkdir -p /backup/pbs-datastore
chown -R backup:backup /backup/pbs-datastore

# Create the datastore in PBS
proxmox-backup-manager datastore create homelab-datastore /backup/pbs-datastore
```

---

### Step 3: Retrieve PBS Fingerprint & Create API Token

To allow Proxmox nodes to authenticate securely over the SAN network:

```bash
# Inside CT 105 (pct enter 105):
# Get TLS SHA-256 fingerprint
proxmox-backup-manager cert info | grep Fingerprint

# Create an unprivileged backup user and API token
proxmox-backup-manager user create pve-backup@pbs --comment "Proxmox Cluster Backup Agent"
proxmox-backup-manager user generate-token pve-backup@pbs backup-token

# Grant parent user permissions, then DatastorePowerUser to token (required for post-backup prune)
proxmox-backup-manager acl update /datastore/homelab-datastore DatastoreAdmin --auth-id pve-backup@pbs
proxmox-backup-manager acl update /datastore/homelab-datastore DatastorePowerUser --auth-id pve-backup@pbs!backup-token

# Create per-host isolated namespaces to prevent VM ID collisions (e.g. VM 100 on multiple hosts)
proxmox-backup-manager namespace create homelab-datastore pve
proxmox-backup-manager namespace create homelab-datastore pve2
proxmox-backup-manager namespace create homelab-datastore pve3
```

---

### Step 4: Register PBS Storage Target on `pve`, `pve2`, and `pve3`

Run this on each Proxmox node to add PBS as a native storage target over the `10.25.25.0/24` SAN network, configuring the respective host namespace:

```bash
# Example for pve (use respective namespace: pve, pve2, or pve3):
pvesm add pbs pbs-backup \
    --server 10.25.25.244 \
    --datastore homelab-datastore \
    --namespace pve \
    --username pve-backup@pbs!backup-token \
    --password "<TOKEN_SECRET>" \
    --fingerprint "<PBS_FINGERPRINT>" \
    --encryption-key autogen \
    --prune-backups keep-last=7,keep-daily=7,keep-weekly=4,keep-monthly=12

# Note: Standalone PVE nodes do not share /etc/pve/priv/storage/!
# Distribute the generated client encryption key (/etc/pve/priv/storage/pbs-backup.enc)
# from pve to pve2 and pve3 via scp so all nodes use identical client encryption.
```


---

### Step 5: Configure Automated Daily Incremental Backup Schedule

In the Proxmox Web GUI (**Datacenter ➔ Backup ➔ Add**) or via CLI:
- **Node**: All
- **Storage**: `pbs-backup`
- **Selection**: All Guests (or select VMs)
- **Schedule**: `02:00` (Daily at 2:00 AM)
- **Mode**: Snapshot
- **Bandwidth Limit**: Unlimited (local SAN link)

---

## 📈 Post-Deployment Verification
1. Run a manual test backup of a VM (e.g. `qm backup 100 pbs-backup`).
2. Verify the initial run completes and creates chunks in `/mnt/pve/backup/pbs-datastore`.
3. Trigger a second backup immediately afterwards: verify QEMU CBT activates and completes in **< 15 seconds**!

---

## 💾 Hardware Upgrade & Auto-Recovery Storage Architecture (2026-10-13)

### 1. Drive Failure & Hardware Replacement
On 2026-10-12, the legacy 500GB external USB drive on `pve3` failed with persistent kernel I/O errors and entered an emergency read-only state.
- **Decommissioned Hardware**: 500GB Seagate Thin HDD in JMicron JMS567 enclosure (bulk-only transport).
- **Installed Production Hardware**: 1TB Western Digital CMR 2.5" HDD (`WD10SPCX`, 5400 RPM, 16MB Cache) enclosed in a Benfei USB 3.0 to SATA adapter.
- **Kernel Transport**: Negotiating USB 3.0 SuperSpeed (5000M) via native Linux kernel `uas` (USB Attached SCSI) driver.

### 2. Bulletproof `/etc/fstab` & Auto-Recovery Directives
To eliminate boot hangs and guarantee automatic filesystem remounting if the USB bus drops or re-enumerates:
```fstab
UUID=010e24cd-69dc-4517-95ff-8b5feed92cfa /mnt/pve/backup ext4 defaults,noatime,nofail,x-systemd.automount,x-systemd.device-timeout=10s 0 2
```
- `UUID=010e24cd-69dc-4517-95ff-8b5feed92cfa`: Guarantees deterministic disk binding regardless of Linux kernel device assignment (`/dev/sdb` vs `/dev/sdc`).
- `x-systemd.automount`: Defers physical filesystem mounting until `/mnt/pve/backup` is accessed. Recovers on demand without requiring a host reboot.
- `nofail` & `x-systemd.device-timeout=10s`: Prevents systemd from halting boot at the emergency shell if the drive is disconnected.

---

## ☁️ Offsite Encrypted Google Drive Mirror (`sync-pbs-backup-to-gdrive.py`)

To achieve true 3-2-1 backup compliance, the PBS datastore is continuously mirrored offsite to Google Drive (`gdrive-encrypted:homelab-backups/pbs-datastore/`) using a standalone orchestrator.

### 1. Standalone Script vs Legacy vzdump Separation
- **Legacy `vzdump` Deprecation**: Monolithic `.vma.zst` archives from `pve`, `pve2`, and `pve3` are migrated once and retired.
- **Standalone PBS Mirror**: Proxmox Backup Server stores deduplicated 4MB chunks in `.chunks/` plus snapshot metadata in `vm/`, `ct/`, and `ns/`. The standalone orchestrator mirrors the entire datastore structure (excluding temporary `.lock` and `lost+found/` files) for instant disaster recovery.
- **Concurrency Mutex**: `mcp/homelab/scripts/sync-pbs-backup-to-gdrive.py` verifies whether legacy vzdump migrations are active before launching, preventing bandwidth starvation and Google 750GB/day quota exhaustion.

### 2. Operational CLI Reference
```bash
# Check PBS mirror status, timer health, and mutex state
.venv/bin/python3 mcp/homelab/scripts/sync-pbs-backup-to-gdrive.py status

# Deploy / update sync script and systemd timer in LXC 105
.venv/bin/python3 mcp/homelab/scripts/sync-pbs-backup-to-gdrive.py deploy

# Trigger manual offsite sync (honors vzdump mutex)
.venv/bin/python3 mcp/homelab/scripts/sync-pbs-backup-to-gdrive.py start

# View recent transfer logs from LXC 105
.venv/bin/python3 mcp/homelab/scripts/sync-pbs-backup-to-gdrive.py logs
```
The systemd service (`pbs-gdrive-sync.service`) and timer (`pbs-gdrive-sync.timer`) execute nightly at 03:00 UTC inside LXC 105.

