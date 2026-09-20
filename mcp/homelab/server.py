from fastmcp import FastMCP
import subprocess
import os
import json

import sys

mcp = FastMCP("Homelab Infrastructure System")

DEFAULT_NODE_IPS = {
    "pve": "192.168.1.250",
    "pve2": "192.168.1.240",
    "pve3": "192.168.1.245"
}

def get_ssh_key():
    for candidate in [
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/dtheurer/.ssh/proxmox_ed25519",
        "/home/agentsvc/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519"
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def run_ssh_cmd(host_ip: str, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    key = get_ssh_key()
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

def run_script(script_name: str, args: list[str] = None) -> str:
    if args is None:
        args = []
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(os.path.dirname(__file__), "scripts", script_name)
    if not os.path.exists(script_path):
        return f"Error: Script {script_path} not found."
    cmd = [sys.executable, script_path] + args
    try:
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout
        else:
            return f"Error executing {script_name}:\n{res.stderr}\n{res.stdout}"
    except Exception as e:
        return f"Exception executing {script_name}: {e}"

def run_bash_script(script_name: str) -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(os.path.dirname(__file__), "scripts", script_name)
    if not os.path.exists(script_path):
        return f"Error: Script {script_path} not found."
    cmd = ["bash", script_path]
    try:
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout
        else:
            return f"Error executing {script_name}:\n{res.stderr}\n{res.stdout}"
    except Exception as e:
        return f"Exception executing {script_name}: {e}"

@mcp.tool()
def register_host(node: str, ip: str) -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    host_dir = os.path.join(repo_root, "infrastructure", "hosts", node)
    os.makedirs(host_dir, exist_ok=True)
    meta_path = os.path.join(host_dir, "meta.json")
    with open(meta_path, 'w') as f:
        json.dump({"ip": ip}, f, indent=4)
    return f"Successfully registered host {node} with IP {ip} at {host_dir}"

@mcp.tool()
def register_vm(node: str, vmid: str, name: str) -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    vm_dir = os.path.join(repo_root, "infrastructure", "vms", f"{node}-{vmid}-{name}")
    os.makedirs(vm_dir, exist_ok=True)
    return f"Successfully registered VM {name} (ID: {vmid}) on node {node} at {vm_dir}"

@mcp.tool()
def list_vms(node: str = None) -> str:
    """Lists both Virtual Machines (QEMU) and LXC Containers across Proxmox nodes."""
    target_nodes = [node] if node else ["pve", "pve2", "pve3"]
    results = []
    for n in target_nodes:
        ip = DEFAULT_NODE_IPS.get(n)
        if not ip:
            continue
        code_qm, stdout_qm, _ = run_ssh_cmd(ip, "qm list")
        code_pct, stdout_pct, _ = run_ssh_cmd(ip, "pct list")
        node_lines = [f"🖥️ Proxmox Node {n} ({ip}):"]
        if code_qm == 0 and stdout_qm.strip():
            node_lines.append(f"  [QEMU VMs]\n{stdout_qm.strip()}")
        if code_pct == 0 and stdout_pct.strip():
            node_lines.append(f"  [LXC Containers]\n{stdout_pct.strip()}")
        if len(node_lines) == 1:
            node_lines.append("  (No VMs or LXCs found or node unreachable)")
        results.append("\n".join(node_lines))
    return "\n\n".join(results)

@mcp.tool()
def get_docker_status(node: str, vmid: int) -> str:
    """Queries live container status and health on a VM (via QGA) or LXC (via pct exec)."""
    ip = DEFAULT_NODE_IPS.get(node)
    if not ip:
        return f"Error: Unknown Proxmox node '{node}'"

    code_type, out_type, _ = run_ssh_cmd(ip, f"test -f /etc/pve/qemu-server/{vmid}.conf && echo qm || (test -f /etc/pve/lxc/{vmid}.conf && echo pct || echo qm)")
    tool = out_type.strip() if code_type == 0 and out_type.strip() in ["qm", "pct"] else "qm"

    if tool == "qm":
        cmd = f"qm guest exec {vmid} -- docker ps"
        code, stdout, stderr = run_ssh_cmd(ip, cmd)
        if code != 0:
            return f"Error querying VM {vmid} on {node}: {stderr.strip()}"
        try:
            data = json.loads(stdout)
            out_data = data.get("out-data", "")
            if out_data:
                return f"🐳 Containers on VM {vmid} ({node}):\n{out_data.strip()}"
            return f"QGA response: {stdout}"
        except Exception:
            return stdout
    else:
        cmd = f"pct exec {vmid} -- docker ps"
        code, stdout, stderr = run_ssh_cmd(ip, cmd)
        if code != 0:
            return f"Error querying LXC {vmid} on {node}: {stderr.strip()}"
        return f"🐳 Containers on LXC {vmid} ({node}):\n{stdout.strip()}"

@mcp.tool()
def audit_infrastructure() -> str:
    out = "Running Phase 1 Audits...\n"
    out += run_bash_script("phase1-system-drift-audit.sh") + "\n"
    out += run_bash_script("phase1-vm-drift-audit.sh") + "\n"
    out += run_bash_script("extract_host_configs.sh") + "\n"
    return out

@mcp.tool()
def backup_host(node: str) -> str:
    return run_script("phase2-extract-custom-files.py", ["--node", node])

@mcp.tool()
def restore_host(node: str, dry_run: bool = False) -> str:
    args = ["--node", node]
    if dry_run: args.append("--dry-run")
    return run_script("restore-host-drifts.py", args)

@mcp.tool()
def restore_host_configs(node: str, dry_run: bool = False) -> str:
    args = ["--node", node]
    if dry_run: args.append("--dry-run")
    return run_script("restore-host-configs.py", args)

@mcp.tool()
def backup_vm(node: str, vmid: str) -> str:
    return run_script("phase2-extract-custom-files.py", ["--node", node, "--vmid", vmid])

@mcp.tool()
def restore_vm(node: str, vmid: str, dry_run: bool = False) -> str:
    args = ["--node", node, "--vmid", vmid]
    if dry_run: args.append("--dry-run")
    return run_script("restore-vm-drifts.py", args)

@mcp.tool()
def backup_stacks() -> str:
    return run_script("phase2-split-stacks.py")

@mcp.tool()
def restore_stacks(node: str, vmid: str, stack: str = None, dry_run: bool = False) -> str:
    """Restores Portainer Docker stacks, decrypts SOPS secrets, and restarts containers."""
    args = ["--node", node, "--vmid", str(vmid)]
    if stack: args.extend(["--stack", str(stack)])
    if dry_run: args.append("--dry-run")
    return run_script("restore-docker-stacks.py", args)

@mcp.tool()
def start_docker_stacks(node: str = None, vmid: str = None, dry_run: bool = False) -> str:
    args = []
    if node: args.extend(["--node", node])
    if vmid: args.extend(["--vmid", vmid])
    if dry_run: args.append("--dry-run")
    return run_script("start-docker-stacks.py", args)

@mcp.tool()
def backup_apt_packages(node: str = None, vmid: str = None) -> str:
    args = []
    if node: args.extend(["--node", node])
    if vmid: args.extend(["--vmid", vmid])
    return run_script("phase2-extract-apt-packages.py", args)

@mcp.tool()
def restore_apt_packages(node: str = None, vmid: str = None, dry_run: bool = False) -> str:
    args = []
    if node: args.extend(["--node", node])
    if vmid: args.extend(["--vmid", vmid])
    if dry_run: args.append("--dry-run")
    return run_script("restore-apt-packages.py", args)

@mcp.tool()
def sync_fleet(node: str = None, vmid: int = None, apply: bool = False, diff_only: bool = True) -> str:
    """Discovers and synchronizes live Proxmox host configs, VM configs, and Portainer stacks."""
    args = []
    if node: args.extend(["--node", node])
    if vmid: args.extend(["--vmid", str(vmid)])
    if apply:
        args.append("--apply")
    elif diff_only:
        args.append("--diff-only")
    return run_script("sync-live-fleet.py", args)

@mcp.tool()
def generate_stack_index() -> str:
    """Regenerates infrastructure/docker-stacks/STACK-INDEX.md catalog."""
    return run_script("generate-stack-index.py")

@mcp.tool()
def snapshot_vm(node: str, vmid: int, name: str, description: str = "", include_ram: bool = False) -> str:
    """Takes a live Proxmox snapshot of a virtual machine (QEMU) or LXC container."""
    args = ["--node", node, "--vmid", str(vmid), "--action", "create", "--name", name]
    if description: args.extend(["--desc", description])
    if include_ram: args.append("--include-ram")
    return run_script("manage-vm-snapshots.py", args)

@mcp.tool()
def list_vm_snapshots(node: str, vmid: int) -> str:
    """Lists all Proxmox snapshots for a virtual machine (QEMU) or LXC container."""
    return run_script("manage-vm-snapshots.py", ["--node", node, "--vmid", str(vmid), "--action", "list"])

@mcp.tool()
def rollback_vm(node: str, vmid: int, name: str) -> str:
    """Rolls back a Proxmox virtual machine (QEMU) or LXC container to a previous snapshot."""
    return run_script("manage-vm-snapshots.py", ["--node", node, "--vmid", str(vmid), "--action", "rollback", "--name", name])

@mcp.tool()
def delete_vm_snapshot(node: str, vmid: int, name: str) -> str:
    """Deletes a Proxmox snapshot from a virtual machine (QEMU) or LXC container."""
    return run_script("manage-vm-snapshots.py", ["--node", node, "--vmid", str(vmid), "--action", "delete", "--name", name])

@mcp.tool()
def backup_vm_vzdump(node: str, vmid: int, storage: str = None) -> str:
    """Takes a full Proxmox vzdump backup archive of a virtual machine (QEMU) or LXC container."""
    args = ["--node", node, "--vmid", str(vmid), "--action", "vzdump"]
    if storage: args.extend(["--storage", storage])
    return run_script("manage-vm-snapshots.py", args)

if __name__ == "__main__":
    mcp.run()


