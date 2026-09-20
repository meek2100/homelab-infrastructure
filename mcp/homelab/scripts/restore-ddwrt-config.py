#!/usr/bin/env python3
"""
DD-WRT Disaster Recovery & Push-Restore Tool
Restores NVRAM settings, startup/firewall scripts, cron jobs, and custom
PIA VPN watchdogs/credentials back to the DD-WRT router over SSH.
"""

import argparse
import base64
import json
import os
import shutil
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DDWRT_BASE_DIR = os.path.join(REPO_ROOT, "infrastructure", "network", "ddwrt")
SOPS_BINARY = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")

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
        os.path.expanduser("~/.ssh/ddwrt_id_ed25519"),
        "/home/dtheurer/.ssh/ddwrt_id_ed25519",
        "/mnt/c/Users/dtheurer/.ssh/ddwrt_id_ed25519",
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh(ip, cmd, user="root", timeout=30):
    key = get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    ]
    if key: ssh_args.extend(["-i", key])
    ssh_args.extend([f"{user}@{ip}", cmd])
    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)

def decrypt_sops(enc_file_path):
    if not os.path.exists(SOPS_BINARY):
        raise RuntimeError(f"SOPS binary not found at {SOPS_BINARY}")
    env = os.environ.copy()
    key_file = get_age_key_path()
    if key_file:
        env["SOPS_AGE_KEY_FILE"] = key_file
    res = subprocess.run([SOPS_BINARY, "-d", enc_file_path], capture_output=True, text=True, env=env, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"SOPS decryption failed: {res.stderr.strip()}")
    return res.stdout

def push_file_to_ddwrt(ip, target_remote_path, content, mode=None, user="root"):
    b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    parent_dir = os.path.dirname(target_remote_path)
    remote_script = f"mkdir -p '{parent_dir}' && echo '{b64_content}' | base64 -d > '{target_remote_path}'"
    if mode:
        remote_script += f" && chmod {mode} '{target_remote_path}'"
    code, _, err = run_ssh(ip, remote_script, user=user)
    return code == 0, err

def restore_ddwrt(router="aurora", ip="10.25.25.1", user="root", dry_run=False):
    router_dir = os.path.join(DDWRT_BASE_DIR, router)
    if not os.path.exists(router_dir):
        print(f"❌ No backup directory found for router '{router}' at {router_dir}")
        return

    print(f"🔄 Starting disaster recovery restoration for DD-WRT '{router}' at {ip} (Dry Run: {dry_run})...")

    # Check connection
    code, out, err = run_ssh(ip, "uname -a; nvram get os_version", user=user)
    if code != 0:
        print(f"❌ Cannot connect to DD-WRT router at {ip}: {err.strip()}")
        return

    restored = []

    # 1. Restore startup, firewall, and shutdown scripts to NVRAM
    for script_type in ["rc_startup", "rc_firewall", "rc_shutdown"]:
        spath = os.path.join(router_dir, f"{script_type}.sh")
        if os.path.exists(spath):
            with open(spath, "r", encoding="utf-8") as sf:
                content = sf.read().strip()
            if not dry_run:
                b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
                set_cmd = f"nvram set {script_type}=\"$(echo '{b64}' | base64 -d)\""
                c, _, _ = run_ssh(ip, set_cmd, user=user)
                if c == 0: restored.append(f"NVRAM: {script_type}")
            else:
                restored.append(f"[DRY-RUN] NVRAM: {script_type}")

    # 2. Restore Cron Jobs
    cj_path = os.path.join(router_dir, "cron_jobs.txt")
    if os.path.exists(cj_path):
        with open(cj_path, "r", encoding="utf-8") as cf:
            cj_content = cf.read().strip()
        if not dry_run:
            b64_cj = base64.b64encode(cj_content.encode("utf-8")).decode("utf-8")
            c, _, _ = run_ssh(ip, f"nvram set cron_jobs=\"$(echo '{b64_cj}' | base64 -d)\"", user=user)
            if c == 0: restored.append("NVRAM: cron_jobs")
        else:
            restored.append("[DRY-RUN] NVRAM: cron_jobs")

    # 3. Restore /usr/bin/is-mounted.sh
    ism_path = os.path.join(router_dir, "is-mounted.sh")
    if os.path.exists(ism_path):
        with open(ism_path, "r", encoding="utf-8") as f:
            content = f.read()
        if not dry_run:
            s, _ = push_file_to_ddwrt(ip, "/usr/bin/is-mounted.sh", content, mode="755", user=user)
            if s: restored.append("/usr/bin/is-mounted.sh")
        else:
            restored.append("[DRY-RUN] /usr/bin/is-mounted.sh")

    # 4. Restore /opt/sbin/ PIA scripts
    opt_sbin_dir = os.path.join(router_dir, "opt_sbin")
    if os.path.exists(opt_sbin_dir):
        for sname in os.listdir(opt_sbin_dir):
            spath = os.path.join(opt_sbin_dir, sname)
            with open(spath, "r", encoding="utf-8") as sf:
                content = sf.read()
            remote_target = f"/opt/sbin/{sname}"
            if not dry_run:
                s, _ = push_file_to_ddwrt(ip, remote_target, content, mode="755", user=user)
                if s: restored.append(remote_target)
            else:
                restored.append(f"[DRY-RUN] {remote_target}")

    # 5. Restore /opt/etc/pia-update/ (including decrypted credentials)
    opt_pia_dir = os.path.join(router_dir, "opt_etc_pia_update")
    if os.path.exists(opt_pia_dir):
        for pname in os.listdir(opt_pia_dir):
            ppath = os.path.join(opt_pia_dir, pname)
            if pname.endswith(".enc.yaml"):
                real_name = pname.replace(".enc.yaml", "")
                print(f"  🔓 Decrypting credentials {pname} via SOPS...")
                dec = decrypt_sops(ppath)
                data = json.loads(dec)
                content = data.get("content", "")
            else:
                real_name = pname
                with open(ppath, "r", encoding="utf-8") as pf:
                    content = pf.read()
            remote_target = f"/opt/etc/pia-update/{real_name}"
            if not dry_run:
                s, _ = push_file_to_ddwrt(ip, remote_target, content, mode="600" if "cred" in real_name else "644", user=user)
                if s: restored.append(remote_target)
            else:
                restored.append(f"[DRY-RUN] {remote_target}")

    if not dry_run:
        print("💾 Committing NVRAM changes...")
        run_ssh(ip, "nvram commit", user=user)

    print(f"\n✅ Restored {len(restored)} assets to DD-WRT {router} ({ip}):")
    for r in restored:
        print(f"   ✓ {r}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore DD-WRT configuration.")
    parser.add_argument("--router", default="aurora", help="Router name")
    parser.add_argument("--ip", default="10.25.25.1", help="Router IP")
    parser.add_argument("--user", default="root", help="SSH user")
    parser.add_argument("--dry-run", action="store_true", help="Simulate restore")
    args = parser.parse_args()
    restore_ddwrt(router=args.router, ip=args.ip, user=args.user, dry_run=args.dry_run)
