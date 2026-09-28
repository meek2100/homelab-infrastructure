# 🔐 GitOps Drills, Disaster Recovery & Secret Rotation Runbook

This runbook establishes standard operating procedures for semi-annual secret rotation, disaster recovery restore drills, and drift verification across all 3 Proxmox hypervisors, 6 VMs, 85 Docker stacks, network switches, routers, and external cloud VPS instances.

---

## 📅 Schedule & Verification Cadence
- **Monthly**: Automated GitOps configuration drift checks (`audit_infrastructure`, `verify_network_matrix`).
- **Quarterly**: PBS backup restoration verification drill (restoring a test VM or container from `pbs-backup`).
- **Semi-Annual**: Secret rotation drill (re-encrypting all 68 SOPS encrypted stacks with updated `age` keys).
- **Annual**: Cold bare-metal hypervisor recovery drill using Git blueprints in `infrastructure/hosts/`.

---

## 1. Semi-Annual Secret Rotation Procedure

All sensitive environment files and passwords across 68 Docker stacks are encrypted using `SOPS` with `age` encryption keys.

### Step 1: Generate New Age Key Pair
```bash
# Generate a new age identity key
age-keygen -o ~/.config/sops/age/keys.txt.new

# Extract the public recipient key
grep "public key:" ~/.config/sops/age/keys.txt.new | awk '{print $NF}'
# Output: age1...
```

### Step 2: Update `.sops.yaml` Configuration
In `.sops.yaml` at the root of the repository, append or replace the age recipient:
```yaml
creation_rules:
  - path_regex: .*\.enc\.ya?ml$
    age: "age1<old_recipient>,age1<new_recipient>"
```

### Step 3: Batch Re-Encrypt All 68 Secret Stacks
Run the automated re-encryption loop across all stacks:
```bash
find infrastructure/docker-stacks/ -name "secrets.enc.yaml" -exec sops updatekeys -y {} \;
find infrastructure/network/openwrt/configs/ -name "*.enc.yaml" -exec sops updatekeys -y {} \;
```

### Step 4: Verification & Decryption Test
Verify that the new private key can decrypt the secrets cleanly:
```bash
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt.new sops -d infrastructure/docker-stacks/nexus-server/71-monitoring/secrets.enc.yaml
```

### Step 5: Key Archive & Cleanup
1. Move the new private key into your secure password manager (1Password / Bitwarden / Keepass).
2. Commit the re-encrypted `.enc.yaml` files and `.sops.yaml` to Git:
   ```bash
   git commit -am "chore(security): rotate SOPS age encryption keys across all stacks"
   ```
3. Securely remove temporary plaintext key files: `shred -u ~/.config/sops/age/keys.txt.new`.

---

## 2. Disaster Recovery Restore Drills

### Drill A: Proxmox Backup Server (PBS) Incremental CBT Restore
To verify that incremental deduplicated backups can be recovered during an outage:

1. **List Available Snapshots via FastMCP**:
   ```python
   # Via FastMCP
   list_vm_snapshots(node="pve3", vmid="100")
   ```
2. **Execute In-Place Rollback or Restore to New VMID**:
   ```bash
   # In PVE Web UI or CLI, restore from PBS storage pool
   qmrestore pbs-backup:backup/vm/100/2026-09-28T00:00:00Z 999 --storage local-lvm
   ```
3. **Verify Guest Integrity**:
   Start VM 999, confirm network interface up, and verify Docker daemon starts without container name collisions.

---

### Drill B: Office Netgear GS108Ev2 Switch Restore
In the event of hardware replacement or switch reset to factory defaults (`192.168.0.239`):

1. **Locate Latest Verified GitOps Backup**:
   [`infrastructure/network/configs/netgear-gs108e-backup.json`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/network/configs/netgear-gs108e-backup.json)
2. **Execute Programmatic FastMCP Restore**:
   ```bash
   # Verify drift first
   python3 mcp/homelab/scripts/manage-netgear-switch.py verify --file infrastructure/network/configs/netgear-gs108e-backup.json

   # Restore all 8 ports, VLANs (1, 10, 20, 30, 40, 150), and PVIDs
   python3 mcp/homelab/scripts/manage-netgear-switch.py restore --file infrastructure/network/configs/netgear-gs108e-backup.json --confirm
   ```

---

### Drill C: Core Araknis 520 Router Restore
1. **Locate Latest Verified Encrypted Backup**:
   [`infrastructure/network/configs/araknis-520-backup.cfg`](file:///home/agentsvc/repos/homelab-infrastructure/infrastructure/network/configs/araknis-520-backup.cfg)
2. **Execute REST API Restore**:
   ```bash
   python3 mcp/homelab/scripts/manage-araknis-router.py restore --file infrastructure/network/configs/araknis-520-backup.cfg --confirm
   ```
   *The router uploads the encrypted OpenSSL blob, reboots, and restores all 21 ACL rules and 8 VLAN subnets.*

---

### Drill D: External Cloud VPS Restore (web-server & email-server)
1. **Web Server (`theurer.dev`)**:
   - Restore Nginx virtual hosts:
     ```bash
     scp infrastructure/external-hosts/web-server/nginx/sites-available/* meek2100@146.235.203.133:/etc/nginx/sites-available/
     ssh meek2100@146.235.203.133 "sudo nginx -t && sudo systemctl reload nginx"
     ```
   - Restore MariaDB databases from newest archive in `infrastructure/external-hosts/web-server/backups/`.
2. **Email Server (`mail.theurer.dev`)**:
   - Restore Postfix & Dovecot configs from `infrastructure/external-hosts/email-server/`:
     ```bash
     scp infrastructure/external-hosts/email-server/postfix/* meek2100@35.212.229.212:/etc/postfix/
     scp infrastructure/external-hosts/email-server/dovecot/* meek2100@35.212.229.212:/etc/dovecot/
     ssh meek2100@35.212.229.212 "sudo postfix check && sudo doveconf -n >/dev/null && sudo systemctl reload postfix dovecot"
     ```

---

## 3. Post-Drill Fleet Health Verification

Always execute the three core diagnostic tools following any restore drill:
1. `python3 mcp/homelab/scripts/verify-network-matrix.py` (Assert 21/21 targets UP with <10ms latency).
2. `python3 mcp/homelab/scripts/manage-external-services.py status` (Assert Web HTTP 200, SMTP :587, IMAPS :993, and TLS certs valid).
3. Check Prometheus Web UI (`http://192.168.40.185:9090/targets`) to confirm **49/49 targets UP**.

---

## 4. External Cloud Log Ingress Lockdown (`logs.theurer.dev`)

Because Loki in Stack 71 runs in single-tenant mode (`auth_enabled: false`), exposing `logs.theurer.dev` without strict Zero Trust lockdown creates serious risks of log reading or denial-of-service ingestion spam.

### Cloudflare Zero Trust Tunnel Setup
1. Open **Cloudflare Zero Trust Dashboard** -> **Networks** -> **Tunnels**.
2. Select the active `nexus-server` tunnel (Stack 46).
3. Under **Public Hostname**, add:
   * **Subdomain**: `logs`
   * **Domain**: `theurer.dev`
   * **Type**: `HTTP`
   * **URL**: `localhost:3100` (or `192.168.40.185:3100`)

### Cloudflare WAF Custom Rules (Mandatory Lockdown)
Navigate to **Cloudflare Dashboard** -> `theurer.dev` -> **Security** -> **WAF** -> **Custom Rules**:

1. **Rule 1: External VPS IP Whitelist (Drop All Others)**
   * **Expression**:
     ```
     (http.host eq "logs.theurer.dev" and not ip.src in {146.235.203.133 35.212.229.212})
     ```
   * **Action**: `Block`
   * *Effect*: Only Oracle Cloud (`web-server`) and Google Cloud (`email-server`) can connect. The rest of the Internet is instantly dropped at Cloudflare edge.

2. **Rule 2: Push-Only Path and Method Enforcement**
   * **Expression**:
     ```
     (http.host eq "logs.theurer.dev" and (http.request.method ne "POST" or not http.request.uri.path matches "^/loki/api/v1/push"))
     ```
   * **Action**: `Block`
   * *Effect*: Completely blocks all read/query APIs (`/loki/api/v1/query*`, `/loki/api/v1/labels`, `/ready`, `/metrics`). External VPS nodes cannot query historical homelab logs.

3. **Rule 3: Ingestion Rate Limiting**
   * Navigate to **Security** -> **WAF** -> **Rate Limiting Rules**.
   * Target: `http.host eq "logs.theurer.dev" and http.request.uri.path matches "^/loki/api/v1/push"`
   * Rate: 100 requests per 10 seconds per IP -> Action: `Block` (Mitigates ingestion flood attacks).

