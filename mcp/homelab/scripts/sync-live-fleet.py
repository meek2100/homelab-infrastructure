#!/usr/bin/env python3
"""
Homelab Fleet Synchronization & Drift Discovery Tool
Automated, non-destructive discovery and sync for Proxmox hosts, VMs, and Portainer stacks.
"""

import os
import sys
import json
import subprocess
import argparse
import difflib
import base64
import re
import shutil
import glob

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
INFRA_DIR = os.path.join(REPO_ROOT, "infrastructure")
HOSTS_DIR = os.path.join(INFRA_DIR, "hosts")
VMS_DIR = os.path.join(INFRA_DIR, "vms")
STACKS_DIR = os.path.join(INFRA_DIR, "docker-stacks")
DEFAULT_STAGING = os.path.join(REPO_ROOT, ".live-staging")

NODES = [
    {"node": "pve", "ip": "192.168.1.250"},
    {"node": "pve2", "ip": "192.168.1.240"},
    {"node": "pve3", "ip": "192.168.1.245"},
]

VM_NAME_MAPPINGS = {
    ("pve", 100): "nexus-server",
    ("pve", 102): "luna-server",
    ("pve", 103): "media-server",
    ("pve", 107): "vxlan-server",
    ("pve", 109): "minecraft-docker",
    ("pve2", 100): "discovery-server",
    ("pve3", 100): "nexus-server2",
    ("pve3", 101): "nas-server",
}

SOPS_BINARY = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
AGE_PUBKEY = "age1yqmzhsl58talkkax7g6xwj9xs68rqm2efxa5z0zg2u566m3dzeusj96x5f"

def get_age_key_path():
    p1 = os.path.join(REPO_ROOT, "homelab-infrastructure.key")
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(REPO_ROOT, "master-age-key.txt")
    if os.path.exists(p2):
        return p2
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

def run_ssh(host_ip, cmd, identity_file=None, timeout=60):
    key = identity_file or get_ssh_key()
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key and os.path.exists(key):
        ssh_args.extend(["-i", key])
    ssh_args.extend([f"root@{host_ip}", cmd])
    try:
        res = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "SSH connection timed out"
    except Exception as e:
        return 1, "", str(e)

def run_qga_b64(host_ip, vmid, file_path, identity_file=None):
    cmd = f"qm guest exec {vmid} -- base64 -w 0 '{file_path}'"
    code, stdout, stderr = run_ssh(host_ip, cmd, identity_file=identity_file, timeout=60)

    if code != 0 or not stdout:
        return None
    try:
        payload = json.loads(stdout)
        b64_data = payload.get("out-data", "").strip()
        if not b64_data:
            return None
        return base64.b64decode(b64_data).decode("utf-8", errors="replace")
    except Exception:
        return None

def run_qga_cmd(host_ip, vmid, inner_cmd, identity_file=None, timeout=60):
    cmd = f"qm guest exec {vmid} -- {inner_cmd}"
    code, stdout, stderr = run_ssh(host_ip, cmd, identity_file=identity_file, timeout=timeout)
    if code != 0 or not stdout:
        return None
    try:
        payload = json.loads(stdout)
        return payload.get("out-data", "")
    except Exception:
        return None

def decrypt_sops_yaml(enc_yaml_path):
    key_file = get_age_key_path()
    if not key_file or not os.path.exists(enc_yaml_path) or not os.path.exists(SOPS_BINARY):
        return None
    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = key_file
    cmd = [SOPS_BINARY, "--decrypt", "--output-type", "dotenv", enc_yaml_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    return None

def encrypt_to_sops_yaml(plaintext_env_content, dest_yaml_path):
    key_file = get_age_key_path()
    if not os.path.exists(SOPS_BINARY):
        raise RuntimeError(f"SOPS binary not found at {SOPS_BINARY}")
    env = os.environ.copy()
    if key_file:
        env["SOPS_AGE_KEY_FILE"] = key_file

    tmp_env_path = dest_yaml_path + ".tmp.env"
    with open(tmp_env_path, "w", encoding="utf-8") as f:
        f.write(plaintext_env_content)

    try:
        cmd = [
            SOPS_BINARY, "--encrypt",
            "--age", AGE_PUBKEY,
            "--input-type", "dotenv",
            "--output-type", "yaml",
            tmp_env_path
        ]
        with open(dest_yaml_path, "w", encoding="utf-8") as out_f:
            res = subprocess.run(cmd, stdout=out_f, stderr=subprocess.PIPE, text=True, env=env)
        if res.returncode != 0:
            raise RuntimeError(f"SOPS encryption failed: {res.stderr}")
    finally:
        if os.path.exists(tmp_env_path):
            os.remove(tmp_env_path)

def audit_node(node_info, staging_dir, identity_file=None):
    node = node_info["node"]
    ip = node_info["ip"]
    print(f"\n📡 Connecting to Proxmox Node: {node} ({ip})...")

    node_stage = os.path.join(staging_dir, "hosts", node)
    os.makedirs(node_stage, exist_ok=True)

    code, stdout, stderr = run_ssh(ip, "pveversion", identity_file=identity_file)
    if code != 0:
        print(f"  ❌ Failed to reach {node} ({ip}): {stderr.strip() or 'Exit code ' + str(code)}")
        return None

    pve_ver = stdout.strip()
    print(f"  ✓ Connected: {pve_ver}")

    # Host interfaces
    code, stdout, _ = run_ssh(ip, "cat /etc/network/interfaces", identity_file=identity_file)
    if code == 0:
        with open(os.path.join(node_stage, "interfaces"), "w") as f:
            f.write(stdout)

    # Storage config
    code, stdout, _ = run_ssh(ip, "cat /etc/pve/storage.cfg", identity_file=identity_file)
    if code == 0:
        with open(os.path.join(node_stage, "storage.cfg"), "w") as f:
            f.write(stdout)

    # Qemu-server VM configs
    qemu_stage = os.path.join(node_stage, "qemu-server")
    os.makedirs(qemu_stage, exist_ok=True)
    code, stdout, _ = run_ssh(ip, "ls -1 /etc/pve/qemu-server/*.conf 2>/dev/null", identity_file=identity_file)
    conf_files = stdout.strip().split("\n") if code == 0 and stdout.strip() else []

    for cf in conf_files:
        if not cf: continue
        vmid_m = re.search(r'/(\d+)\.conf', cf)
        if vmid_m:
            vmid = vmid_m.group(1)
            _, c_out, _ = run_ssh(ip, f"cat '{cf}'", identity_file=identity_file)
            if c_out:
                with open(os.path.join(qemu_stage, f"{vmid}.conf"), "w") as f:
                    f.write(c_out)

    # VM List
    code, qm_out, _ = run_ssh(ip, "qm list", identity_file=identity_file)

    vms = []
    if code == 0 and qm_out:
        lines = qm_out.strip().split("\n")
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 3:
                try:
                    vmid = int(parts[0])
                    name = parts[1]
                    status = parts[2]
                    vms.append({"vmid": vmid, "name": name, "status": status})
                except ValueError:
                    pass

    print(f"  ✓ Discovered {len(vms)} VMs on {node}: {', '.join(f'{v['vmid']}:{v['name']} ({v['status']})' for v in vms)}")
    return {
        "node": node,
        "ip": ip,
        "pve_ver": pve_ver,
        "vms": vms,
        "stage_dir": node_stage
    }

def audit_vm_docker(node_info, vm, staging_dir, identity_file=None):
    node = node_info["node"]
    ip = node_info["ip"]
    vmid = vm["vmid"]
    vm_name = VM_NAME_MAPPINGS.get((node, vmid), vm["name"])

    if vm["status"] != "running":
        print(f"  - VM {vmid} ({vm_name}) is {vm['status']}. Skipping Docker audit.")
        return []

    # Check QGA
    who = run_qga_cmd(ip, vmid, "whoami", identity_file=identity_file)
    if not who:
        print(f"  - VM {vmid} ({vm_name}): QEMU Guest Agent not responding. Skipping.")
        return []

    print(f"\n🐳 Auditing Docker & Portainer on VM {vmid} ({vm_name}) on {node}...")

    find_out = run_qga_cmd(ip, vmid, "find /var/lib/docker/volumes/portainer_data/_data/compose/ -name docker-compose.yml 2>/dev/null", identity_file=identity_file)
    if not find_out:
        print(f"  - No Portainer stacks found on VM {vmid}.")
        return []

    lines = [l.strip() for l in find_out.split("\n") if l.strip().endswith("docker-compose.yml")]
    stacks_raw = {}
    pat = re.compile(r"/compose/(\d+)/(?:(v\d+)/)?docker-compose\.yml")

    for l in lines:
        m = pat.search(l)
        if m:
            s_id = m.group(1)
            v_str = m.group(2) or "v1"
            v_num = int(v_str.lstrip("v")) if v_str.startswith("v") else 1
            if s_id not in stacks_raw or v_num > stacks_raw[s_id]["ver_num"]:
                stacks_raw[s_id] = {
                    "ver_num": v_num,
                    "ver_str": v_str,
                    "yml_path": l,
                    "env_path": l.replace("docker-compose.yml", "stack.env")
                }

    print(f"  ✓ Discovered {len(stacks_raw)} Portainer stacks in VM {vmid}.")

    results = []
    vm_stage_dir = os.path.join(staging_dir, "docker-stacks", vm_name)
    os.makedirs(vm_stage_dir, exist_ok=True)

    for s_id, info in sorted(stacks_raw.items(), key=lambda x: int(x[0])):
        s_stage = os.path.join(vm_stage_dir, s_id)
        os.makedirs(s_stage, exist_ok=True)

        compose_content = run_qga_b64(ip, vmid, info["yml_path"], identity_file=identity_file)
        env_content = run_qga_b64(ip, vmid, info["env_path"], identity_file=identity_file)


        if compose_content:
            with open(os.path.join(s_stage, "docker-compose.yml"), "w", encoding="utf-8") as f:
                f.write(compose_content)

        if env_content and env_content.strip():
            with open(os.path.join(s_stage, "stack.env"), "w", encoding="utf-8") as f:
                f.write(env_content)

        deploy_info = {
            "node": node,
            "vmid": vmid,
            "version": info["ver_str"],
            "remote_path": info["yml_path"]
        }
        with open(os.path.join(s_stage, "deploy.json"), "w") as f:
            json.dump(deploy_info, f, indent=2)

        results.append({
            "vm_name": vm_name,
            "vmid": vmid,
            "node": node,
            "stack_id": s_id,
            "version": info["ver_str"],
            "has_compose": bool(compose_content),
            "has_env": bool(env_content and env_content.strip()),
            "stage_path": s_stage
        })

    return results

def compute_diffs(staging_dir):
    diffs = {
        "hosts": [],
        "vm_configs": [],
        "docker_stacks": []
    }

    # Host interfaces & storage
    for node in ["pve", "pve2", "pve3"]:
        node_stage = os.path.join(staging_dir, "hosts", node)
        if not os.path.exists(node_stage): continue

        for fname in ["interfaces", "storage.cfg"]:
            staged_file = os.path.join(node_stage, fname)
            repo_file = os.path.join(HOSTS_DIR, node, "configs", fname)
            if not os.path.exists(staged_file): continue

            with open(staged_file, 'r', encoding='utf-8') as f:
                staged_text = f.read()

            repo_text = ""
            if os.path.exists(repo_file):
                with open(repo_file, 'r', encoding='utf-8') as f:
                    repo_text = f.read()

            if staged_text.strip() != repo_text.strip():
                diff = list(difflib.unified_diff(
                    repo_text.splitlines(keepends=True),
                    staged_text.splitlines(keepends=True),
                    fromfile=f"repo/{node}/{fname}",
                    tofile=f"live/{node}/{fname}"
                ))
                diffs["hosts"].append({
                    "node": node,
                    "file": fname,
                    "diff": "".join(diff[:50])
                })

        # VM configs in qemu-server
        qemu_stage = os.path.join(node_stage, "qemu-server")
        if os.path.exists(qemu_stage):
            for cf in glob.glob(os.path.join(qemu_stage, "*.conf")):
                cf_name = os.path.basename(cf)
                repo_cf = os.path.join(HOSTS_DIR, node, "configs", "qemu-server", cf_name)

                with open(cf, 'r', encoding='utf-8') as f:
                    staged_conf = f.read()

                repo_conf = ""
                if os.path.exists(repo_cf):
                    with open(repo_cf, 'r', encoding='utf-8') as f:
                        repo_conf = f.read()

                if staged_conf.strip() != repo_conf.strip():
                    diff = list(difflib.unified_diff(
                        repo_conf.splitlines(keepends=True),
                        staged_conf.splitlines(keepends=True),
                        fromfile=f"repo/{node}/qemu-server/{cf_name}",
                        tofile=f"live/{node}/qemu-server/{cf_name}"
                    ))
                    diffs["vm_configs"].append({
                        "node": node,
                        "conf": cf_name,
                        "diff": "".join(diff)
                    })

    # Docker stacks
    staged_stacks = glob.glob(os.path.join(staging_dir, "docker-stacks", "*", "*"))
    repo_stacks = glob.glob(os.path.join(STACKS_DIR, "*", "*"))

    repo_stack_keys = set()
    for rs in repo_stacks:
        parts = rs.split(os.sep)
        vm_name, s_id = parts[-2], parts[-1]
        repo_stack_keys.add((vm_name, s_id))

    staged_stack_keys = set()
    for ss in staged_stacks:
        parts = ss.split(os.sep)
        vm_name, s_id = parts[-2], parts[-1]
        staged_stack_keys.add((vm_name, s_id))

        staged_compose = os.path.join(ss, "docker-compose.yml")
        staged_env = os.path.join(ss, "stack.env")

        repo_dir = os.path.join(STACKS_DIR, vm_name, s_id)
        repo_compose = os.path.join(repo_dir, "docker-compose.yml")
        repo_secrets = os.path.join(repo_dir, "secrets.enc.yaml")

        compose_changed = False
        compose_diff = ""
        if os.path.exists(staged_compose):
            with open(staged_compose, 'r', encoding='utf-8') as f:
                s_comp_text = f.read()
            r_comp_text = ""
            if os.path.exists(repo_compose):
                with open(repo_compose, 'r', encoding='utf-8') as f:
                    r_comp_text = f.read()
            if s_comp_text.strip() != r_comp_text.strip():
                compose_changed = True
                compose_diff = "".join(list(difflib.unified_diff(
                    r_comp_text.splitlines(keepends=True),
                    s_comp_text.splitlines(keepends=True),
                    fromfile=f"repo/{vm_name}/{s_id}/docker-compose.yml",
                    tofile=f"live/{vm_name}/{s_id}/docker-compose.yml"
                ))[:40])

        env_changed = False
        if os.path.exists(staged_env):
            with open(staged_env, 'r', encoding='utf-8') as f:
                s_env_text = f.read()
            r_env_text = decrypt_sops_yaml(repo_secrets) if os.path.exists(repo_secrets) else ""
            if s_env_text.strip() != (r_env_text or "").strip():
                env_changed = True

        status = "MODIFIED" if (compose_changed or env_changed) else "UNCHANGED"
        if (vm_name, s_id) not in repo_stack_keys:
            status = "NEW"

        if status != "UNCHANGED":
            diffs["docker_stacks"].append({
                "vm_name": vm_name,
                "stack_id": s_id,
                "status": status,
                "compose_changed": compose_changed,
                "env_changed": env_changed,
                "diff": compose_diff
            })

    # Retired stacks
    for (vm_name, s_id) in (repo_stack_keys - staged_stack_keys):
        diffs["docker_stacks"].append({
            "vm_name": vm_name,
            "stack_id": s_id,
            "status": "REMOVED_OR_OFFLINE",
            "compose_changed": False,
            "env_changed": False,
            "diff": ""
        })

    return diffs

def apply_sync(staging_dir, diffs):
    print("\n💾 Applying Live Fleet Changes into Repository Blueprints...")

    # 1. Host configs
    for node in ["pve", "pve2", "pve3"]:
        node_stage = os.path.join(staging_dir, "hosts", node)
        if not os.path.exists(node_stage): continue

        repo_node_cfg = os.path.join(HOSTS_DIR, node, "configs")
        os.makedirs(repo_node_cfg, exist_ok=True)

        for fname in ["interfaces", "storage.cfg"]:
            src = os.path.join(node_stage, fname)
            dst = os.path.join(repo_node_cfg, fname)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"  ✓ Synced {node} {fname}")

        # qemu-server
        qemu_stage = os.path.join(node_stage, "qemu-server")
        if os.path.exists(qemu_stage):
            repo_qemu = os.path.join(repo_node_cfg, "qemu-server")
            os.makedirs(repo_qemu, exist_ok=True)
            for cf in glob.glob(os.path.join(qemu_stage, "*.conf")):
                shutil.copy2(cf, os.path.join(repo_qemu, os.path.basename(cf)))
            print(f"  ✓ Synced {node} VM configs in qemu-server/")

    # 2. Docker stacks
    staged_stacks = glob.glob(os.path.join(staging_dir, "docker-stacks", "*", "*"))
    synced_stacks = 0
    encrypted_secrets = 0

    for ss in staged_stacks:
        parts = ss.split(os.sep)
        vm_name, s_id = parts[-2], parts[-1]
        repo_stack_dir = os.path.join(STACKS_DIR, vm_name, s_id)
        os.makedirs(repo_stack_dir, exist_ok=True)

        # Copy compose
        s_comp = os.path.join(ss, "docker-compose.yml")
        if os.path.exists(s_comp):
            shutil.copy2(s_comp, os.path.join(repo_stack_dir, "docker-compose.yml"))

        # Copy deploy.json
        s_dep = os.path.join(ss, "deploy.json")
        if os.path.exists(s_dep):
            shutil.copy2(s_dep, os.path.join(repo_stack_dir, "deploy.json"))

        # Handle stack.env -> encrypt to secrets.enc.yaml
        s_env = os.path.join(ss, "stack.env")
        if os.path.exists(s_env):
            with open(s_env, 'r', encoding='utf-8') as f:
                env_text = f.read().strip()
            if env_text:
                dest_enc = os.path.join(repo_stack_dir, "secrets.enc.yaml")
                encrypt_to_sops_yaml(env_text, dest_enc)
                encrypted_secrets += 1

        synced_stacks += 1

    print(f"  ✅ Applied {synced_stacks} stacks into infrastructure/docker-stacks/.")
    print(f"  🔒 Encrypted {encrypted_secrets} stack secrets into secrets.enc.yaml.")

    # 3. Clean up plaintext secrets in staging
    for root, _, files in os.walk(staging_dir):
        for f in files:
            if f.endswith(".env"):
                os.remove(os.path.join(root, f))
    print(f"  🧹 Sanitized staging directory: All plaintext .env files purged.")

    # 4. Regenerate stack index
    index_script = os.path.join(os.path.dirname(__file__), "generate-stack-index.py")
    if os.path.exists(index_script):
        subprocess.run([sys.executable, index_script])

def print_drift_report(diffs):
    print("\n" + "="*70)
    print("📊 LIVE FLEET DRIFT AUDIT REPORT")
    print("="*70)

    host_changes = diffs.get("hosts", [])
    vm_changes = diffs.get("vm_configs", [])
    stack_changes = diffs.get("docker_stacks", [])

    print(f"\n1. Proxmox Host Config Drift: {len(host_changes)} changes detected")
    for hc in host_changes:
        print(f"  - [{hc['node']}] {hc['file']} modified")

    print(f"\n2. VM Hardware/QEMU Config Drift: {len(vm_changes)} changes detected")
    for vc in vm_changes:
        print(f"  - [{vc['node']}] {vc['conf']} modified")

    print(f"\n3. Docker Portainer Stack Drift: {len(stack_changes)} changes detected")
    for sc in stack_changes:
        status_tag = sc["status"]
        tags = []
        if sc.get("compose_changed"): tags.append("compose.yml")
        if sc.get("env_changed"): tags.append("stack.env")
        tag_str = f" ({', '.join(tags)})" if tags else ""
        print(f"  - [{status_tag}] {sc['vm_name']} / Stack {sc['stack_id']}{tag_str}")

    print("\n" + "="*70)

def main():
    parser = argparse.ArgumentParser(description="Live Homelab Fleet Discovery & Sync Tool")
    parser.add_argument("--node", help="Target specific node (pve, pve2, pve3)")
    parser.add_argument("--vmid", type=int, help="Target specific VMID")
    parser.add_argument("-i", "--identity", help="Path to SSH private key (defaults to ~/.ssh/id_ed25519 if present)")
    parser.add_argument("--staging-dir", default=DEFAULT_STAGING, help="Directory to stage live configs")
    parser.add_argument("--apply", action="store_true", help="Apply discovered changes to repository blueprints")
    parser.add_argument("--diff-only", action="store_true", help="Only audit and print drift report without applying")
    args = parser.parse_args()

    os.makedirs(args.staging_dir, exist_ok=True)

    # Determine identity file
    identity_file = args.identity
    if not identity_file:
        for candidate in [
            os.path.expanduser("~/.ssh/proxmox_ed25519"),
            "/home/dtheurer/.ssh/proxmox_ed25519",
            os.path.expanduser("~/.ssh/id_ed25519"),
            "/home/dtheurer/.ssh/id_ed25519",
        ]:
            if os.path.exists(candidate):
                identity_file = candidate
                break
    if identity_file:
        print(f"🔑 Using SSH identity key: {identity_file}")


    target_nodes = NODES
    if args.node:
        target_nodes = [n for n in NODES if n["node"] == args.node]

    all_stack_results = []
    node_audits = []

    for n in target_nodes:
        res = audit_node(n, args.staging_dir, identity_file=identity_file)
        if not res: continue
        node_audits.append(res)

        vms_to_audit = res["vms"]
        if args.vmid:
            vms_to_audit = [v for v in vms_to_audit if v["vmid"] == args.vmid]

        for vm in vms_to_audit:
            stacks = audit_vm_docker(n, vm, args.staging_dir, identity_file=identity_file)
            all_stack_results.extend(stacks)

    if not node_audits:
        print("\n⚠️ Could not connect to any Proxmox node via SSH.")
        print("Please check SSH keys or run from an interactive terminal with root credentials.")
        sys.exit(1)

    diffs = compute_diffs(args.staging_dir)
    print_drift_report(diffs)

    if args.apply:
        apply_sync(args.staging_dir, diffs)
    else:
        print("\n💡 Run with --apply to synchronize discovered changes and re-encrypt secrets into the repository.")

if __name__ == "__main__":
    main()

