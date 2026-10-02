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
    session.cookies.set("usa_Pakedge_user", f"{user}|0", domain=host, path="/")

    login_url = f"http://{host}/cgi/set.cgi?cmd=home_loginAuth"
    status_url = f"http://{host}/cgi/get.cgi?cmd=home_loginStatus"
    data = {
        "_ds": "1",
        "username": user,
        "password": password,
        "_de": "1"
    }

    try:
        r = session.post(login_url, data=data, timeout=5)
        time.sleep(0.5)
        sr = session.get(status_url, timeout=5)
        
        status_data = sr.json().get("data", {}) if sr.status_code == 200 else {}
        if status_data.get("status") != "ok":
            fail_reason = status_data.get("failReason", r.text.strip())
            return {
                "status": "error",
                "error": f"Login failed for user '{user}': {fail_reason}"
            }

        # Trigger HTTP file backup
        backup_payload = {
            "_ds": "1",
            "cfg_action": "backup",
            "method": "http",
            "fileType": "running",
            "_de": "1"
        }
        b_resp = session.post(f"http://{host}/cgi/set.cgi?cmd=file_backup", data=backup_payload, timeout=5)
        b_data = b_resp.json() if b_resp.status_code == 200 else {}

        if b_data.get("status") != "ok" or "filename" not in b_data:
            return {
                "status": "error",
                "error": f"Failed to generate backup: {b_resp.text.strip()}"
            }

        remote_filename = b_data["filename"]
        download_url = f"http://{host}/{remote_filename}" if not remote_filename.startswith("http") else remote_filename

        cfg_res = session.get(download_url, timeout=10)
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


def cmd_configure_vlans(host: str = DEFAULT_SWITCH_IP) -> dict:
    """Apply the standard VLAN layout to Pakedge SX-8P via Telnet CLI.

    Port assignment:
      gi1: Hybrid trunk, PVID=1, tagged 10,150,200 -> Araknis 920 1/0/7 (allowed 1,10,150,200)
      gi2: Access VLAN 10 (Control4 DS2 Door Station)
      gi3: Access VLAN 10 (Luma X20 Cam 3)
      gi4: Access VLAN 10 (Luma X20 Cam 2)
      gi5: Access VLAN 10 (Luma X20 Cam 1)
      gi6: Access VLAN 10 (Pakedge PoE switch — confirm device)
      gi7: Access VLAN 10 (Unmanaged switch: C4 Core Lite, EA-1, Luma Bridge)
      gi8: Access VLAN 150 (Control4 CA-1 Controller)

    Layout matches the live switch as of 2026-09-29 (VLANs 20/30/40/100 pruned).
    Commands are additive only: this does not remove VLANs or tagged memberships that
    already exist, so run it on a factory-reset or already-aligned switch.

    NOTE: Uses Telnet CLI (port 23) -- the only reliable method for VLAN config.
    If Telnet has been disabled on the switch, this action cannot run.
    The CGI pkg_vlanWizard wipes all custom VLANs back to factory default.
    The CGI pkg_vlanAccess/Hybrid does not persist PVID to startup-config.
    """
class SwitchTelnet:
    """Socket-based Telnet client handling RFC 854 option negotiations."""
    def __init__(self, host: str, port: int = 23, timeout: float = 5.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(2.0)

    def _recv(self, timeout: float = 2.0) -> str:
        buf = bytearray()
        self.s.settimeout(timeout)
        start = time.time()
        while time.time() - start < timeout:
            try:
                chunk = self.s.recv(1024)
                if not chunk:
                    break
            except socket.timeout:
                break
            i = 0
            while i < len(chunk):
                if chunk[i] == 255 and i + 2 < len(chunk):
                    cmd, opt = chunk[i+1], chunk[i+2]
                    if cmd == 253:  # DO -> reply WONT
                        self.s.sendall(bytes([255, 252, opt]))
                    elif cmd == 251:  # WILL -> reply DO
                        self.s.sendall(bytes([255, 253, opt]))
                    elif cmd == 254:  # DONT -> reply WONT
                        self.s.sendall(bytes([255, 252, opt]))
                    elif cmd == 252:  # WONT -> reply DONT
                        self.s.sendall(bytes([255, 254, opt]))
                    i += 3
                else:
                    buf.append(chunk[i])
                    i += 1
            if b"SX-8P#" in buf or b"Username:" in buf or b"Password:" in buf:
                break
        return bytes(buf).decode("latin1", errors="replace")

    def login(self, user: str, password: str) -> bool:
        txt = self._recv()
        if "Username:" in txt:
            self.s.sendall(user.encode("latin1") + b"\r\n")
            txt2 = self._recv()
            if "Password:" in txt2:
                self.s.sendall(password.encode("latin1") + b"\r\n")
                txt3 = self._recv()
                return "SX-8P#" in txt3 or ">" in txt3
        return "SX-8P#" in txt

    def cmd(self, command: str, wait: float = 0.5) -> str:
        self.s.sendall(command.encode("latin1") + b"\r\n")
        time.sleep(wait)
        return self._recv(timeout=2.0)

    def close(self):
        try:
            self.s.sendall(b"exit\r\n")
            time.sleep(0.3)
            self.s.close()
        except Exception:
            pass


def cmd_configure_vlans(host: str = DEFAULT_SWITCH_IP) -> dict:
    """Apply the standard VLAN layout to Pakedge SX-8P via Telnet CLI.

    Port assignment:
      gi1: Hybrid trunk, PVID=1, tagged 10,150,200 -> Araknis 920 1/0/7 (allowed 1,10,150,200)
      gi2: Access VLAN 10 (Control4 DS2 Door Station)
      gi3: Access VLAN 10 (Luma X20 Cam 3)
      gi4: Access VLAN 10 (Luma X20 Cam 2)
      gi5: Access VLAN 10 (Luma X20 Cam 1)
      gi6: Access VLAN 10 (Pakedge PoE switch)
      gi7: Access VLAN 10 (Unmanaged switch: C4 Core Lite, EA-1, Luma Bridge)
      gi8: Access VLAN 150 (Control4 CA-1 Controller)

    Layout matches the live switch as of 2026-09-29 (VLANs 20/30/40/100 pruned).
    """
    if not check_tcp_port(host, 23):
        return {"status": "error", "error": f"Telnet port 23 not reachable on {host}. Is the switch powered on?"}

    user, password = load_credentials()
    if not user or not password:
        return {"status": "error", "error": "Could not load credentials from pakedge-switch.enc.yaml"}

    try:
        client = SwitchTelnet(host)
        logged_in = client.login(user, password)
        if not logged_in:
            # Fall back to default credentials if newly factory-reset
            logged_in = client.login("pakedge", "pakedges")
        if not logged_in:
            client.close()
            return {"status": "error", "error": f"Failed to authenticate as {user} or pakedge"}

        client.cmd("configure")

        # Create VLANs
        client.cmd("vlan 10,150,200")
        client.cmd("exit")
        for vid, name in [(10, "Main-Trusted"), (150, "CA1-Test"), (200, "Core5-Test")]:
            client.cmd(f"vlan {vid}")
            client.cmd(f"name {name}")
            client.cmd("exit")

        # Port 1: Hybrid trunk uplink to Araknis 920 Port 1/0/7
        client.cmd("interface gi1")
        client.cmd("switchport mode hybrid")
        client.cmd("switchport hybrid pvid 1")
        client.cmd('description "Trunk-Araknis920-Port7"')
        for vid in [10, 150, 200]:
            client.cmd(f"switchport hybrid allowed vlan add {vid} tagged")
        client.cmd("exit")

        # Ports 2-7: Access VLAN 10 (main-system test gear)
        access_ports = {
            2: "Control4-DS2-DoorStation",
            3: "LumaX20-Cam3",
            4: "LumaX20-Cam2",
            5: "LumaX20-Cam1",
            6: "Pakedge-PoE-Switch",
            7: "C4Core-EA1-Luma-UnmgdSW",
        }
        for port, desc in access_ports.items():
            client.cmd(f"interface gi{port}")
            client.cmd("switchport mode access")
            client.cmd("switchport access vlan 10")
            client.cmd(f'description "{desc}"')
            client.cmd("exit")

        # Port 8: Access VLAN 150 (Control4 CA-1 Controller)
        client.cmd("interface gi8")
        client.cmd("switchport mode access")
        client.cmd("switchport access vlan 150")
        client.cmd('description "Control4-CA1-Controller"')
        client.cmd("exit")

        # System Services & Protocols
        client.cmd("clock source sntp")
        client.cmd("sntp host time.google.com port 123")
        client.cmd("clock timezone PST -8 minutes 0")
        client.cmd("clock summer-time PDT recurring usa")
        client.cmd("ip dns 192.168.40.185")
        client.cmd("ip dns lookup")
        client.cmd("no snmp community public")
        client.cmd("snmp community homelab-metrics ro")
        client.cmd("logging host 192.168.40.185")

        client.cmd("no spanning-tree")
        client.cmd("end")
        vlan_table = client.cmd("show vlan", wait=1.5)
        save_out = client.cmd("save", wait=2.5)
        client.close()

        return {
            "status": "success",
            "message": "VLAN, DNS, SNTP, SNMP, and system configuration applied and saved to startup-config",
            "vlan_table": vlan_table.strip(),
            "save": "Success" if "Success" in save_out else save_out.strip()[-80:],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def cmd_poe_port_cycle(port: int, wait_sec: float = 3.0, host: str = DEFAULT_SWITCH_IP) -> dict:
    """Power-cycles an individual PoE port (1-8) on the Pakedge switch."""
    if not (1 <= port <= 8):
        return {"status": "error", "error": f"Invalid port {port}. Must be 1-8"}

    user, password = load_credentials()
    try:
        client = SwitchTelnet(host)
        if not client.login(user, password) and not client.login("pakedge", "pakedges"):
            client.close()
            return {"status": "error", "error": "Login failed"}

        client.cmd("configure")
        client.cmd(f"interface gi{port}")
        client.cmd("power inline disable", wait=0.5)
        time.sleep(wait_sec)
        client.cmd("power inline enable", wait=0.5)
        client.cmd("exit")
        client.cmd("end")
        client.close()
        return {
            "status": "success",
            "port": f"gi{port}",
            "message": f"Successfully power-cycled PoE on Pakedge switch port gi{port} (waited {wait_sec}s)"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Pakedge SX-8P Managed Switch Automation")
    parser.add_argument(
        "action",
        choices=["status", "poe-cycle", "backup", "configure-vlans", "poe-port-cycle"],
        help="Action to perform",
    )
    parser.add_argument("--host", default=DEFAULT_SWITCH_IP, help="Pakedge switch IP")
    parser.add_argument("--port", type=int, default=ARAKNIS_PORT, help="Port number (Araknis port for poe-cycle; Pakedge 1-8 for poe-port-cycle)")
    parser.add_argument("--wait", type=float, default=3.0, help="Wait time in seconds for poe-port-cycle")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    if args.action == "status":
        res = cmd_status(args.host)
    elif args.action == "poe-cycle":
        res = cmd_poe_cycle(args.port)
    elif args.action == "backup":
        res = cmd_backup(args.host)
    elif args.action == "configure-vlans":
        res = cmd_configure_vlans(args.host)
    elif args.action == "poe-port-cycle":
        res = cmd_poe_port_cycle(args.port, args.wait, args.host)

    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()

