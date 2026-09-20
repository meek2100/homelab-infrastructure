#!/usr/bin/env python3
"""
Homelab Docker Stacks Restoration Tool
Restores Portainer Docker stacks, decrypts SOPS age secrets, recreates compose environments,
and starts containers via QEMU Guest Agent on target Proxmox nodes.
"""

import os
import sys
import glob
import subprocess
import json
import argparse
import base64
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
INFRA_DIR = os.path.join(REPO_ROOT, "infrastructure")
HOSTS_DIR = os.path.join(INFRA_DIR, "hosts")
STACKS_DIR = os.path.join(INFRA_DIR, "docker-stacks")

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
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/dtheurer/.ssh/proxmox_ed25519",
        "/home/agentsvc/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519",
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh(host_ip, cmd, identity_file=None, timeout=120):
    key = identity_file or get_ssh_key()
    ssh_args = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key:
        ssh_args.extend(["-i", key])
    ssh_args.extend([f"root@{host_ip}", cmd])

    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)

def run_qga_cmd(host_ip, vmid, inner_cmd, identity_file=None, timeout=120):
    cmd = f"qm guest exec {vmid} -- sh -c \"{inner_cmd}\""
    code, stdout, stderr = run_ssh(host_ip, cmd, identity_file=identity_file, timeout=timeout)
    if code != 0:
        return None, stderr or f"SSH error {code}"
    try:
        data = json.loads(stdout)
        exitcode = data.get("exitcode", 0)
        out_data = data.get("out-data", "")
        err_data = data.get("err-data", "")
        if exitcode != 0:
            return None, err_data or out_data or f"Exit code {exitcode}"
        return out_data, None
    except Exception:
        return stdout, None

def decrypt_secrets(secrets_path):
    key_file = get_age_key_path()
    if not key_file or not os.path.exists(key_file):
        raise RuntimeError(f"Master age key not found. Ensure homelab-infrastructure.key exists.")
    if not os.path.exists(SOPS_BINARY):
        raise RuntimeError(f"SOPS binary not found at {SOPS_BINARY}")

    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = key_file

    cmd = [SOPS_BINARY, "--decrypt", "--output-type", "dotenv", secrets_path]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"SOPS decryption failed: {res.stderr.strip()}")
    return res.stdout

def restore_stacks(target_node=None, target_vmid=None, target_stack=None, dry_run=False, identity_file=None):
    key_file = get_age_key_path()
    if not key_file:
        print("❌ Error: Master age key not found in repository root (homelab-infrastructure.key)")
        sys.exit(1)

    stack_dirs = sorted(glob.glob(os.path.join(STACKS_DIR, "*", "*")))
    valid_stacks = []

    for s_dir in stack_dirs:
        deploy_file = os.path.join(s_dir, "deploy.json")
        compose_file = os.path.join(s_dir, "docker-compose.yml")
        if os.path.exists(deploy_file) and os.path.exists(compose_file):
            valid_stacks.append(s_dir)

    print(f"📦 Found {len(valid_stacks)} Docker stack blueprints.")

    # Cache host IPs from meta.json
    node_ips = {}
    for h in ["pve", "pve2", "pve3"]:
        meta_p = os.path.join(HOSTS_DIR, h, "meta.json")
        if os.path.exists(meta_p):
            with open(meta_p, 'r') as f:
                node_ips[h] = json.load(f).get("ip")

    matched_count = 0
    restored_count = 0

    for s_dir in valid_stacks:
        with open(os.path.join(s_dir, "deploy.json"), 'r') as f:
            deploy_info = json.load(f)

        node_name = deploy_info.get("node")
        vmid = deploy_info.get("vmid")
        stack_id = os.path.basename(s_dir)
        vm_name = os.path.basename(os.path.dirname(s_dir))

        if target_node and node_name != target_node:
            continue
        if target_vmid and int(vmid) != int(target_vmid):
            continue
        if target_stack and str(stack_id) != str(target_stack):
            continue

        matched_count += 1
        host_ip = node_ips.get(node_name)
        if not host_ip:
            print(f"  ❌ Unknown IP for host node '{node_name}'. Skipping stack {stack_id}.")
            continue

        compose_path = os.path.join(s_dir, "docker-compose.yml")
        secrets_path = os.path.join(s_dir, "secrets.enc.yaml")

        remote_path = deploy_info.get("remote_path")
        if remote_path:
            target_compose_dir = os.path.dirname(remote_path)
        else:
            target_compose_dir = f"/var/lib/docker/volumes/portainer_data/_data/compose/{stack_id}"

        print(f"\n🚀 Restoring Stack {stack_id} on VM {vmid} ({vm_name}) on {node_name} ({host_ip})...")
        print(f"   Target path: {target_compose_dir}")

        with open(compose_path, 'r', encoding='utf-8') as cf:
            compose_content = cf.read()

        decrypted_dotenv = ""
        if os.path.exists(secrets_path):
            try:
                decrypted_dotenv = decrypt_secrets(secrets_path)
                print(f"   ✓ Successfully decrypted SOPS secrets for stack {stack_id}")
            except Exception as e:
                print(f"   ❌ Failed to decrypt secrets for stack {stack_id}: {e}")
                continue

        if dry_run:
            print(f"   [DRY RUN] Would create directory: {target_compose_dir}")
            print(f"   [DRY RUN] Would write: {target_compose_dir}/docker-compose.yml ({len(compose_content)} bytes)")
            if decrypted_dotenv:
                print(f"   [DRY RUN] Would write: {target_compose_dir}/stack.env ({len(decrypted_dotenv)} bytes)")
            print(f"   [DRY RUN] Would execute: docker compose up -d")
            restored_count += 1
            continue

        # 1. Base64 payload encoding
        b64_compose = base64.b64encode(compose_content.encode('utf-8')).decode('ascii')
        write_compose_cmd = (
            f"mkdir -p '{target_compose_dir}' && "
            f"echo '{b64_compose}' | base64 -d > '{target_compose_dir}/docker-compose.yml'"
        )

        res_compose, err_compose = run_qga_cmd(host_ip, vmid, write_compose_cmd, identity_file=identity_file)
        if res_compose is None:
            print(f"   ❌ Failed to write docker-compose.yml via QGA on VM {vmid}: {err_compose}")
            continue

        # 2. Write stack.env if exists
        if decrypted_dotenv:
            b64_env = base64.b64encode(decrypted_dotenv.encode('utf-8')).decode('ascii')
            write_env_cmd = f"echo '{b64_env}' | base64 -d > '{target_compose_dir}/stack.env'"
            res_env, err_env = run_qga_cmd(host_ip, vmid, write_env_cmd, identity_file=identity_file)
            if res_env is None:
                print(f"   ❌ Failed to write stack.env via QGA on VM {vmid}: {err_env}")
                continue
            print("   ✓ Injected decrypted stack.env")

        # 3. Spin up the containers
        if decrypted_dotenv:
            up_cmd = f"cd '{target_compose_dir}' && docker compose --env-file stack.env up -d"
        else:
            up_cmd = f"cd '{target_compose_dir}' && docker compose up -d"

        print(f"   ⚙️  Executing: {up_cmd}")
        up_out, up_err = run_qga_cmd(host_ip, vmid, up_cmd, identity_file=identity_file, timeout=180)
        if up_out is not None:
            print(f"   ✅ Stack {stack_id} containers started successfully.")
            if up_out.strip():
                for l in up_out.strip().splitlines()[-5:]:
                    print(f"      {l}")
            restored_count += 1
        else:
            print(f"   ❌ Failed to start stack {stack_id} containers via QGA:\n{up_err}")

    print(f"\n✨ Restoration summary: {restored_count}/{matched_count} matched stacks restored successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Homelab Docker Stacks Restoration Tool")
    parser.add_argument("--node", help="Specific Proxmox node (pve, pve2, pve3)", default=None)
    parser.add_argument("--vmid", help="Specific VMID (e.g. 109)", default=None)
    parser.add_argument("--stack", help="Specific Stack ID (e.g. 3)", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Simulate restoration without changes")
    parser.add_argument("-i", "--identity-file", help="Path to SSH identity key", default=None)
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if args.dry_run:
        print("Starting DRY-RUN stack restoration...")
        restore_stacks(args.node, args.vmid, args.stack, dry_run=True, identity_file=args.identity_file)
    elif args.node or args.vmid or args.stack or args.yes:
        restore_stacks(args.node, args.vmid, args.stack, dry_run=False, identity_file=args.identity_file)
    else:
        confirm = input("⚠️  WARNING: This will decrypt secrets and spin up Docker containers on VMs! Proceed? (y/N): ")
        if confirm.lower() == 'y':
            restore_stacks(dry_run=False, identity_file=args.identity_file)
        else:
            print("Aborted.")
