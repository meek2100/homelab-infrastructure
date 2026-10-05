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

Because `pve3` hypervisor runs Debian 13 (Trixie), PBS (built for Debian 12 Bookworm) is deployed inside a dedicated, lightweight Debian 12 LXC container (CT 105). This gives bare-metal speed with zero host library conflicts:

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

# Grant datastore backup permissions to the token
proxmox-backup-manager acl update /datastore/homelab-datastore DatastoreBackup --auth-id pve-backup@pbs!backup-token
```

---

### Step 4: Register PBS Storage Target on `pve`, `pve2`, and `pve3`

Run this on each Proxmox node to add PBS as a native storage target over the `10.25.25.0/24` network:

```bash
# Run on pve (192.168.1.250), pve2 (10.25.25.240), and pve3 (192.168.1.245):
pvesm add pbs pbs-backup \
    --server 10.25.25.244 \
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
2. Verify the initial run completes and creates chunks in `/mnt/pve/backup/pbs-datastore`.
3. Trigger a second backup immediately afterwards: verify QEMU CBT activates and completes in **< 15 seconds**!
