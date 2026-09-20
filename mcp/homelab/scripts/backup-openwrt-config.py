#!/usr/bin/env python3
"""
OpenWrt Router Configuration Backup & GitOps Tool
Extracts /etc/config/ files from OpenWrt (192.168.1.225) over SSH,
encrypts sensitive credentials with SOPS + age, and stages them in git.
"""

import argparse
import json
import os
import shutil
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OPENWRT_DEFAULT_IP = "192.168.1.225"
OPENWRT_TARGET_DIR = os.path.join(REPO_ROOT, "infrastructure", "network", "openwrt")

SOPS_BINARY = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
AGE_PUBKEY = "age1yqmzhsl58talkkax7g6xwj9xs68rqm2efxa5z0zg2u566m3dzeusj96x5f"

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
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/dtheurer/.ssh/proxmox_ed25519",
        "/home/agentsvc/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519",
        "/home/agentsvc/.ssh/id_ed25519",
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
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "SSH connection timed out"
    except Exception as e:
        return 1, "", str(e)

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
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"SOPS encryption failed: {res.stderr.strip()}")

def backup_openwrt(ip=OPENWRT_DEFAULT_IP, user="root"):
    print(f"📡 Connecting to OpenWrt at {ip} as {user}...")
    code, out, err = run_ssh(ip, "cat /etc/openwrt_release 2>/dev/null || cat /etc/os-release", user=user)
    if code != 0 or not out:
        print(f"❌ Failed to reach OpenWrt at {ip}: {err.strip()}")
        return f"Error connecting to OpenWrt at {ip}: {err.strip()}"

    os_info = {}
    for line in out.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            os_info[k.strip()] = v.strip().strip('"')

    distrib = os_info.get("DISTRIB_DESCRIPTION") or os_info.get("PRETTY_NAME", "OpenWrt")
    print(f"✓ Detected OpenWrt: {distrib}")

    # List all files in /etc/config/
    code_list, out_list, _ = run_ssh(ip, "ls -1 /etc/config/", user=user)
    if code_list != 0 or not out_list:
        return f"Error listing /etc/config/ on OpenWrt {ip}"

    config_names = [f.strip() for f in out_list.strip().splitlines() if f.strip()]
    print(f"✓ Discovered {len(config_names)} configuration modules: {', '.join(config_names)}")

    configs_dir = os.path.join(OPENWRT_TARGET_DIR, "configs")
    os.makedirs(configs_dir, exist_ok=True)

    # Metadata file
    meta = {
        "ip": ip,
        "user": user,
        "distribution": distrib,
        "config_count": len(config_names),
        "modules": config_names
    }
    with open(os.path.join(OPENWRT_TARGET_DIR, "meta.json"), "w", encoding="utf-8") as mf:
        json.dump(meta, mf, indent=2)

    sensitive_modules = ["wireless", "network", "firewall", "dropbear", "passwords", "sqm"]
    backed_up = []

    for mod in config_names:
        c_code, c_out, _ = run_ssh(ip, f"cat /etc/config/{mod}", user=user)
        if c_code != 0:
            continue

        target_plain = os.path.join(configs_dir, mod)
        with open(target_plain, "w", encoding="utf-8") as f:
            f.write(c_out)

        # Check if sensitive; if so, encrypt with SOPS
        if mod in sensitive_modules:
            enc_target = os.path.join(configs_dir, f"{mod}.enc.yaml")
            try:
                # Convert UCI plain key-value format to a structured dictionary for SOPS
                structured = {"raw_uci": c_out, "module": mod}
                tmp_json = target_plain + ".tmp.json"
                with open(tmp_json, "w", encoding="utf-8") as tf:
                    json.dump(structured, tf, indent=2)
                encrypt_file_sops(tmp_json, enc_target)
                if os.path.exists(tmp_json):
                    os.remove(tmp_json)
                if os.path.exists(target_plain):
                    os.remove(target_plain)
                backed_up.append(f"{mod} (encrypted)")
            except Exception as e:
                backed_up.append(f"{mod} (plain)")
        else:
            backed_up.append(f"{mod} (plain)")

    summary = f"✅ Successfully backed up {len(backed_up)} OpenWrt modules from {ip} ({distrib}) into {configs_dir}."
    print(summary)
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup OpenWrt configurations.")
    parser.add_argument("--ip", default=OPENWRT_DEFAULT_IP, help="OpenWrt IP address")
    parser.add_argument("--user", default="root", help="SSH username")
    args = parser.parse_args()
    backup_openwrt(ip=args.ip, user=args.user)
