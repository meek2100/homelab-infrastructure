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
 │  │   (OpenMediaVault)     │    │       (PBS Core)       │  │
 │  │   IP: 10.25.25.248     │    │   IP: 10.25.25.245     │  │
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

Because `pve3` runs standard Debian / Proxmox VE on the HP EliteDesk, you can install PBS natively alongside PVE:

```bash
# 1. SSH into pve3 as root
ssh root@192.168.1.245

# 2. Add the Proxmox Backup Server No-Subscription repository
echo "deb http://download.proxmox.com/debian/pbs bookworm pbs-no-subscription" > /etc/apt/sources.list.d/pbs-no-subscription.list

# 3. Update apt and install PBS packages
apt update && apt install -y proxmox-backup-server

# 4. Verify PBS service is running
systemctl status proxmox-backup proxmox-backup-proxy
```

*The PBS Web Management UI will now be available at:* `https://10.25.25.245:8007` (or `https://192.168.1.245:8007`) using your `root` Linux credentials.

---

### Step 2: Initialize the Backup Datastore on `pve3`

Create a dedicated filesystem path or ZFS dataset for PBS backups:

```bash
# On pve3: Create directory for backups (or mount secondary backup disk)
mkdir -p /mnt/pve/backup-datastore
chown -R backup:backup /mnt/pve/backup-datastore

# Create the datastore in PBS
proxmox-backup-manager datastore create homelab-datastore /mnt/pve/backup-datastore
```

---

### Step 3: Retrieve PBS Fingerprint & Create API Token

To allow Proxmox nodes to authenticate securely over the SAN network:

```bash
# On pve3: Get TLS SHA-256 fingerprint
proxmox-backup-manager cert info | grep Fingerprint

# Create an unprivileged backup user and API token
proxmox-backup-manager user create pve-backup@pbs --comment "Proxmox Cluster Backup Agent"
proxmox-backup-manager user generate-token pve-backup@pbs backup-token

# Grant datastore backup permissions to the token
proxmox-backup-manager acl update /datastore/homelab-datastore DatastoreBackup --auth-id pve-backup@pbs!backup-token
```

---

### Step 4: Register PBS Storage Target on `pve`, `pve2`, and `pve3`

Run this on each Proxmox node to add PBS as a native storage target over the `10.25.25.0/24` network:

```bash
# Run on pve (192.168.1.250), pve2 (10.25.25.240), and pve3 (192.168.1.245):
pvesm add pbs pbs-backup \
    --server 10.25.25.245 \
    --datastore homelab-datastore \
    --username pve-backup@pbs!backup-token \
    --password "<TOKEN_SECRET>" \
    --fingerprint "<PBS_FINGERPRINT>" \
    --encryption-key autogen \
    --prune-backups keep-last=7,keep-daily=7,keep-weekly=4,keep-monthly=12
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
2. Verify the initial run completes and creates chunks in `/mnt/pve/backup-datastore`.
3. Trigger a second backup immediately afterwards: verify QEMU CBT activates and completes in **< 15 seconds**!
