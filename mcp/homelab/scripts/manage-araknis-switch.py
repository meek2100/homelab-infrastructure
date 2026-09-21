#!/usr/bin/env python3
"""
Araknis 920 Switch Management & Automation Tool (FASTPATH CLI)
Interacts with the Araknis 920 switch (192.168.1.215) over SSH via Paramiko.
Supports:
  - Configuration backup (running-config to gitops)
  - Port status and MAC table inspection
  - Spanning tree and IGMP snooping checks
  - Hardware PoE port power-cycling
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_TARGET_FILE = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "araknis-920-running.cfg")
SECRET_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "araknis-switch.enc.yaml")

DEFAULT_SWITCH_IP = "192.168.1.215"
DEFAULT_USER = "meek2100"

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
    """Load switch credentials from SOPS-encrypted file or environment."""
    user = os.environ.get("ARAKNIS_USER", DEFAULT_USER)
    password = os.environ.get("ARAKNIS_PASSWORD")
    host = os.environ.get("ARAKNIS_HOST", DEFAULT_SWITCH_IP)

    if password:
        return host, user, password

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
            host = data.get("switch_ip", host)
            user = data.get("username", user)
            password = data.get("password")
            if password:
                return host, user, password
        else:
            sys.stderr.write(f"Warning: SOPS decryption failed: {res.stderr}\n")

    raise RuntimeError(
        "Switch password not found. Either provide ARAKNIS_PASSWORD in environment "
        f"or create encrypted SOPS secret at {SECRET_FILE}"
    )

def connect_switch(host, user, password, timeout=15):
    """Establish interactive SSH shell connection using Paramiko."""
    try:
        import paramiko
    except ImportError:
        raise RuntimeError("paramiko is required. Run: .venv/bin/pip install paramiko")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=22,
        username=user,
        password=password,
        look_for_keys=False,
        allow_agent=False,
        timeout=timeout,
    )

    chan = client.invoke_shell(term="vt100", width=200, height=5000)
    chan.settimeout(timeout)

    # Read initial banner until prompt
    _read_until_prompt(chan, timeout=10)

    # Disable pagination
    _send_cmd(chan, "terminal length 0")

    return client, chan

def _read_until_prompt(chan, prompt_regex=r"[\(].*?[\)]#\s*$", timeout=10):
    buf = ""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if chan.recv_ready():
            chunk = chan.recv(4096).decode("utf-8", errors="ignore")
            buf += chunk
            if re.search(prompt_regex, buf):
                return buf
            if "--More--" in buf:
                chan.send(" ")
        time.sleep(0.05)
    return buf

def _send_cmd(chan, cmd, timeout=15):
    # Flush existing buffer
    while chan.recv_ready():
        chan.recv(4096)

    chan.send(cmd.strip() + "\n")
    out = _read_until_prompt(chan, timeout=timeout)

    # Clean echoed command from the beginning and prompt from the end
    lines = out.replace("\r\n", "\n").split("\n")
    if lines and cmd.strip() in lines[0]:
        lines = lines[1:]
    if lines and re.search(r"[\(].*?[\)]#", lines[-1]):
        lines = lines[:-1]

    # Clean any lingering --More-- or backspaces
    cleaned = []
    for line in lines:
        cleaned_line = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line)
        cleaned_line = re.sub(r"[\b\r]", "", cleaned_line)
        cleaned.append(cleaned_line)

    return "\n".join(cleaned).strip()

def cmd_backup(chan):
    """Fetch running-config and save to repository."""
    raw_config = _send_cmd(chan, "show running-config", timeout=25)
    if not raw_config or "!Current Configuration:" not in raw_config:
        return {"status": "error", "message": "Failed to retrieve full running-config", "raw": raw_config}

    # Secrets hygiene: Redact password hashes
    redacted = re.sub(r'(username\s+"[^"]+"\s+password\s+)[a-fA-F0-9]{32,}(\s+level\s+15\s+encrypted)',
                      r'\1***REDACTED***\2', raw_config)

    os.makedirs(os.path.dirname(CONFIG_TARGET_FILE), exist_ok=True)
    with open(CONFIG_TARGET_FILE, "w") as f:
        f.write(redacted + "\n")

    return {
        "status": "success",
        "file": CONFIG_TARGET_FILE,
        "bytes": len(redacted),
        "lines": len(redacted.splitlines())
    }

def cmd_status(chan):
    """Retrieve structured operational status."""
    ports = _send_cmd(chan, "show port all", timeout=15)
    macs = _send_cmd(chan, "show mac-addr-table", timeout=15)
    stp = _send_cmd(chan, "show spanning-tree", timeout=10)
    igmp = _send_cmd(chan, "show igmpsnooping", timeout=10)
    monitor = _send_cmd(chan, "show monitor session 1", timeout=10)

    return {
        "status": "success",
        "ports": ports,
        "mac_table": macs,
        "spanning_tree": stp,
        "igmp_snooping": igmp,
        "span_monitor": monitor
    }

def cmd_poe_cycle(chan, port):
    """Power-cycle PoE on a specific port (e.g., 1/0/3)."""
    if not re.match(r"^1/0/[0-9]+$", port):
        return {"status": "error", "message": f"Invalid port format: {port}. Expected format: 1/0/X"}

    commands = [
        "configure",
        f"interface {port}",
        "poe mode shutdown",
        "exit",
        "exit"
    ]
    for c in commands:
        _send_cmd(chan, c, timeout=5)

    time.sleep(3)

    commands_restore = [
        "configure",
        f"interface {port}",
        "poe mode enable",
        "exit",
        "exit"
    ]
    for c in commands_restore:
        _send_cmd(chan, c, timeout=5)

    return {"status": "success", "message": f"PoE power-cycled on port {port}"}

def main():
    parser = argparse.ArgumentParser(description="Manage Araknis 920 Switch via FASTPATH CLI")
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("backup", help="Backup running-config to gitops repository")
    subparsers.add_parser("status", help="Get operational status (ports, MACs, STP, IGMP, SPAN)")

    poe_parser = subparsers.add_parser("poe-cycle", help="Power cycle PoE on a specific port")
    poe_parser.add_argument("port", help="Port number, e.g., 1/0/3")

    exec_parser = subparsers.add_parser("exec", help="Execute arbitrary FASTPATH show command")
    exec_parser.add_argument("command", help="Command string to execute (e.g. 'show vlan')")

    args = parser.parse_args()

    host, user, password = load_credentials()
    client, chan = connect_switch(host, user, password)

    try:
        if args.action == "backup":
            res = cmd_backup(chan)
            print(json.dumps(res, indent=2))
        elif args.action == "status":
            res = cmd_status(chan)
            print(json.dumps(res, indent=2))
        elif args.action == "poe-cycle":
            res = cmd_poe_cycle(chan, args.port)
            print(json.dumps(res, indent=2))
        elif args.action == "exec":
            out = _send_cmd(chan, args.command, timeout=20)
            print(out)
    finally:
        try:
            chan.send("logout\n")
            client.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
