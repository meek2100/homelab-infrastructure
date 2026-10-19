#!/usr/bin/env python3
"""
manage-family-secrets.py
========================
Automated zero-trust backup and recovery for Family Assistant credentials and tokens.
Encrypts ~/.config/homelab-todo/ into infrastructure/secrets/family-assistant-secrets.enc.yaml
using the homelab master age public key.

Usage:
    .venv/bin/python3 manage-family-secrets.py backup
    .venv/bin/python3 manage-family-secrets.py restore [--force]
    .venv/bin/python3 manage-family-secrets.py status
"""

import os
import sys
import argparse
import subprocess
import shutil
import tempfile
import hashlib
import yaml

def find_repo_root():
    cur = os.path.dirname(os.path.abspath(__file__))
    while cur and cur != "/":
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        cur = os.path.dirname(cur)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

REPO_ROOT = find_repo_root()
CONFIG_DIR = os.path.expanduser("~/.config/homelab-todo")
ENC_SECRETS_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "family-assistant-secrets.enc.yaml")
SOPS_BINARY = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
AGE_PUBKEY = "age1yqmzhsl58talkkax7g6xwj9xs68rqm2efxa5z0zg2u566m3dzeusj96x5f"


def get_age_key_path():
    for candidate in [
        os.path.join(REPO_ROOT, "homelab-infrastructure.key"),
        os.path.join(REPO_ROOT, "master-age-key.txt"),
        os.path.expanduser("~/.config/sops/age/keys.txt"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return None


def get_sops_env():
    env = os.environ.copy()
    key_file = get_age_key_path()
    if key_file:
        env["SOPS_AGE_KEY_FILE"] = key_file
    return env


def compute_fingerprint(data_str: str) -> str:
    """Return first 12 hex characters of SHA-256 for secret hygiene."""
    return hashlib.sha256(data_str.encode("utf-8")).hexdigest()[:12]


def backup_secrets():
    print(f"🔒 Scanning Family Assistant credentials in {CONFIG_DIR}...")
    if not os.path.exists(CONFIG_DIR):
        print(f"❌ Error: Config directory {CONFIG_DIR} does not exist.")
        sys.exit(1)

    if not os.path.exists(SOPS_BINARY):
        print(f"❌ Error: SOPS binary not found at {SOPS_BINARY}")
        sys.exit(1)

    files_to_backup = {}
    for entry in sorted(os.listdir(CONFIG_DIR)):
        full_path = os.path.join(CONFIG_DIR, entry)
        if os.path.isfile(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            fp = compute_fingerprint(content)
            files_to_backup[entry] = content
            print(f"  • {entry} ({len(content)} bytes, sha256:{fp}...)")

    if not files_to_backup:
        print("⚠️ No credential files found to back up.")
        return

    payload = {
        "version": "1.0",
        "files": files_to_backup
    }

    # Write plaintext payload to temporary file for SOPS encryption
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        yaml.dump(payload, tmp, default_flow_style=False)
        tmp_path = tmp.name

    try:
        os.makedirs(os.path.dirname(ENC_SECRETS_FILE), exist_ok=True)
        env = get_sops_env()
        cmd = [
            SOPS_BINARY, "--encrypt",
            "--age", AGE_PUBKEY,
            "--output", ENC_SECRETS_FILE,
            tmp_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if res.returncode != 0:
            print(f"❌ SOPS encryption failed: {res.stderr.strip()}")
            sys.exit(1)

        print(f"✅ Successfully encrypted {len(files_to_backup)} files into:")
        print(f"   {ENC_SECRETS_FILE}")
        print("💡 This file is safe to commit to Git. Only the master key can decrypt it.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def restore_secrets(force=False):
    print(f"🔓 Restoring Family Assistant secrets from {ENC_SECRETS_FILE}...")
    if not os.path.exists(ENC_SECRETS_FILE):
        print(f"❌ Error: Encrypted secrets file not found: {ENC_SECRETS_FILE}")
        sys.exit(1)

    key_file = get_age_key_path()
    if not key_file:
        print("❌ Error: Master age decryption key not found!")
        print("   Ensure 'homelab-infrastructure.key' is in the repo root or ~/.config/sops/age/keys.txt")
        sys.exit(1)

    if not os.path.exists(SOPS_BINARY):
        print(f"❌ Error: SOPS binary not found at {SOPS_BINARY}")
        sys.exit(1)

    env = get_sops_env()
    cmd = [SOPS_BINARY, "-d", ENC_SECRETS_FILE]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        print(f"❌ SOPS decryption failed: {res.stderr.strip()}")
        sys.exit(1)

    try:
        data = yaml.safe_load(res.stdout)
    except Exception as e:
        print(f"❌ Failed to parse decrypted YAML: {e}")
        sys.exit(1)

    files = data.get("files", {})
    if not files:
        print("⚠️ No files found in decrypted archive.")
        return

    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)

    restored_count = 0
    for filename, content in files.items():
        target_path = os.path.join(CONFIG_DIR, filename)
        if os.path.exists(target_path) and not force:
            with open(target_path, "r", encoding="utf-8") as f:
                cur_content = f.read()
            if cur_content == content:
                print(f"  • {filename}: Identical, skipped")
                continue
            else:
                print(f"  • {filename}: Exists with different content (use --force to overwrite)")
                continue

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(target_path, 0o600)
        fp = compute_fingerprint(content)
        print(f"  ✅ Restored {filename} (mode 0600, sha256:{fp}...)")
        restored_count += 1

    print(f"🎉 Restoration complete! ({restored_count} files written to {CONFIG_DIR})")


def check_status():
    print(f"🔍 Checking Family Assistant secrets status...")
    if not os.path.exists(ENC_SECRETS_FILE):
        print(f"❌ Encrypted bundle {ENC_SECRETS_FILE} DOES NOT EXIST.")
        print(f"   Run: .venv/bin/python3 manage-family-secrets.py backup")
        return

    key_file = get_age_key_path()
    if not key_file:
        print(f"⚠️ Master age key not found. Encrypted bundle exists at {ENC_SECRETS_FILE}, but cannot verify decryption.")
        return

    env = get_sops_env()
    res = subprocess.run([SOPS_BINARY, "-d", ENC_SECRETS_FILE], capture_output=True, text=True, env=env)
    if res.returncode != 0:
        print(f"❌ Failed to decrypt {ENC_SECRETS_FILE}: {res.stderr.strip()}")
        return

    data = yaml.safe_load(res.stdout)
    enc_files = data.get("files", {})
    print(f"📦 Encrypted bundle contains {len(enc_files)} files.")

    if not os.path.exists(CONFIG_DIR):
        print(f"⚠️ Local directory {CONFIG_DIR} does not exist. Run restore to recreate.")
        return

    local_files = [f for f in os.listdir(CONFIG_DIR) if os.path.isfile(os.path.join(CONFIG_DIR, f))]
    all_names = sorted(set(list(enc_files.keys()) + local_files))

    synced = True
    for name in all_names:
        in_bundle = name in enc_files
        in_local = name in local_files
        if in_bundle and in_local:
            with open(os.path.join(CONFIG_DIR, name), "r", encoding="utf-8") as f:
                local_content = f.read()
            local_fp = compute_fingerprint(local_content)
            enc_fp = compute_fingerprint(enc_files[name])
            if local_fp == enc_fp:
                print(f"  ✅ {name}: In sync (sha256:{local_fp}...)")
            else:
                print(f"  ⚠️ {name}: DRIFT DETECTED (local sha256:{local_fp} vs backup sha256:{enc_fp})")
                synced = False
        elif in_bundle and not in_local:
            print(f"  ❌ {name}: In encrypted bundle, missing locally")
            synced = False
        else:
            print(f"  ⚠️ {name}: Present locally, NOT backed up in bundle")
            synced = False

    if synced:
        print("✨ All credentials and tokens are fully synchronized and backed up.")
    else:
        print("💡 Run 'backup' or 'restore' to resolve drifts.")


def main():
    parser = argparse.ArgumentParser(description="Manage Family Assistant SOPS Secrets")
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("backup", help="Encrypt and backup ~/.config/homelab-todo into repo")

    restore_p = subparsers.add_parser("restore", help="Decrypt and restore files into ~/.config/homelab-todo")
    restore_p.add_argument("--force", action="store_true", help="Force overwrite existing files")

    subparsers.add_parser("status", help="Compare local files against encrypted backup")

    args = parser.parse_args()

    if args.action == "backup":
        backup_secrets()
    elif args.action == "restore":
        restore_secrets(force=args.force)
    elif args.action == "status":
        check_status()


if __name__ == "__main__":
    main()
