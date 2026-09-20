#!/usr/bin/env python3
"""
OpenWrt Disaster Recovery & Push-Restore Tool
Decrypts SOPS-encrypted configurations and restores all UCI modules,
custom daemons, failover scripts, and system hooks back to the OpenWrt router over SSH.
"""

import argparse
import base64
import json
import os
import shutil
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OPENWRT_DIR = os.path.join(REPO_ROOT, "infrastructure", "network", "openwrt")
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
        "/home/dtheurer/.ssh/pi_id_ed25519",
        os.path.expanduser("~/.ssh/pi_id_ed25519"),
        "/mnt/c/Users/dtheurer/.ssh/pi_id_ed25519",
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
        raise RuntimeError(f"SOPS decryption failed for {enc_file_path}: {res.stderr.strip()}")
    return res.stdout

def push_file_to_openwrt(ip, target_remote_path, content, mode=None, user="root"):
    # Base64 encode to safely transmit without escaping issues
    b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    parent_dir = os.path.dirname(target_remote_path)
    remote_script = f"mkdir -p '{parent_dir}' && echo '{b64_content}' | base64 -d > '{target_remote_path}'"
    if mode:
        remote_script += f" && chmod {mode} '{target_remote_path}'"
    code, _, err = run_ssh(ip, remote_script, user=user)
    return code == 0, err

def restore_openwrt(ip="192.168.1.226", user="root", dry_run=False):
    print(f"🔄 Starting disaster recovery restoration for OpenWrt at {ip} (Dry Run: {dry_run})...")

    # Verify connectivity
    code, out, err = run_ssh(ip, "cat /etc/openwrt_release 2>/dev/null", user=user)
    if code != 0:
        print(f"❌ Cannot connect to OpenWrt at {ip}: {err.strip()}")
        return

    configs_dir = os.path.join(OPENWRT_DIR, "configs")
    restored = []

    # 1. Restore /etc/config/ modules
    if os.path.exists(configs_dir):
        for fname in os.listdir(configs_dir):
            fpath = os.path.join(configs_dir, fname)
            if fname.endswith(".enc.yaml"):
                mod_name = fname.replace(".enc.yaml", "")
                print(f"  🔓 Decrypting {fname} via SOPS...")
                dec_json = decrypt_sops(fpath)
                data = json.loads(dec_json)
                content = data.get("raw_uci", "")
            else:
                mod_name = fname
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()

            remote_target = f"/etc/config/{mod_name}"
            if not dry_run:
                success, err = push_file_to_openwrt(ip, remote_target, content, mode="644", user=user)
                if success:
                    restored.append(f"/etc/config/{mod_name}")
                else:
                    print(f"  ❌ Failed restoring {remote_target}: {err}")
            else:
                restored.append(f"[DRY-RUN] /etc/config/{mod_name}")

    # 2. Restore /etc/scripts/
    scripts_dir = os.path.join(OPENWRT_DIR, "scripts")
    if os.path.exists(scripts_dir):
        for sname in os.listdir(scripts_dir):
            spath = os.path.join(scripts_dir, sname)
            with open(spath, "r", encoding="utf-8") as sf:
                content = sf.read()
            remote_target = f"/etc/scripts/{sname}"
            if not dry_run:
                success, _ = push_file_to_openwrt(ip, remote_target, content, mode="755", user=user)
                if success: restored.append(remote_target)
            else:
                restored.append(f"[DRY-RUN] {remote_target}")

    # 3. Restore custom daemons, hooks, and configs
    custom_dir = os.path.join(OPENWRT_DIR, "custom")
    if os.path.exists(custom_dir):
        mapping = {
            "etc_crontabs_root": ("/etc/crontabs/root", "600"),
            "etc_rc.local": ("/etc/rc.local", "755"),
            "etc_sysupgrade.conf": ("/etc/sysupgrade.conf", "644"),
            "etc_vxlan-nm.conf": ("/etc/vxlan-nm.conf", "644"),
            "etc_init.d_vxlan-nm": ("/etc/init.d/vxlan-nm", "755"),
            "usr_bin_vxlan-nm": ("/usr/bin/vxlan-nm", "755"),
            "usr_bin_failover-tester.py": ("/usr/bin/failover-tester.py", "755"),
        }
        for cfile, (remote_dest, mode) in mapping.items():
            cpath = os.path.join(custom_dir, cfile)
            if os.path.exists(cpath):
                with open(cpath, "r", encoding="utf-8") as cf:
                    content = cf.read()
                if not dry_run:
                    success, _ = push_file_to_openwrt(ip, remote_dest, content, mode=mode, user=user)
                    if success: restored.append(remote_dest)
                else:
                    restored.append(f"[DRY-RUN] {remote_dest}")

    print(f"\n✅ Restored {len(restored)} assets to OpenWrt {ip}:")
    for r in restored:
        print(f"   ✓ {r}")

    if not dry_run:
        print("\n🔄 Restarting network service to apply configuration...")
        run_ssh(ip, "/etc/init.d/network restart", user=user)
        print("🎉 OpenWrt network and services successfully synchronized!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore OpenWrt configuration.")
    parser.add_argument("--ip", default="192.168.1.226", help="OpenWrt IP")
    parser.add_argument("--user", default="root", help="SSH user")
    parser.add_argument("--dry-run", action="store_true", help="Simulate restore without pushing")
    args = parser.parse_args()
    restore_openwrt(ip=args.ip, user=args.user, dry_run=args.dry_run)
