#!/usr/bin/env python3
"""
Araknis 520 Router Management & Automation Tool (REST API)
Interacts with the Araknis AN-520-RT (192.168.1.1) via its REST API.

Auth mechanism: HTTP Basic Auth via GET /api/cgi-bin/v1/authorize
  - Method:  GET (not POST)
  - Header:  Authorization: Basic base64(username:password)
  - Returns: 302 on success, 401 on failure

Supports:
  - Configuration backup (export-config to gitops)
  - Status review (system info, WAN, ports, subnets, DHCP, firewall)
  - Configuration restore (upload-config from gitops blueprint)
  - DHCP table audit
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None

try:
    import requests
except ImportError:
    requests = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_BACKUP_FILE = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "araknis-520-backup.cfg")
SECRET_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "araknis-switch.enc.yaml")

DEFAULT_ROUTER_IP = "192.168.1.1"
DEFAULT_USER = "meek2100"
BASE_PATH = "/api/cgi-bin/v1"


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
    """Load router credentials from SOPS-encrypted file or environment."""
    user = os.environ.get("ARAKNIS_USER", DEFAULT_USER)
    password = os.environ.get("ARAKNIS_PASSWORD")
    host = os.environ.get("ARAKNIS_HOST", DEFAULT_ROUTER_IP)

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

        result = subprocess.run(
            [sops_bin, "-d", SECRET_FILE],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(f"SOPS decryption failed: {result.stderr.strip()}")

        if yaml is None:
            raise RuntimeError("PyYAML not installed. Run: pip install pyyaml")

        data = yaml.safe_load(result.stdout)
        password = data.get("password")
        user = data.get("username", user)
        # Secret file has switch_ip; router IP auto-detected across VLANs
        host = os.environ.get("ARAKNIS_HOST") or probe_router_host()

    if not password:
        raise RuntimeError(
            "No router password found. Set ARAKNIS_PASSWORD env var or ensure "
            f"{SECRET_FILE} exists and is decryptable."
        )

    return host, user, password


def probe_router_host(candidates=None):
    """Probe candidate router interface IPs to find the reachable gateway."""
    import socket
    candidates = candidates or ["192.168.10.1", "192.168.1.1", "192.168.40.1"]
    for ip in candidates:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex((ip, 80)) == 0:
                    return ip
        except Exception:
            pass
    return DEFAULT_ROUTER_IP


def create_session(host, user, password):
    """Create an authenticated requests.Session using HTTP Basic Auth (GET /authorize)."""
    if requests is None:
        raise RuntimeError("requests library not installed. Run: pip install requests")

    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Accept": "*/*",
    })

    url = f"http://{host}{BASE_PATH}/authorize"
    resp = s.get(url, allow_redirects=False, timeout=10)
    if resp.status_code not in (200, 302):
        raise RuntimeError(
            f"Authentication failed: GET {url} returned {resp.status_code}. "
            f"Check credentials in {SECRET_FILE}."
        )
    return s


def api_get(s, host, path, timeout=10):
    url = f"http://{host}{BASE_PATH}{path}"
    resp = s.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_put(s, host, path, data, timeout=15):
    url = f"http://{host}{BASE_PATH}{path}"
    resp = s.put(url, json=data, timeout=timeout)
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception:
        return {"status_code": resp.status_code, "text": resp.text}


def cmd_status(s, host):
    """Gather comprehensive router status across system, WAN, LAN, and ports."""
    endpoints = {
        "system_info":       "/status/system/system-information",
        "system_stats":      "/status/system/stats",
        "wan_status":        "/status/wan",
        "ports_status":      "/status/ports",
        "wan_config":        "/config/wan",
        "lan_subnets":       "/config/lan/subnets",
        "dhcp_reservations": "/config/lan/dhcp-reservation",
        "firewall":          "/config/firewall",
    }

    results = {}
    errors = []
    for key, path in endpoints.items():
        try:
            results[key] = api_get(s, host, path)
        except Exception as e:
            errors.append(f"{key}: {e}")
            results[key] = {"error": str(e)}

    lines = [f"=== Araknis 520 Router Status ({host}) ===\n"]

    si = results.get("system_info", {}).get("systemInfo", {})
    if si:
        lines += [
            "[System]",
            f"  Model:       {si.get('modelNumber', 'N/A')}",
            f"  Firmware:    {si.get('firmwareVersion', 'N/A')} ({si.get('buildDate', 'N/A')})",
            f"  ServiceTag:  {si.get('serviceTag', 'N/A')}",
            f"  LAN MAC:     {si.get('lanMacAddress', 'N/A')}",
            f"  WAN1 MAC:    {si.get('wan1MacAddress', 'N/A')}",
            f"  WAN2 MAC:    {si.get('wan2MacAddress', 'N/A')}",
            "",
        ]

    for section, key in [("System Stats", "system_stats"), ("WAN Status", "wan_status"),
                          ("LAN Subnets", "lan_subnets"), ("DHCP Reservations", "dhcp_reservations"),
                          ("Firewall", "firewall")]:
        data = results.get(key, {})
        if data and "error" not in data:
            lines += [f"[{section}]", json.dumps(data, indent=2), ""]

    if errors:
        lines += ["[Errors]"] + [f"  {e}" for e in errors]

    return {"status": "success", "summary": "\n".join(lines), "raw": results}


def cmd_backup(s, host):
    """Export the router configuration and save to the repository.
    The router returns HTTP 201 with a base64-encoded OpenSSL-encrypted config blob.
    """
    url = f"http://{host}{BASE_PATH}/command/export-config"
    resp = s.get(url, timeout=30)
    if resp.status_code not in (200, 201):
        # Try POST variant
        resp = s.post(url, json={}, timeout=30)

    if resp.status_code not in (200, 201):
        return {"status": "error", "message": f"export-config returned {resp.status_code}", "body": resp.text[:500]}

    config_data = resp.content
    if not config_data:
        return {"status": "error", "message": "export-config returned empty response"}

    os.makedirs(os.path.dirname(CONFIG_BACKUP_FILE), exist_ok=True)
    with open(CONFIG_BACKUP_FILE, "wb") as f:
        f.write(config_data)

    return {
        "status": "success",
        "file": CONFIG_BACKUP_FILE,
        "bytes": len(config_data),
        "http_status": resp.status_code,
        "content_type": resp.headers.get("Content-Type", "unknown"),
        "note": "Config is base64-encoded OpenSSL-encrypted blob (Salted__ prefix). Use restore-config endpoint to restore.",
    }


def cmd_dhcp_table(s, host):
    """List all DHCP reservations and active client leases."""
    results = {}
    for key, path in [("reservations", "/config/lan/dhcp-reservation"),
                       ("clients_services", "/status/clients-services")]:
        try:
            results[key] = api_get(s, host, path)
        except Exception as e:
            results[key] = {"error": str(e)}
    return {"status": "success", "dhcp": results}


def cmd_get_acls(s, host):
    """Retrieve current ACL configuration and services."""
    data = api_get(s, host, "/config/acls")
    return {"status": "success", "acls": data}


def cmd_apply_acls(s, host, payload_file):
    """Apply ACL configuration from a JSON file."""
    with open(payload_file, "r") as f:
        payload = json.load(f)
    resp = api_put(s, host, "/config/acls", payload)
    return {"status": "success", "response": resp}


def cmd_restore(s, host, backup_file=None):
    """Restore router configuration from a backup file."""
    target = backup_file or CONFIG_BACKUP_FILE
    if not os.path.exists(target):
        return {"status": "error", "message": f"Backup file not found: {target}"}

    with open(target, "rb") as f:
        config_data = f.read()

    for endpoint in ["/command/restore-config", "/command/upload-config"]:
        url = f"http://{host}{BASE_PATH}{endpoint}"
        resp = s.post(url, data=config_data,
                      headers={"Content-Type": "application/octet-stream"}, timeout=60)
        if resp.status_code in (200, 302):
            return {"status": "success", "http_status": resp.status_code,
                    "response": resp.text[:300], "file": target, "bytes": len(config_data)}

    return {"status": "error", "http_status": resp.status_code, "response": resp.text[:300]}


def main():
    parser = argparse.ArgumentParser(description="Araknis 520 Router REST API Management Tool")
    parser.add_argument("action", choices=["backup", "status", "dhcp-table", "get-acls", "apply-acls", "restore"])
    parser.add_argument("--backup-file", help="Path to backup file (for restore)")
    parser.add_argument("--payload-file", help="Path to JSON file containing {aclConfig, serviceManagement} (for apply-acls)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    try:
        host, user, password = load_credentials()
        s = create_session(host, user, password)
        print(f"[*] Authenticated to {host} as {user}", file=sys.stderr)

        if args.action == "backup":
            result = cmd_backup(s, host)
        elif args.action == "status":
            result = cmd_status(s, host)
        elif args.action == "dhcp-table":
            result = cmd_dhcp_table(s, host)
        elif args.action == "get-acls":
            result = cmd_get_acls(s, host)
        elif args.action == "apply-acls":
            if not args.payload_file:
                raise ValueError("--payload-file required for apply-acls")
            result = cmd_apply_acls(s, host, args.payload_file)
        elif args.action == "restore":
            result = cmd_restore(s, host, args.backup_file)

        if args.json or "summary" not in result:
            print(json.dumps(result, indent=2))
        else:
            print(result["summary"])

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
