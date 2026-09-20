#!/usr/bin/env python3
"""
DD-WRT Router Configuration Backup & GitOps Tool
Connects to DD-WRT routers (aurora: 10.25.25.1, luna: 10.20.20.1) over SSH,
extracts NVRAM configurations and custom scripts, encrypts sensitive data with SOPS,
and archives them into infrastructure/network/ddwrt/.
"""

import argparse
import json
import os
import shutil
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DDWRT_TARGET_DIR = os.path.join(REPO_ROOT, "infrastructure", "network", "ddwrt")

SOPS_BINARY = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
AGE_PUBKEY = "age1yqmzhsl58talkkax7g6xwj9xs68rqm2efxa5z0zg2u566m3dzeusj96x5f"

ROUTER_PROFILES = {
    "aurora": {
        "ip": "10.25.25.1",
        "user": "root",
        "role": "WAN2 Isolation & Discovery Network Gateway"
    },
    "luna": {
        "ip": "10.20.20.1",
        "user": "meek2100",
        "role": "Upstream DD-WRT Gateway (Transit 10.20.20.0/24)"
    }
}

def get_age_key_path():
    candidates = [
        os.path.join(REPO_ROOT, "homelab-infrastructure.key"),
        os.path.join(REPO_ROOT, "master-age-key.txt"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def get_ssh_key():
    for candidate in [
        "/home/dtheurer/.ssh/ddwrt_id_ed25519",
        os.path.expanduser("~/.ssh/ddwrt_id_ed25519"),
        "/mnt/c/Users/dtheurer/.ssh/ddwrt_id_ed25519",
        os.path.expanduser("~/.ssh/pi_id_ed25519"),
        "/home/dtheurer/.ssh/pi_id_ed25519",
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh(ip, cmd, user="root", timeout=30):
    key = get_ssh_key()
    ssh_args = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=8",
    ]
    if key and os.path.exists(key):
        ssh_args.extend(["-i", key])
    ssh_args.extend([f"{user}@{ip}", cmd])

    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "SSH connection timed out"
    except Exception as exc:
        return 1, "", str(exc)

def encrypt_file_sops(source_file, dest_enc_file):
    if not os.path.exists(SOPS_BINARY):
        raise RuntimeError(f"SOPS binary not found at {SOPS_BINARY}")
    env = os.environ.copy()
    key_file = get_age_key_path()
    if key_file:
        env["SOPS_AGE_KEY_FILE"] = key_file

    cmd = [
        SOPS_BINARY, "--encrypt",
        "--age", AGE_PUBKEY,
        "--output", dest_enc_file,
        source_file
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"SOPS encryption failed: {res.stderr.strip()}")

def backup_ddwrt_router(name: str, ip: str, user: str):
    router_dir = os.path.join(DDWRT_TARGET_DIR, name)
    os.makedirs(router_dir, exist_ok=True)
    print(f"📡 Connecting to DD-WRT router '{name}' at {ip} as {user}...")

    # Query system info
    code, out, err = run_ssh(ip, "uname -a; nvram get os_version 2>/dev/null", user=user)
    if code != 0:
        print(f"❌ Failed to reach {name} ({ip}): {err.strip()}")
        return f"Error connecting to {name} at {ip}: {err.strip()}"

    print(f"✓ Connected to {name} ({ip}). Archiving NVRAM and scripts...")

    # Backup NVRAM variables
    code_nv, out_nv, _ = run_ssh(ip, "nvram show 2>/dev/null", user=user)
    if code_nv == 0 and out_nv:
        raw_nvram_path = os.path.join(router_dir, "nvram.raw.tmp")
        enc_nvram_path = os.path.join(router_dir, "nvram.enc.yaml")
        
        # Structure for SOPS
        structured = {
            "router": name,
            "ip": ip,
            "raw_nvram": out_nv
        }
        with open(raw_nvram_path, "w", encoding="utf-8") as rf:
            json.dump(structured, rf, indent=2)
        
        try:
            encrypt_file_sops(raw_nvram_path, enc_nvram_path)
            if os.path.exists(raw_nvram_path):
                os.remove(raw_nvram_path)
            print(f"✓ NVRAM encrypted with SOPS -> {enc_nvram_path}")
        except Exception as e:
            print(f"⚠️ SOPS encryption warning: {e}, keeping plain text")
            os.rename(raw_nvram_path, os.path.join(router_dir, "nvram.txt"))

    # Backup startup and firewall scripts
    for script_type in ["rc_startup", "rc_firewall", "rc_shutdown"]:
        code_s, out_s, _ = run_ssh(ip, f"nvram get {script_type} 2>/dev/null", user=user)
        if code_s == 0 and out_s.strip():
            with open(os.path.join(router_dir, f"{script_type}.sh"), "w", encoding="utf-8") as sf:
                sf.write(out_s)

    # Check for /jffs/ files
    code_j, out_j, _ = run_ssh(ip, "[ -d /jffs ] && ls -la /jffs/ 2>/dev/null || echo '__NO_JFFS__'", user=user)
    if code_j == 0 and "__NO_JFFS__" not in out_j:
        with open(os.path.join(router_dir, "jffs_listing.txt"), "w", encoding="utf-8") as jf:
            jf.write(out_j)

    meta = {
        "router": name,
        "ip": ip,
        "user": user,
        "role": ROUTER_PROFILES.get(name, {}).get("role", "DD-WRT Node")
    }
    with open(os.path.join(router_dir, "meta.json"), "w", encoding="utf-8") as mf:
        json.dump(meta, mf, indent=2)

    return f"✅ Successfully backed up DD-WRT router '{name}' ({ip}) into {router_dir}"

def backup_all_ddwrt():
    results = []
    for name, prof in ROUTER_PROFILES.items():
        res = backup_ddwrt_router(name, prof["ip"], prof["user"])
        results.append(res)
    return "\n".join(results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup DD-WRT configurations.")
    parser.add_argument("--router", choices=["aurora", "luna", "all"], default="all", help="Target router")
    args = parser.parse_args()

    if args.router == "all":
        print(backup_all_ddwrt())
    else:
        p = ROUTER_PROFILES[args.router]
        print(backup_ddwrt_router(args.router, p["ip"], p["user"]))
