# 🔒 SOPS + Age Encrypted Backup & Restoration Guide

This guide details how secrets, API tokens, database dumps, and credentials across all 3 Proxmox nodes are encrypted using `SOPS` and `age` before being committed to your private GitHub repository.

---

## 1. Zero-Trust Security & Master Key Architecture

- **Public Repository Security**: All sensitive values inside `.env`, `.yaml`, `.json`, `.sql`, and `.conf` files are encrypted using `SOPS` + `age` (`*.enc.yaml`, `*.enc.json`).
- **Single Master Key**: You hold a single private `age` key (`keys.txt` / secret passphrase) saved exclusively in your personal password manager (1Password, Bitwarden, KeePass, etc.).
- **No Local Secret Backups Needed**: Your private GitHub repo contains 100% of your homelab code and encrypted credentials. Without your single master key, the repository is useless to an attacker.

---

## 2. Generating & Managing Your Master Key

### Step A: Install SOPS and Age (On Workstation)
```bash
# Ubuntu / Debian
sudo apt install -y age sops

# macOS
brew install age sops
```

### Step B: Generate Your Master Key Pair
```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
```
> ⚠️ **CRITICAL STEP**: Copy the private key contents of `~/.config/sops/age/keys.txt` (starting with `AGE-SECRET-KEY-1...`) and save it in your **Password Manager**. This single key decrypts your entire homelab backup!

### Step C: Get Your Public Recipient Key
```bash
age-keygen -y ~/.config/sops/age/keys.txt
# Output example: age1ql8z...
```

---

## 3. Encrypting Secrets before Git Commit

### Step A: Configure `.sops.yaml` in Repository Root
Create `.sops.yaml`:
```yaml
creation_rules:
  - path_regex: .*\.enc\.ya?ml$
    age: "YOUR_PUBLIC_AGE_KEY_HERE"
  - path_regex: .*\.enc\.json$
    age: "YOUR_PUBLIC_AGE_KEY_HERE"
```

### Step B: Encrypting Secret Files
```bash
# Encrypt an environment or config file
sops -e network-routing/adguard-dns/secrets.yaml > network-routing/adguard-dns/secrets.enc.yaml

# Encrypt Nginx Proxy Manager SQLite database dump
sops -e network-routing/nginx-proxy-manager/npm-db.sql > network-routing/nginx-proxy-manager/npm-db.enc.sql
```

---

## 4. Disaster Recovery & Single-Key Restoration

If your hardware fails or you deploy to a fresh server:

### Step 1: Clone Private Repository
```bash
git clone https://github.com/your-user/homelab-infrastructure.git
cd homelab-infrastructure
```

### Step 2: Restore Master Secret Key
```bash
mkdir -p ~/.config/sops/age
echo "YOUR_SAVED_AGE_SECRET_KEY_FROM_PASSWORD_MANAGER" > ~/.config/sops/age/keys.txt
```

### Step 3: Decrypt All Configs Instantly
```bash
# Decrypt AdGuard Home secrets
sops -d network-routing/adguard-dns/secrets.enc.yaml > network-routing/adguard-dns/secrets.yaml

# Decrypt Nginx Proxy Manager database
sops -d network-routing/nginx-proxy-manager/npm-db.enc.sql > network-routing/nginx-proxy-manager/npm-db.sql
```
