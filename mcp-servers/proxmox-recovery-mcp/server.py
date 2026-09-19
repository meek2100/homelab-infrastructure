from fastmcp import FastMCP
import subprocess
import os
import json

mcp = FastMCP("Proxmox Recovery System")

def run_script(script_name: str, args: list[str] = None) -> str:
    if args is None:
        args = []
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script_path = os.path.join(os.path.dirname(__file__), "scripts", script_name)
    if not os.path.exists(script_path):
        return f"Error: Script {script_path} not found."
    cmd = ["python3", script_path] + args
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
def restore_stacks(node: str, vmid: str, dry_run: bool = False) -> str:
    args = ["--node", node, "--vmid", vmid]
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

if __name__ == "__main__":
    mcp.run()

