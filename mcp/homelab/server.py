from fastmcp import FastMCP
from typing import Literal, Optional
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
    python_bin = os.path.join(repo_root, ".venv", "bin", "python3")
    if not os.path.exists(python_bin):
        python_bin = sys.executable
    cmd = [python_bin, script_path] + args
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


# ==============================================================================
# 1. FLEET & HYPERVISOR MANAGEMENT
# ==============================================================================

@mcp.tool()
def sync_fleet(apply: bool = False, diff_only: bool = True) -> str:
    """Core GitOps fleet drift verification and synchronization.
    Runs non-destructive state diff against live hypervisors and VMs when diff_only=True."""
    args = []
    if apply:
        args.append("--apply")
    if diff_only:
        args.append("--diff-only")
    return run_script("sync-live-fleet.py", args)

@mcp.tool()
def manage_hosts(
    action: Literal["audit", "backup", "restore", "restore_configs", "register"],
    node: str | None = None,
    ip: str | None = None
) -> str:
    """Manage Proxmox physical hypervisor nodes (pve, pve2, pve3).
    Actions:
      - 'audit': Compare live host config & packages against Git blueprints (diff-only).
      - 'backup': Extract network interfaces, storage definitions, and cron to Git.
      - 'restore': Restore host drift artifacts and system configs.
      - 'restore_configs': Restore /etc/network/interfaces and storage.cfg.
      - 'register': Register or update a host IP definition in infrastructure/hosts."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    action = action.lower().strip()
    if action == "audit":
        return run_script("sync-live-fleet.py", ["--diff-only"])
    elif action == "backup":
        return run_bash_script("extract_host_configs.sh")
    elif action == "restore":
        return run_script("restore-host-drifts.py", [node] if node else [])
    elif action == "restore_configs":
        return run_script("restore-host-configs.py", [node] if node else [])
    elif action == "register":
        if not node or not ip:
            return "Error: Both 'node' and 'ip' are required for action='register'."
        host_dir = os.path.join(repo_root, "infrastructure", "hosts", node)
        os.makedirs(host_dir, exist_ok=True)
        with open(os.path.join(host_dir, "meta.json"), "w") as f:
            json.dump({"ip": ip}, f, indent=4)
        return f"Successfully registered host {node} ({ip}) at {host_dir}"
    return f"Unknown host action: '{action}'. Valid actions: audit, backup, restore, restore_configs, register."

@mcp.tool()
def manage_vms(
    action: Literal["list", "status", "start", "stop", "restore", "register"],
    node: str | None = None,
    vmid: str | None = None,
    name: str | None = None
) -> str:
    """Manage QEMU Virtual Machines and LXC Containers across Proxmox nodes.
    Actions:
      - 'list': List all running/stopped VMs and LXCs with IP and resource status.
      - 'status': Check Docker daemon and container status on a VM via QGA.
      - 'start': Start a specific VM ID on a node.
      - 'stop': Gracefully stop a specific VM ID on a node.
      - 'restore': Restore custom VM configuration drift from Git blueprints.
      - 'register': Register a VM directory definition in infrastructure/vms."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    action = action.lower().strip()

    if action == "list":
        target_nodes = [node] if node else ["pve", "pve2", "pve3"]
        results = []
        for target in target_nodes:
            ip = DEFAULT_NODE_IPS.get(target)
            if not ip: continue
            code, out, _ = run_ssh_cmd(ip, "qm list")
            if code == 0:
                results.append(f"--- QEMU VMs on {target} ({ip}) ---\n{out.strip()}")
            code_lxc, out_lxc, _ = run_ssh_cmd(ip, "pct list 2>/dev/null || true")
            if code_lxc == 0 and out_lxc.strip():
                results.append(f"--- LXC Containers on {target} ({ip}) ---\n{out_lxc.strip()}")
        return "\n\n".join(results) if results else "No VMs or containers found."

    elif action == "status":
        if not node or not vmid:
            return "Error: Both 'node' and 'vmid' are required for action='status'."
        ip = DEFAULT_NODE_IPS.get(node)
        if not ip: return f"Error: Unknown node '{node}'."
        code, out, err = run_ssh_cmd(ip, f"qm guest exec {vmid} -- docker ps --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}'")
        if code == 0:
            try:
                data = json.loads(out)
                return data.get("out-data", "No output returned from guest agent.")
            except Exception:
                return out
        return f"Failed to get Docker status for VM {vmid} on {node}: {err}"

    elif action == "start":
        if not node or not vmid: return "Error: 'node' and 'vmid' required."
        ip = DEFAULT_NODE_IPS.get(node)
        code, out, err = run_ssh_cmd(ip, f"qm start {vmid}")
        return f"Successfully started VM {vmid} on {node}." if code == 0 else f"Failed to start VM {vmid}: {err}"

    elif action == "stop":
        if not node or not vmid: return "Error: 'node' and 'vmid' required."
        ip = DEFAULT_NODE_IPS.get(node)
        code, out, err = run_ssh_cmd(ip, f"qm shutdown {vmid}")
        return f"Graceful shutdown initiated for VM {vmid} on {node}." if code == 0 else f"Failed to stop VM {vmid}: {err}"

    elif action == "restore":
        return run_script("restore-vm-drifts.py", [vmid] if vmid else [])

    elif action == "register":
        if not node or not vmid or not name:
            return "Error: 'node', 'vmid', and 'name' are required for action='register'."
        vm_dir = os.path.join(repo_root, "infrastructure", "vms", f"{node}-{vmid}-{name}")
        os.makedirs(vm_dir, exist_ok=True)
        return f"Successfully registered VM {name} (ID: {vmid}) on node {node} at {vm_dir}"

    return f"Unknown VM action: '{action}'. Valid actions: list, status, start, stop, restore, register."

@mcp.tool()
def manage_vm_snapshots(
    action: Literal["list", "create", "rollback", "delete", "vzdump"],
    node: str,
    vmid: str,
    snapshot_name: str | None = None
) -> str:
    """Manage Proxmox QEMU VM live memory/disk snapshots and vzdump archives.
    Actions:
      - 'list': List all existing snapshots for a VM.
      - 'create': Create a new snapshot (snapshot_name required).
      - 'rollback': Rollback VM to a named snapshot.
      - 'delete': Delete an existing snapshot.
      - 'vzdump': Trigger Proxmox vzdump backup job to local/PBS storage."""
    action = action.lower().strip()
    if action == "vzdump":
        ip = DEFAULT_NODE_IPS.get(node)
        if not ip: return f"Error: Unknown node '{node}'."
        code, out, err = run_ssh_cmd(ip, f"vzdump {vmid} --mode snapshot --compress zstd --storage local", timeout=300)
        return out if code == 0 else f"vzdump failed: {err}"
    
    args = ["--action", action, "--node", node, "--vmid", str(vmid)]
    if snapshot_name:
        args.extend(["--name", snapshot_name])
    return run_script("manage-vm-snapshots.py", args)


# ==============================================================================
# 2. DOCKER STACKS & SOFTWARE PACKAGES
# ==============================================================================

@mcp.tool()
def manage_stacks(
    action: Literal["index", "backup", "restore", "start"],
    target_vm: str | None = None,
    stack_name: str | None = None
) -> str:
    """Manage 91 Portainer stacks and 188 microservices across all Docker VMs.
    Actions:
      - 'index': Rebuild infrastructure/docker-stacks/STACK-INDEX.md catalog with secrets state.
      - 'backup': Capture all live compose files and decryptable secrets to Git.
      - 'restore': Decrypt SOPS secrets, inject environment files, and write compose configs.
      - 'start': Spin up all Docker compose stacks on target VM (e.g. luna-server, nexus-server)."""
    action = action.lower().strip()
    if action == "index":
        return run_script("generate-stack-index.py")
    elif action == "backup":
        return run_script("sync-live-fleet.py", ["--apply"])
    elif action == "restore":
        args = []
        if target_vm: args.extend(["--vm", target_vm])
        if stack_name: args.extend(["--stack", stack_name])
        return run_script("restore-docker-stacks.py", args)
    elif action == "start":
        args = [target_vm] if target_vm else []
        return run_script("start-docker-stacks.py", args)
    return f"Unknown stack action: '{action}'. Valid actions: index, backup, restore, start."

@mcp.tool()
def manage_apt_packages(
    action: Literal["backup", "restore"],
    node: str | None = None,
    vmid: str | None = None
) -> str:
    """Backup or restore APT software package states across Proxmox hosts and guest VMs.
    Actions:
      - 'backup': Capture installed Debian/Ubuntu package manifests to configs/apt-packages.txt.
      - 'restore': Reinstall missing APT dependencies matching GitOps manifest."""
    action = action.lower().strip()
    if action == "backup":
        return run_script("sync-live-fleet.py", ["--apply"])
    elif action == "restore":
        args = []
        if node: args.extend(["--node", node])
        if vmid: args.extend(["--vmid", str(vmid)])
        return run_script("restore-apt-packages.py", args)
    return f"Unknown action: '{action}'. Valid actions: backup, restore."


# ==============================================================================
# 3. SWITCHING & ROUTING HARDWARE AUTOMATION
# ==============================================================================

@mcp.tool()
def manage_araknis_router(
    action: Literal["status", "backup", "restore"] = "status",
    config_file: str | None = None,
    confirm: bool = False
) -> str:
    """Manage Araknis 520 Dual-WAN Router (192.168.1.1) via native REST API.
    Actions:
      - 'status': Audit router health, WAN links, subnets, DHCP leases, and 36 ACL rules.
      - 'backup': Export running configuration blob to infrastructure/network/configs/araknis-520-backup.cfg.
      - 'restore': Restore encrypted configuration blob from Git blueprint (confirm=True required)."""
    action = action.lower().strip()
    if action == "status":
        return run_script("manage-araknis-router.py", ["status"])
    elif action == "backup":
        return run_script("manage-araknis-router.py", ["backup"])
    elif action == "restore":
        args = ["restore"]
        if config_file: args.extend(["--file", config_file])
        if confirm: args.append("--confirm")
        return run_script("manage-araknis-router.py", args)
    return f"Unknown action: '{action}'. Valid actions: status, backup, restore."

@mcp.tool()
def manage_araknis_switch(
    action: Literal["status", "backup", "poe_cycle"] = "status",
    port: str | None = None,
    wait_sec: int = 5
) -> str:
    """Manage Araknis 920 Multi-Gig Core Managed Switch (192.168.1.215) via SSH/Telnet CLI.
    Actions:
      - 'status': Audit 24-port link status, speeds, PoE power draw, and IGMP snooping.
      - 'backup': Export running configuration to infrastructure/network/configs/araknis-920-running.cfg.
      - 'poe_cycle': Power cycle an attached PoE device (e.g. port='1/0/7', wait_sec=5)."""
    action = action.lower().strip()
    if action == "status":
        return run_script("manage-araknis-switch.py", ["status"])
    elif action == "backup":
        return run_script("manage-araknis-switch.py", ["backup"])
    elif action == "poe_cycle":
        if not port: return "Error: 'port' required for poe_cycle (e.g. '1/0/7')."
        return run_script("manage-araknis-switch.py", ["poe-cycle", "--port", port, "--wait", str(wait_sec)])
    return f"Unknown action: '{action}'. Valid actions: status, backup, poe_cycle."

@mcp.tool()
def manage_netgear_switch(
    action: Literal["status", "backup", "verify", "restore", "set_vlan", "delete_vlan", "set_pvid", "set_port", "set_features"] = "status",
    ip: str = "192.168.1.220",
    file: str | None = None,
    confirm: bool = False,
    vid: int | None = None,
    pvid: int | None = None,
    port: int | None = None,
    tagged: str | None = None,
    untagged: str | None = None,
    admin: Literal["enable", "disable"] | None = None,
    speed: str | None = None,
    igmp: Literal["enable", "disable"] | None = None,
    loop: Literal["enable", "disable"] | None = None,
    json_output: bool = False
) -> str:
    """Manage headless Netgear GS108Ev2 switch (192.168.1.220) via pure-Python Layer 2 NSDP protocol.
    Automatically queries directly or relays via OpenWrt (192.168.1.226) / PVE (192.168.1.250).
    Actions:
      - 'status'      : Query 8-port link state, CRC errors, VLAN table, PVIDs, and features.
      - 'backup'      : Save dual JSON state and binary payload backups to Git.
      - 'verify'      : Compare live switch state against GitOps backup JSON.
      - 'restore'     : Restore all VLANs, ports, PVIDs, and features from backup (confirm=True).
      - 'set_vlan'    : Configure 802.1Q VLAN membership (vid, tagged, untagged, pvid).
      - 'delete_vlan' : Delete an 802.1Q VLAN (vid).
      - 'set_pvid'    : Assign port default VLAN ID (port, pvid).
      - 'set_port'    : Configure port state (port, admin='enable'/'disable', speed='auto'/'100M').
      - 'set_features': Configure switch features (igmp='enable'/'disable', loop='enable'/'disable')."""
    action = action.lower().strip()
    base_args = ["--ip", ip] if ip != "192.168.1.220" else []

    if action == "status":
        args = base_args + ["status"]
        if json_output: args.append("--json")
        return run_script("manage-netgear-switch.py", args)
    elif action == "backup":
        return run_script("manage-netgear-switch.py", base_args + ["backup"])
    elif action == "verify":
        args = base_args + ["verify"]
        if file: args.extend(["--file", file])
        return run_script("manage-netgear-switch.py", args)
    elif action == "restore":
        args = base_args + ["restore"]
        if file: args.extend(["--file", file])
        if confirm: args.append("--confirm")
        return run_script("manage-netgear-switch.py", args)
    elif action == "set_vlan":
        if vid is None: return "Error: 'vid' is required."
        args = base_args + ["set-vlan", "--vid", str(vid)]
        if tagged: args.extend(["--tagged", tagged])
        if untagged: args.extend(["--untagged", untagged])
        if pvid: args.extend(["--pvid", str(pvid)])
        return run_script("manage-netgear-switch.py", args)
    elif action == "delete_vlan":
        if vid is None: return "Error: 'vid' is required."
        return run_script("manage-netgear-switch.py", base_args + ["delete-vlan", "--vid", str(vid)])
    elif action == "set_pvid":
        if port is None or pvid is None: return "Error: 'port' and 'pvid' required."
        return run_script("manage-netgear-switch.py", base_args + ["set-pvid", "--port", str(port), "--pvid", str(pvid)])
    elif action == "set_port":
        if port is None: return "Error: 'port' is required."
        args = base_args + ["set-port", "--port", str(port)]
        if admin: args.extend(["--admin", admin])
        if speed: args.extend(["--speed", speed])
        return run_script("manage-netgear-switch.py", args)
    elif action == "set_features":
        args = base_args + ["set-feature"]
        if igmp: args.extend(["--igmp", igmp])
        if loop: args.extend(["--loop-detection", loop])
        return run_script("manage-netgear-switch.py", args)
    return f"Unknown action: '{action}'. Valid actions: status, backup, verify, restore, set_vlan, delete_vlan, set_pvid, set_port, set_features."

@mcp.tool()
def manage_pakedge_switch(
    action: Literal["status", "backup", "poe_cycle", "power_cycle", "configure_vlans"] = "status",
    port: int | None = None,
    wait_sec: int = 5,
    vlans: str | None = None,
    host: str = "192.168.1.205"
) -> str:
    """Manage Pakedge SX-8P Managed Switch (192.168.1.205) via native Telnet/RFC854 engine.
    Actions:
      - 'status'         : Query 8-port link state, learned MACs, and VLAN assignments.
      - 'backup'         : Export running configuration to infrastructure/network/configs/pakedge-sx8p-running.cfg.
      - 'poe_cycle'      : Power-cycle individual PoE port (1-8) to reboot connected test equipment.
      - 'power_cycle'    : Reboot entire Pakedge switch via internal CLI.
      - 'configure_vlans': Update 802.1Q port VLAN tags across switch ports."""
    action = action.lower().strip()
    if action == "status":
        return run_script("manage-pakedge-switch.py", ["status", "--host", host])
    elif action == "backup":
        return run_script("manage-pakedge-switch.py", ["backup", "--host", host])
    elif action == "poe_cycle":
        if port is None: return "Error: 'port' (1-8) required."
        return run_script("manage-pakedge-switch.py", ["poe-port-cycle", "--port", str(port), "--wait", str(wait_sec), "--host", host])
    elif action == "power_cycle":
        return run_script("manage-pakedge-switch.py", ["power-cycle", "--wait", str(wait_sec), "--host", host])
    elif action == "configure_vlans":
        if not vlans: return "Error: 'vlans' definition string required."
        return run_script("manage-pakedge-switch.py", ["vlan-config", "--vlans", vlans, "--host", host])
    return f"Unknown action: '{action}'. Valid actions: status, backup, poe_cycle, power_cycle, configure_vlans."

@mcp.tool()
def manage_openwrt(
    action: Literal["status", "backup", "restore", "deploy_vxlan"] = "status",
    config_file: str | None = None,
    host: str = "192.168.1.226"
) -> str:
    """Manage Belkin AX3200 OpenWrt router (192.168.1.226).
    Actions:
      - 'status': Audit 3-priority failover state, Wi-Fi stations, interfaces, and routes.
      - 'backup': Export UCI firewall, network, and wireless configs to Git.
      - 'restore': Restore UCI configurations from Git backup archive.
      - 'deploy_vxlan': Deploy VXLAN MSS clamping and priority routing hardening."""
    action = action.lower().strip()
    if action == "status":
        return run_script("get-openwrt-status.py")
    elif action == "backup":
        return run_script("backup-openwrt-config.py")
    elif action == "restore":
        args = ["--file", config_file] if config_file else []
        return run_script("restore-openwrt-config.py", args)
    elif action == "deploy_vxlan":
        return run_script("deploy-vxlan-hardening.py")
    return f"Unknown action: '{action}'. Valid actions: status, backup, restore, deploy_vxlan."

@mcp.tool()
def manage_ddwrt(
    action: Literal["status", "backup", "restore"] = "status",
    router: Literal["all", "aurora", "luna"] = "all",
    config_file: str | None = None
) -> str:
    """Manage DD-WRT isolation routers (aurora: 10.25.25.1, luna: 10.20.20.1) over Dropbear SSH.
    Actions:
      - 'status': Check router uptime, WAN IP, WireGuard tunnel, and firewall rules.
      - 'backup': Export NVRAM variables and rc_firewall startup scripts encrypted via SOPS.
      - 'restore': Restore NVRAM configurations from Git backup."""
    action = action.lower().strip()
    if action == "status":
        return run_script("get-ddwrt-status.py")
    elif action == "backup":
        return run_script("backup-ddwrt-config.py", ["--router", router])
    elif action == "restore":
        args = ["--router", router]
        if config_file: args.extend(["--file", config_file])
        return run_script("restore-ddwrt-config.py", args)
    return f"Unknown action: '{action}'. Valid actions: status, backup, restore."


# ==============================================================================
# 4. NETWORK DIAGNOSTICS & TELEMETRY
# ==============================================================================

@mcp.tool()
def verify_network_matrix(
    profile: Literal["quick", "comprehensive"] = "quick",
    targets_file: str | None = None
) -> str:
    """Audits comprehensive cross-VLAN network reachability and latency across all 21 core targets.
    Profiles: 'quick' (ping latency) or 'comprehensive' (full TCP/UDP and inter-VLAN ACL matrix)."""
    args = ["--profile", profile]
    if targets_file:
        args.extend(["--targets", targets_file])
    return run_script("verify-network-matrix.py", args)

@mcp.tool()
def manage_wireshark(action: Literal["status", "sync_capture"] = "status") -> str:
    """Manage headless Wireshark SPAN sniffer on luna-server (VM 102).
    Actions:
      - 'status': Inspect ens19 SPAN packets/sec, capture daemon state, and NAS storage mount.
      - 'sync_capture': Re-sync running capture loop script to latest GitOps version."""
    action = action.lower().strip()
    if action == "status":
        return run_script("get-wireshark-status.py")
    elif action == "sync_capture":
        return run_script("sync-wireshark-capture-script.py")
    return f"Unknown action: '{action}'. Valid actions: status, sync_capture."

@mcp.tool()
def analyze_pcap_telemetry(
    path: str = "",
    focus: Literal["comprehensive", "summary", "l2_hygiene", "routing_matrix", "transport_health", "core_services", "security_anomalies"] = "comprehensive",
    vlan: int | None = None,
    max_files: int | None = None,
    max_packets: int | None = None,
    json_output: bool = False
) -> str:
    """High-throughput streaming diagnostic engine for PCAP/PCAPNG packet captures.
    Streams continuous ring buffers at >100,000 pkts/s using zero-copy binary unpacking.
    Focus options: 'comprehensive', 'summary', 'l2_hygiene', 'routing_matrix', 'transport_health', 'core_services', 'security_anomalies'.
    Optionally filter by VLAN ID (e.g. 10, 20, 30, 40, 150, 200)."""
    args = ["--focus", focus]
    if path: args.extend(["--path", path])
    if vlan is not None: args.extend(["--vlan", str(vlan)])
    if max_files is not None: args.extend(["--max-files", str(max_files)])
    if max_packets is not None: args.extend(["--max-packets", str(max_packets)])
    if json_output: args.append("--json")
    return run_script("analyze-pcap-telemetry.py", args)

@mcp.tool()
def query_pcap_flows(
    path: str = "",
    host: str | None = None,
    port: int | None = None,
    proto: Literal["tcp", "udp", "icmp", "arp"] | None = None,
    vlan: int | None = None,
    limit: int = 50,
    max_files: int = 10
) -> str:
    """Targeted flow query tool for matching packet conversations across PCAP/PCAPNG captures.
    Filter by host IP (e.g. '192.168.10.200'), port (e.g. 53), protocol ('tcp', 'udp', 'icmp', 'arp'), or VLAN ID."""
    args = ["--focus", "query_flows", "--limit", str(limit), "--max-files", str(max_files)]
    if path: args.extend(["--path", path])
    if host: args.extend(["--query-host", host])
    if port is not None: args.extend(["--query-port", str(port)])
    if proto: args.extend(["--query-proto", proto])
    if vlan is not None: args.extend(["--vlan", str(vlan)])
    return run_script("analyze-pcap-telemetry.py", args)


# ==============================================================================
# 5. EXTERNAL SERVICES & CLOUD VPS MANAGEMENT
# ==============================================================================

@mcp.tool()
def manage_external_services(
    action: Literal["status", "ssl", "email", "security", "whitelist"] = "status",
    ip: str | None = None
) -> str:
    """Manage external cloud services across Oracle Cloud (theurer.dev) and Google Cloud (mail.theurer.dev).
    Actions:
      - 'status'   : Comprehensive health audit (Nginx HTTP 200, Postfix SMTP :587, Dovecot IMAP :993).
      - 'ssl'      : Verify Let's Encrypt TLS certificate validity and expiration dates.
      - 'email'    : End-to-end email pipeline delivery audit (DNS SPF, DKIM, DMARC, SASL).
      - 'security' : Audit VPS firewall rules, fail2ban active jails, and SSH key enforcement.
      - 'whitelist': Whitelist an IP address across external VPS UFW and fail2ban firewalls."""
    action = action.lower().strip()
    if action == "status":
        return run_script("manage-external-services.py", ["status"])
    elif action == "ssl":
        return run_script("manage-external-services.py", ["ssl"])
    elif action == "email":
        return run_script("manage-external-services.py", ["email"])
    elif action == "security":
        return run_script("manage-external-services.py", ["security"])
    elif action == "whitelist":
        if not ip: return "Error: 'ip' is required for whitelist action."
        return run_script("manage-external-services.py", ["whitelist", "--ip", ip])
    return f"Unknown action: '{action}'. Valid actions: status, ssl, email, security, whitelist."

@mcp.tool()
def manage_external_hosts(
    action: Literal["audit", "backup", "deploy_promtail"] = "audit",
    target: Literal["all", "web", "email"] = "all"
) -> str:
    """Manage external VPS host configurations and monitoring daemons.
    Actions:
      - 'audit'          : Audit drift on external VPS instances (web-server, email-server, or all).
      - 'backup'         : Backup Nginx configs, Postfix/Dovecot configs, and databases to Git.
      - 'deploy_promtail': Deploy and configure Promtail log shipping to Loki on nexus-server."""
    action = action.lower().strip()
    if action == "audit":
        return run_script("manage-external-hosts.py", ["audit", "--host", target])
    elif action == "backup":
        return run_script("manage-external-hosts.py", ["backup", "--host", target])
    elif action == "deploy_promtail":
        return run_script("deploy-external-promtail.py")
    return f"Unknown action: '{action}'. Valid actions: audit, backup, deploy_promtail."


# ==============================================================================
# 6. IDENTITY, OVRC & DHCP CLIENT ALIGNMENT
# ==============================================================================

@mcp.tool()
def sync_adguard_clients(
    host: str = "http://192.168.40.185:8081",
    user: str | None = None,
    password: str | None = None,
    dry_run: bool = False
) -> str:
    """Synchronizes authoritative DHCP reservations into AdGuard Home's Persistent Clients table via REST API.
    Applied to Primary AdGuard Home (nexus-server); adguardhome-sync automatically mirrors to Secondary AdGuard Home."""
    args = ["--host", host]
    if user: args.extend(["--user", user])
    if password: args.extend(["--password", password])
    if dry_run: args.append("--dry-run")
    return run_script("sync-adguard-clients.py", args)

@mcp.tool()
def align_ovrc_devices(
    action: Literal["preview", "csv", "apply", "scan", "status"] = "preview",
    token: str | None = None,
    user: str | None = None,
    password: str | None = None,
    ovrc_csv: str = "",
    reservations: str = "",
    output: str = ""
) -> str:
    """Correlates, aligns, and synchronizes OvrC device names with authoritative DHCP reservations.
    Credentials can be loaded automatically from infrastructure/secrets/ovrc.enc.yaml via SOPS.
    Actions:
      - 'status' : Display OvrC location details, device count, and Unspecified device count.
      - 'scan'   : Trigger a fresh network discovery scan via OvrC Cloud API.
      - 'preview': Non-destructive correlation diff showing devices to rename (default).
      - 'csv'    : Export enriched blueprint (ovrc-device-list-aligned.csv) with accurate names & rooms.
      - 'apply'  : Connect to live OvrC Cloud API and apply device names & room assignments."""
    args = [action]
    if token: args.extend(["--token", token])
    if user: args.extend(["--user", user])
    if password: args.extend(["--password", password])
    if ovrc_csv: args.extend(["--ovrc-csv", ovrc_csv])
    if reservations: args.extend(["--reservations", reservations])
    if output: args.extend(["--output", output])
    return run_script("align-ovrc-devices.py", args)


# ==============================================================================
# BACKWARDS-COMPATIBLE HELPER EXPORTS
# ==============================================================================
# Allows scripts and runbooks to import top-level functions directly from server:
def generate_stack_index():
    return manage_stacks(action="index")

def backup_araknis_router():
    return manage_araknis_router(action="backup")

def backup_araknis_switch():
    return manage_araknis_switch(action="backup")

def backup_netgear_switch():
    return manage_netgear_switch(action="backup")

def backup_pakedge_switch():
    return manage_pakedge_switch(action="backup")

def backup_openwrt():
    return manage_openwrt(action="backup")

def backup_ddwrt(router: str = "all"):
    return manage_ddwrt(action="backup", router=router)

def backup_apt_packages():
    return manage_apt_packages(action="backup")

def sync_wireshark_capture():
    return manage_wireshark(action="sync_capture")

def backup_external_host(target: str = "all"):
    return manage_external_hosts(action="backup", target=target)


if __name__ == "__main__":
    mcp.run()
