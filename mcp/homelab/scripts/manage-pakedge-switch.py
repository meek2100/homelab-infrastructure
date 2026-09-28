#!/usr/bin/env python3
"""
Pakedge SX-8P Managed Switch Driver & Testbench Manager
Interacts with the Pakedge SX-8P switch (192.168.1.205) connected to Port 1/0/7
on the Araknis 920 Managed Switch.

Note:
  The Pakedge SX-8P switch is a dedicated testbench switch for work/lab devices
  (VLAN 150 CA-1, VLAN 200 Core-5, touchscreens). It is powered down when idle
  and does not require 24/7 uptime SLOs.

Actions:
  - status: Checks reachability, HTTP, Telnet, and queries Araknis 920 Port 1/0/7 for MAC table and link status.
  - backup: Backs up the running configuration to GitOps.
  - poe-cycle: Power cycles Port 1/0/7 on the Araknis 920 switch to reboot the testbench.
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    requests = None

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_TARGET_FILE = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "pakedge-sx8p-running.cfg")
SECRET_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "pakedge-switch.enc.yaml")

DEFAULT_SWITCH_IP = "192.168.1.205"
ARAKNIS_PORT = 7

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
    """Load switch credentials from env or SOPS encrypted secrets."""
    user = os.environ.get("PAKEDGE_USER")
    password = os.environ.get("PAKEDGE_PASSWORD")
    if user and password:
        return user, password

    candidates = [
        SECRET_FILE,
        os.path.join(REPO_ROOT, "infrastructure", "secrets", "araknis-switch.enc.yaml")
    ]
    for s_file in candidates:
        if os.path.exists(s_file):
            sops_bin = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
            if sops_bin and os.path.exists(sops_bin):
                key_file = get_age_key_path()
                env = os.environ.copy()
                if key_file:
                    env["SOPS_AGE_KEY_FILE"] = key_file
                try:
                    res = subprocess.run([sops_bin, "-d", s_file], capture_output=True, text=True, check=True, env=env)
                    data = yaml.safe_load(res.stdout) if yaml else {}
                    if "pakedge_switch" in data:
                        return data["pakedge_switch"].get("username", "pakedge"), data["pakedge_switch"].get("password")
                    if "pakedge_password" in data:
                        return data.get("pakedge_username", "pakedge"), data["pakedge_password"]
                except Exception:
                    pass
    return None, None

def check_tcp_port(host: str, port: int, timeout: float = 1.0) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        s.close()

def get_uplink_status() -> dict:
    """Queries Araknis 920 switch for Port 1/0/7 link state and learned MAC table."""
    script_path = os.path.join(os.path.dirname(__file__), "manage-araknis-switch.py")
    venv_py = os.path.join(REPO_ROOT, ".venv", "bin", "python3")
    py_bin = venv_py if os.path.exists(venv_py) else sys.executable
    cmd = [
        py_bin, "-c",
        f"""
import sys, os
sys.path.append('{os.path.dirname(__file__)}')
mod = __import__('manage-araknis-switch')
host, user, password = mod.load_credentials()
client, chan = mod.connect_switch(host, user, password)
out_mac = mod._send_cmd(chan, 'show mac-addr-table interface 1/0/{ARAKNIS_PORT}')
out_int = mod._send_cmd(chan, 'show interfaces status 1/0/{ARAKNIS_PORT}')
client.close()
import json
print(json.dumps({{'mac_table': out_mac, 'interface_status': out_int}}))
"""
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            for line in reversed(lines):
                if line.startswith("{"):
                    return json.loads(line)
        return {"error": res.stderr.strip() or "Failed to query switch"}
    except Exception as e:
        return {"error": str(e)}

def cmd_status(host: str = DEFAULT_SWITCH_IP) -> dict:
    http_open = check_tcp_port(host, 80)
    telnet_open = check_tcp_port(host, 23)
    is_online = http_open or telnet_open
    
    uplink = get_uplink_status()
    
    # Parse learned MACs if available
    macs = []
    if "mac_table" in uplink:
        for line in uplink["mac_table"].splitlines():
            line = line.strip()
            if line and line[0].isalnum() and ":" in line:
                parts = line.split()
                if len(parts) >= 2:
                    macs.append({"mac": parts[0], "vlan": parts[1]})

    return {
        "device": "Pakedge SX-8P Managed Switch",
        "ip": host,
        "online": is_online,
        "services": {
            "http_80": "open" if http_open else "closed",
            "telnet_23": "open" if telnet_open else "closed"
        },
        "uplink": {
            "upstream_switch": "Araknis 920 (192.168.1.215)",
            "port": f"1/0/{ARAKNIS_PORT}",
            "role": "Trunk (VLAN 1, 150 CA-1, 200 Core-5)",
            "learned_mac_count": len(macs),
            "learned_macs": macs
        },
        "note": "Work automation testbench switch. Powered off when idle. Exempt from 24/7 SLA."
    }

def cmd_backup(host: str = DEFAULT_SWITCH_IP) -> dict:
    """Attempts to pull running configuration backup from Pakedge web GUI."""
    if not requests:
        return {"status": "error", "error": "python requests library is required"}

    if not check_tcp_port(host, 80):
        return {
            "status": "error",
            "error": f"Switch at {host}:80 is unreachable. Is the switch powered on via Araknis Port 1/0/7?"
        }

    user, password = load_credentials()
    if not user or not password:
        return {
            "status": "notice",
            "message": "Pakedge SX-8P backup protocol ready. Provide switch credentials in infrastructure/secrets/pakedge-switch.enc.yaml (or env PAKEDGE_USER / PAKEDGE_PASSWORD) to enable automated CGI export.",
            "target": CONFIG_TARGET_FILE
        }

    session = requests.Session()
    login_url = f"http://{host}/cgi/set.cgi?cmd=home_loginAuth"
    status_url = f"http://{host}/cgi/get.cgi?cmd=home_loginStatus"
    data = {"login_username": user, "login_password": password}

    try:
        r = session.post(login_url, data=data, timeout=5)
        sr = session.get(status_url, timeout=5)
        if "loginSuccess" not in r.text and "loginSuccess" not in sr.text:
            return {
                "status": "error",
                "error": f"Login failed for user '{user}': {r.text.strip() or sr.text.strip()}"
            }

        # Trigger file backup and pull config
        session.post(f"http://{host}/cgi/set.cgi?cmd=file_backup", timeout=5)
        time.sleep(1)
        cfg_res = session.get(f"http://{host}/cgi/get.cgi?cmd=file_cfg", timeout=10)

        if cfg_res.status_code == 200 and len(cfg_res.content) > 0:
            os.makedirs(os.path.dirname(CONFIG_TARGET_FILE), exist_ok=True)
            with open(CONFIG_TARGET_FILE, "wb") as f:
                f.write(cfg_res.content)
            return {
                "status": "success",
                "bytes": len(cfg_res.content),
                "target": CONFIG_TARGET_FILE,
                "message": f"Successfully backed up Pakedge SX-8P configuration ({len(cfg_res.content)} bytes)"
            }
        else:
            return {"status": "error", "error": f"Failed to download config file: HTTP {cfg_res.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def cmd_poe_cycle(port: int = ARAKNIS_PORT) -> dict:
    """Power-cycles Port 1/0/7 on Araknis 920 switch."""
    script_path = os.path.join(os.path.dirname(__file__), "manage-araknis-switch.py")
    venv_py = os.path.join(REPO_ROOT, ".venv", "bin", "python3")
    py_bin = venv_py if os.path.exists(venv_py) else sys.executable
    cmd = [py_bin, script_path, "poe-cycle", "--port", str(port)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "status": "success" if res.returncode == 0 else "error",
            "output": res.stdout.strip(),
            "error": res.stderr.strip() if res.returncode != 0 else ""
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Pakedge SX-8P Managed Switch Automation")
    parser.add_argument("action", choices=["status", "poe-cycle", "backup"], help="Action to perform")
    parser.add_argument("--host", default=DEFAULT_SWITCH_IP, help="Pakedge switch IP")
    parser.add_argument("--port", type=int, default=ARAKNIS_PORT, help="Araknis PoE port (default 7)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    if args.action == "status":
        res = cmd_status(args.host)
    elif args.action == "poe-cycle":
        res = cmd_poe_cycle(args.port)
    elif args.action == "backup":
        res = cmd_backup(args.host)

    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
