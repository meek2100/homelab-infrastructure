# 🏛️ Araknis Hardware GUI Binary Configuration Backups

This directory stores native `.cfg` / `.tar.gz` exported configuration files downloaded from the Araknis web interfaces.

---

## 📥 How to Export Configuration Files

### 1. Araknis 520 Dual-WAN Router (`https://192.168.1.1`)
1. Log into the router management interface.
2. Navigate to: **Maintenance ➔ Backup / Restore**.
3. Under **Backup Configuration**, click **Save Configuration File**.
4. Save the file into this directory as:
   `infrastructure/network/araknis/araknis-520-router.cfg`

### 2. Araknis 920 Core Switch (`https://192.168.1.215`)
1. Log into the switch management interface.
2. Navigate to: **Maintenance ➔ Backup / Restore** (or **File Management ➔ Dual Image / Config Backup**).
3. Export the running configuration.
4. Save the file into this directory as:
   `infrastructure/network/araknis/araknis-920-switch.cfg`

### 3. Araknis 830 APs (`https://192.168.1.231` & `https://192.168.1.236`)
1. Log into each access point interface.
2. Navigate to: **Maintenance ➔ Configuration Backup**.
3. Save the files as:
   - `infrastructure/network/araknis/araknis-830-ap1.cfg`
   - `infrastructure/network/araknis/araknis-830-ap2.cfg`

---

## 🔒 Automatic SOPS Encryption
Once downloaded, any files in this directory containing plain-text passwords or Wi-Fi keys can be encrypted using SOPS:

```bash
sops --encrypt --age age1yqmzhsl58talkkax7g6xwj9xs68rqm2efxa5z0zg2u566m3dzeusj96x5f \
     --output araknis-520-router.enc.cfg araknis-520-router.cfg
```
