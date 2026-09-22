#!/usr/bin/env python3
"""
Netgear GS108Ev2 Switch Management & Automation Tool
Interacts with the Netgear GS108Ev2 switch (192.168.1.220) via HTTP web management interface.
Supports:
  - Configuration backup (system metadata, port configurations, VLANs, IGMP, rate limits)
  - Port status and operational health inspection (link speed, packet counters, CRC errors)
  - Integration with SOPS-encrypted credentials
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, is_dataclass

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_BACKUP_FILE = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "netgear-gs108e-backup.json")
SECRET_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "araknis-switch.enc.yaml")

DEFAULT_SWITCH_IP = "192.168.1.220"


def get_age_key_path():
    for candidate in [
        os.path.join(REPO_ROOT, "homelab-infrastructure.key"),
        os.path.join(REPO_ROOT, "master-age-key.txt"),
        os.path.expanduser("~/.config/sops/age/keys.txt"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return None


def load_credentials():
    """Load Netgear switch credentials from SOPS-encrypted file or environment."""
    host = os.environ.get("NETGEAR_HOST", DEFAULT_SWITCH_IP)
    password = os.environ.get("NETGEAR_PASSWORD")

    if password:
        return host, password

    if os.path.exists(SECRET_FILE):
        sops_bin = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
        if not sops_bin or not os.path.exists(sops_bin):
            raise RuntimeError(f"sops binary not found to decrypt {SECRET_FILE}")

        key_file = get_age_key_path()
        env = os.environ.copy()
        if key_file:
            env["SOPS_AGE_KEY_FILE"] = key_file

        res = subprocess.run([sops_bin, "-d", SECRET_FILE], capture_output=True, text=True, env=env)
        if res.returncode == 0:
            if yaml:
                data = yaml.safe_load(res.stdout)
            else:
                data = json.loads(res.stdout)

            # Check netgear specific keys first, fallback to generic switch credentials
            host = data.get("netgear_switch_ip", data.get("netgear_ip", host))
            password = data.get("netgear_password", data.get("password"))
            if password:
                return host, str(password)
        else:
            sys.stderr.write(f"Warning: SOPS decryption failed: {res.stderr}\n")

    # Fallback default password for unconfigured Netgear Plus switches
    return host, "password"


def _serialize(obj):
    """Recursively convert dataclass / IntEnum objects to JSON-serializable primitives."""
    if is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def connect_switch(host, password, timeout=10.0):
    """Attempt connection using netgear_tool, with fallback to py_netgear_plus."""
    errors = []

    # 1. Primary: netgear-tool
    try:
        import netgear_tool
        sw = netgear_tool.make_switch(host, password=password, timeout=timeout)
        return "netgear_tool", sw
    except Exception as e:
        errors.append(f"netgear-tool: {e}")

    # 2. Secondary fallback: py-netgear-plus
    try:
        from py_netgear_plus import NetgearSwitchConnector
        conn = NetgearSwitchConnector(host, password)
        model = conn.autodetect_model()
        return "py_netgear_plus", (conn, model)
    except Exception as e:
        errors.append(f"py-netgear-plus: {e}")

    raise RuntimeError(
        f"Unable to connect to Netgear switch at {host}. Attempted drivers failed:\n"
        + "\n".join(f"  - {err}" for err in errors)
        + "\n\nNote: If the switch is only accessible via ProSAFE Plus Utility, ensure 'Switch Management Mode' "
        "is set to 'Web browser and Plus Utility' in the utility."
    )


def cmd_status(driver_type, client):
    """Retrieve operational status and health metrics."""
    if driver_type == "netgear_tool":
        sw = client
        with sw:
            sys_info = _serialize(sw.get_system_info())
            cfg = _serialize(sw.get_switch_config())
            ports = [_serialize(p) for p in sw.get_port_settings()]
            stats = [_serialize(p) for p in sw.get_port_stats()]
            pvids = sw.get_port_pvids()

        summary_lines = [
            f"=== Netgear GS108Ev2 Status ({cfg.get('ip', 'N/A')}) ===",
            f"Model:    {cfg.get('model', 'GS108Ev2')}",
            f"Name:     {cfg.get('name', 'N/A')}",
            f"Firmware: {cfg.get('firmware', 'N/A')}",
            f"MAC:      {cfg.get('mac', 'N/A')}",
            f"Gateway:  {cfg.get('gateway', 'N/A')}",
            "",
            "Port Status:",
            f"{'Port':<6} {'State':<8} {'Speed Config':<14} {'Actual Speed':<14} {'RX Bytes':<12} {'TX Bytes':<12} {'CRC Errors':<10}",
            "-" * 80,
        ]

        stats_by_port = {s["port"]: s for s in stats}
        for p in ports:
            port_num = p["port"]
            st = stats_by_port.get(port_num, {})
            state_str = "UP" if p.get("enabled") else "DOWN"
            speed_cfg = str(p.get("speed_cfg", "Auto"))
            speed_act = p.get("speed_act", "No Speed")
            rx = st.get("bytes_rx", 0)
            tx = st.get("bytes_tx", 0)
            crc = st.get("crc_errors", 0)
            summary_lines.append(
                f"{port_num:<6} {state_str:<8} {speed_cfg:<14} {speed_act:<14} {rx:<12} {tx:<12} {crc:<10}"
            )

        return {
            "status": "success",
            "driver": "netgear-tool",
            "summary": "\n".join(summary_lines),
            "system_info": sys_info,
            "switch_config": cfg,
            "ports": ports,
            "port_statistics": stats,
            "pvids": pvids,
        }

    else:
        conn, model = client
        infos = conn.get_switch_infos()
        return {
            "status": "success",
            "driver": "py-netgear-plus",
            "model": model.MODEL_NAME,
            "switch_info": infos,
        }


def cmd_backup(driver_type, client):
    """Retrieve full switch configuration and export to gitops repository."""
    if driver_type == "netgear_tool":
        sw = client
        with sw:
            sys_info = _serialize(sw.get_system_info())
            cfg = _serialize(sw.get_switch_config())
            ports = [_serialize(p) for p in sw.get_port_settings()]
            stats = [_serialize(p) for p in sw.get_port_stats()]
            pvids = sw.get_port_pvids()

            # Optional advanced features
            def safe_get(fn):
                try:
                    return _serialize(fn())
                except Exception:
                    return None

            vlans = safe_get(sw.get_vlan_ids)
            vlan_members = {}
            if vlans:
                for vid in vlans:
                    try:
                        vlan_members[vid] = _serialize(sw.get_vlan_membership(vid))
                    except Exception:
                        pass

            rate_limits = safe_get(sw.get_rate_limits)
            igmp = safe_get(sw.get_igmp_config)
            mirror = safe_get(sw.get_mirror_config)
            loop_detect = safe_get(sw.get_loop_detection)
            power_saving = safe_get(sw.get_power_saving)
            qos = safe_get(sw.get_qos_mode)
            bcast_filter = safe_get(sw.get_broadcast_filter)

        backup_payload = {
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "system_info": sys_info,
            "switch_config": cfg,
            "ports": ports,
            "port_statistics": stats,
            "pvids": pvids,
            "vlans": vlans,
            "vlan_members": vlan_members,
            "rate_limits": rate_limits,
            "igmp_snooping": igmp,
            "port_mirroring": mirror,
            "loop_detection": loop_detect,
            "power_saving": power_saving,
            "qos_mode": qos,
            "broadcast_filter": bcast_filter,
        }

        os.makedirs(os.path.dirname(CONFIG_BACKUP_FILE), exist_ok=True)
        with open(CONFIG_BACKUP_FILE, "w") as f:
            json.dump(backup_payload, f, indent=2)

        return {
            "status": "success",
            "file": CONFIG_BACKUP_FILE,
            "model": cfg.get("model", "GS108Ev2"),
            "ip": cfg.get("ip", DEFAULT_SWITCH_IP),
            "bytes": os.path.getsize(CONFIG_BACKUP_FILE),
            "ports_backed_up": len(ports),
        }

    else:
        conn, model = client
        infos = conn.get_switch_infos()
        backup_payload = {
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": model.MODEL_NAME,
            "switch_info": infos,
        }
        os.makedirs(os.path.dirname(CONFIG_BACKUP_FILE), exist_ok=True)
        with open(CONFIG_BACKUP_FILE, "w") as f:
            json.dump(backup_payload, f, indent=2)

        return {
            "status": "success",
            "file": CONFIG_BACKUP_FILE,
            "model": model.MODEL_NAME,
            "bytes": os.path.getsize(CONFIG_BACKUP_FILE),
        }


def main():
    parser = argparse.ArgumentParser(description="Netgear GS108Ev2 Switch Management Tool")
    parser.add_argument("action", choices=["status", "backup"], help="Action to execute")
    parser.add_argument("--ip", default=None, help=f"Target switch IP (default: {DEFAULT_SWITCH_IP})")
    parser.add_argument("--password", default=None, help="Switch admin password (default: from SOPS or env)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    host, sops_pw = load_credentials()
    target_ip = args.ip or host
    target_password = args.password or sops_pw

    try:
        driver_type, client = connect_switch(target_ip, target_password)

        if args.action == "status":
            result = cmd_status(driver_type, client)
            if args.json or "summary" not in result:
                print(json.dumps(result, indent=2))
            else:
                print(result["summary"])
        elif args.action == "backup":
            result = cmd_backup(driver_type, client)
            print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
