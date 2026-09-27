# 📝 Homelab Manual Setup Checklist & Action Items

This document tracks all manual setup tasks required to activate your notification pipeline and transition to the unified Proxmox Backup Server (PBS) architecture.

---

## 📋 Task Summary

- [x] **Task 1**: [Configure Alertmanager Secrets (Pushover & SMTP)](#task-1-configure-alertmanager-secrets-pushover--smtp) — 🟢 **Active & Configured**
- [ ] **Task 2**: [Install Proxmox Backup Server (Debian 12 LXC on `pve3`)](#task-2-install-proxmox-backup-server-debian-12-lxc-container-on-pve3)
- [ ] **Task 3**: [Initialize PBS Datastore & Generate API Token](#task-3-initialize-pbs-datastore--generate-api-token)
- [ ] **Task 4**: [Register PBS Storage on `pve`, `pve2`, and `pve3`](#task-4-register-pbs-storage-on-all-nodes)
- [ ] **Task 5**: [Transition Backup Schedule from Legacy vzdump to PBS](#task-5-transition-backup-schedule-to-pbs)
- [ ] **Task 6**: [Verify Grafana Dashboard & End-to-End Alert Routing](#task-6-verify-grafana--test-alert-routing)

---

## Task 1: Configure Alertmanager Secrets (Pushover & SMTP) — 🟢 Completed

Stack 71 on `nexus-server` is actively monitoring 49 targets and evaluating 9 alerting rules. Alertmanager now has decrypted SOPS credentials and routes directly to Pushover (`pushover-default`, `pushover-critical` siren) and SMTP email (`email-critical`, `email-warning`).

### Steps:
1. **Copy the example secrets file**:
   ```bash
   cp infrastructure/docker-stacks/nexus-server/71-monitoring/secrets.example.yaml \
      infrastructure/docker-stacks/nexus-server/71-monitoring/secrets.yaml
   ```

2. **Edit `secrets.yaml` with your actual keys**:
   ```yaml
   PUSHOVER_USER_KEY: "your-pushover-user-key"
   PUSHOVER_APP_TOKEN: "your-pushover-app-token"

   SMTP_SMARTHOST: "smtp.gmail.com:587"
   SMTP_FROM: "alerts@theurer.dev"
   SMTP_USER: "alerts@theurer.dev"
   SMTP_PASS: "your-google-app-password"
   SMTP_TO: "dave@theurer.dev"
   ```

3. **Encrypt the secrets with SOPS using age**:
   ```bash
   sops -e infrastructure/docker-stacks/nexus-server/71-monitoring/secrets.yaml > \
           infrastructure/docker-stacks/nexus-server/71-monitoring/secrets.enc.yaml
   rm infrastructure/docker-stacks/nexus-server/71-monitoring/secrets.yaml
   ```

4. **Deploy and reload Alertmanager**:
   ```bash
   python3 mcp/homelab/scripts/deploy-monitoring-stack.py deploy
   ```

---

## Task 2: Install Proxmox Backup Server (Debian 12 LXC Container on `pve3`)

Because `pve3` host runs Debian 13 (Trixie), PBS (built for Debian 12 Bookworm) is deployed inside a dedicated, lightweight Debian 12 LXC container (CT 105). This gives bare-metal speed with 0% host library conflicts.

### Step 2.1: Download Debian 12 Template on `pve3`
Run on `root@pve3`:
```bash
# Update template catalogue
pveam update

# Download the latest Debian 12 standard template
TEMPLATE=$(pveam available | grep -o 'debian-12-standard_[^ ]*' | head -n 1)
pveam download local "$TEMPLATE"
```

### Step 2.2: Provision the PBS LXC Container (CT 105)
Run on `root@pve3`:
```bash
TEMPLATE=$(pveam list local | grep -o 'debian-12-standard_[^ ]*' | head -n 1)

# Create container with dual-NIC (Management LAN + Private SAN)
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

# Bind mount the host backup disk /mnt/pve/backup into /backup in the container
mkdir -p /mnt/pve/backup/pbs-datastore
pct set 105 -mp0 /mnt/pve/backup,mp=/backup

# Start the container
pct start 105
```

### Step 2.3: Install PBS Inside Container CT 105
Enter the container shell:
```bash
pct enter 105
```

Inside the container (`root@pbs-server:~#`), run:
```bash
# 1. Add PBS No-Subscription repository
echo "deb http://download.proxmox.com/debian/pbs bookworm pbs-no-subscription" > /etc/apt/sources.list.d/pbs-no-subscription.list

# 2. Add Proxmox repository key
wget https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg -O /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg

# 3. Install Proxmox Backup Server
apt update && apt install -y proxmox-backup-server

# 4. Verify services are running
systemctl status proxmox-backup proxmox-backup-proxy
```

*PBS Web UI is now available at:* `https://192.168.1.244:8007` (and `https://10.25.25.244:8007`).

---

## Task 3: Initialize PBS Datastore & Generate API Token

Sets up the deduplicated backup pool on `/backup/pbs-datastore` and generates a secure API token.

### Commands to run inside CT 105 (`pct enter 105`):
```bash
# 1. Set permissions and create datastore
chown -R backup:backup /backup/pbs-datastore
proxmox-backup-manager datastore create homelab-datastore /backup/pbs-datastore

# 2. Create the backup user and API token
proxmox-backup-manager user create pve-backup@pbs --comment "PVE Hypervisor Backup Agent"
proxmox-backup-manager user generate-token pve-backup@pbs backup-token

# 3. Assign backup permissions to the token
proxmox-backup-manager acl update /datastore/homelab-datastore DatastoreBackup --auth-id pve-backup@pbs!backup-token

# 4. Display the PBS TLS Fingerprint (Record this for Task 4)
proxmox-backup-manager cert info | grep Fingerprint
```

> [!NOTE]
> Save the **Token Secret value** printed in step 2 and the **Fingerprint** from step 4.

---

## Task 4: Register PBS Storage on All Nodes

Adds PBS as a native storage target across all 3 nodes over the private `10.25.25.0/24` SAN network (`vmbr1` connecting to `10.25.25.244`).

### Commands to run on `pve` (`192.168.1.250`), `pve2` (`10.25.25.240`), and `pve3` (`192.168.1.245`):
```bash
pvesm add pbs pbs-backup \
    --server 10.25.25.244 \
    --datastore homelab-datastore \
    --username pve-backup@pbs!backup-token \
    --password "<TOKEN_SECRET_FROM_TASK_3>" \
    --fingerprint "<PBS_FINGERPRINT_FROM_TASK_3>" \
    --encryption-key autogen \
    --prune-backups keep-last=7,keep-daily=7,keep-weekly=4,keep-monthly=12
```


---

## Task 5: Transition Backup Schedule to PBS

Replaces the slow weekly `vzdump` jobs with fast daily incremental CBT backups.

### In the Proxmox Web GUI:
1. Navigate to **Datacenter ➔ Backup**.
2. **Disable / Delete** the existing weekly local `vzdump` backup jobs.
3. Click **Add** to create a new backup job:
   - **Node**: All
   - **Storage**: `pbs-backup`
   - **Selection Mode**: All Guests
   - **Schedule**: `02:00` (Daily at 2:00 AM)
   - **Mode**: Snapshot
   - **Compression**: Fast / ZSTD (handled natively by PBS)
4. **Trigger a test run**:
   - Manually trigger backup on a small VM (e.g. `nexus-server2` VM 100 on `pve3`).
   - Initial backup seeds the datastore.
   - Run a second backup immediately afterwards to verify **QEMU Changed Block Tracking (CBT)** completes in **under 30 seconds**!

---

## Task 6: Verify Grafana & Test Alert Routing

Confirm monitoring visualization and test alert routing to your phone and email.

1. **Open Grafana**:
   - URL: `http://192.168.40.185:3030`
   - Username / Password: `admin` / `admin`
   - Navigate to **Dashboards ➔ Homelab Network ➔ Homelab Network & Infrastructure Overview (v4)**.
   - Confirm all stat cards, router WAN bandwidth, switch port traffic, printer toners, and live Loki log stream are active.

2. **Trigger a Test Alert**:
   - Temporarily stop a test container or simulate an alert to confirm you receive the Pushover mobile siren and email notification:
   ```bash
   # Send a synthetic test alert to Alertmanager
   curl -H "Content-Type: application/json" -d '[{
     "labels": {
       "alertname": "TestAlert",
       "severity": "critical",
       "instance": "test-box"
     },
     "annotations": {
       "summary": "This is a test notification from Homelab Alertmanager",
       "description": "Verifying Pushover siren and SMTP email routing are working properly."
     }
   }]' http://192.168.40.185:9093/api/v2/alerts
   ```
   - Verify notification arrives on your phone via Pushover and in your email inbox!
