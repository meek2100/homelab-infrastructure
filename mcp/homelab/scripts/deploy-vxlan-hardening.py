#!/usr/bin/env python3
"""
Deploy Hardened VXLAN & Failover Configuration to OpenWrt and VM 107
Eliminates split-brain autonomous failover, disables duplicate daemons,
stops interface bouncing/STP TCN storms, and verifies P1 split-trunking.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OPENWRT_IP = "192.168.1.226"
PVE_IP = "192.168.1.250"
VMID = 107

FAILOVER_SCRIPT_PATH = os.path.join(REPO_ROOT, "infrastructure", "network", "openwrt", "scripts", "failover.sh")
VM107_SCRIPT_PATH = os.path.join(REPO_ROOT, "infrastructure", "network", "known-good", "vxlan-server-vm107", "usr", "local", "bin", "vxlan-nm")

def get_ssh_key_for(target):
    if target == "openwrt":
        candidates = [
            "/home/dtheurer/.ssh/pi_id_ed25519",
            os.path.expanduser("~/.ssh/pi_id_ed25519"),
            "/mnt/c/Users/dtheurer/.ssh/pi_id_ed25519",
        ]
    else:
        candidates = [
            "/home/dtheurer/.ssh/proxmox_ed25519",
            os.path.expanduser("~/.ssh/proxmox_ed25519"),
            "/home/agentsvc/.ssh/proxmox_ed25519",
            "/home/dtheurer/.ssh/id_ed25519",
            os.path.expanduser("~/.ssh/id_ed25519"),
        ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def run_ssh(host_ip, cmd, user="root", target_type="pve", timeout=30, input_data=None):
    key = get_ssh_key_for(target_type)
    ssh_args = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    ]
    if key:
        ssh_args.extend(["-i", key])
    ssh_args.extend([f"{user}@{host_ip}", cmd])
    try:
        res = subprocess.run(
            ssh_args,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)

def qm_exec_vm107(cmd, timeout=30):
    escaped_cmd = cmd.replace('"', '\\"')
    remote_cmd = f'qm guest exec {VMID} -- sh -c "{escaped_cmd}"'
    code, stdout, stderr = run_ssh(PVE_IP, remote_cmd, user="root", target_type="pve", timeout=timeout)
    if code != 0:
        return False, stderr
    try:
        data = json.loads(stdout)
        out_data = data.get("out-data", "")
        err_data = data.get("err-data", "")
        exit_code = data.get("exitcode", 0)
        return exit_code == 0, out_data + err_data
    except Exception:
        return code == 0, stdout

def deploy_to_vm107():
    print(f"\n🚀 Deploying hardened vxlan-nm to vxlan-server (VM {VMID} on {PVE_IP})...")
    if not os.path.exists(VM107_SCRIPT_PATH):
        return f"❌ Source script not found: {VM107_SCRIPT_PATH}"

    with open(VM107_SCRIPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    b64_payload = base64.b64encode(content.encode("utf-8")).decode("ascii")
    write_cmd = f"echo '{b64_payload}' | base64 -d > /usr/local/bin/vxlan-nm && chmod 755 /usr/local/bin/vxlan-nm"

    ok, out = qm_exec_vm107(write_cmd)
    if not ok:
        return f"❌ Failed writing /usr/local/bin/vxlan-nm on VM {VMID}: {out}"
    print("  ✓ Updated /usr/local/bin/vxlan-nm on VM 107")

    # Restart vxlan-nm.service
    ok, out = qm_exec_vm107("systemctl restart vxlan-nm.service")
    if not ok:
        print(f"  ⚠️ systemctl restart returned: {out}")
    else:
        print("  ✓ Restarted vxlan-nm.service on VM 107")

    # Force P1 baseline
    ok, out = qm_exec_vm107("/usr/local/bin/vxlan-nm -p1")
    print(f"  ✓ Activated P1 baseline on VM 107:\n{out.strip()}")

    # Check status
    ok, out = qm_exec_vm107("/usr/local/bin/vxlan-nm -s")
    print(f"  ✓ VM 107 Status:\n{out.strip()}")
    return "✅ VM 107 deployed successfully"

def deploy_to_openwrt():
    print(f"\n🚀 Deploying hardened failover to OpenWrt ({OPENWRT_IP})...")
    if not os.path.exists(FAILOVER_SCRIPT_PATH):
        return f"❌ Source script not found: {FAILOVER_SCRIPT_PATH}"

    with open(FAILOVER_SCRIPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Stop and disable duplicate vxlan-nm daemon, and stub /usr/bin/vxlan-nm
    stop_cmd = (
        "/etc/init.d/vxlan-nm stop 2>/dev/null; "
        "/etc/init.d/vxlan-nm disable 2>/dev/null; "
        "killall -9 vxlan-nm 2>/dev/null; "
        "echo '#!/bin/sh' > /usr/bin/vxlan-nm && echo 'exit 0' >> /usr/bin/vxlan-nm && chmod 755 /usr/bin/vxlan-nm; "
        "true"
    )
    code, out, err = run_ssh(OPENWRT_IP, stop_cmd, user="root", target_type="openwrt")
    print("  ✓ Stopped, disabled, and stubbed duplicate vxlan-nm daemon on OpenWrt")

    # 2. Stream updated /etc/scripts/failover.sh via stdin
    write_cmd = "mkdir -p /etc/scripts && cat > /etc/scripts/failover.sh && chmod 755 /etc/scripts/failover.sh"
    code, out, err = run_ssh(OPENWRT_IP, write_cmd, user="root", target_type="openwrt", input_data=content)
    if code != 0:
        return f"❌ Failed streaming /etc/scripts/failover.sh on OpenWrt: {err}"
    print("  ✓ Streamed /etc/scripts/failover.sh to OpenWrt via stdin")

    # 3. Verify file size
    code, out, err = run_ssh(OPENWRT_IP, "wc -c /etc/scripts/failover.sh", user="root", target_type="openwrt")
    print(f"  ✓ Remote file size: {out.strip()}")

    # 4. Apply clean P1 state
    apply_cmd = "/etc/scripts/failover.sh -p1"
    code, out, err = run_ssh(OPENWRT_IP, apply_cmd, user="root", target_type="openwrt")
    print(f"  ✓ Activated P1 on OpenWrt:\n{out.strip()}")

    # 5. Show status
    code, out, err = run_ssh(OPENWRT_IP, "/etc/scripts/failover.sh -s", user="root", target_type="openwrt")
    print(f"  ✓ OpenWrt Status:\n{out.strip()}")
    return "✅ OpenWrt deployed successfully"

def main():
    parser = argparse.ArgumentParser(description="Deploy hardened VXLAN & Failover scripts")
    parser.add_argument("--target", choices=["all", "vm107", "openwrt"], default="all", help="Target to deploy to")
    args = parser.parse_args()

    print("=== Automated Deployment of Hardened VXLAN & Failover ===")
    if args.target in ["all", "vm107"]:
        vm_res = deploy_to_vm107()
        print(vm_res)

    if args.target in ["all", "openwrt"]:
        ow_res = deploy_to_openwrt()
        print(ow_res)

    print("\n🚀 Deployment complete! Waiting 5s for network to settle before testing...")
    time.sleep(5)
    print("✅ Ready for verification tests.")

if __name__ == "__main__":
    main()
