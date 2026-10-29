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

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
CONFIG_BACKUP_FILE = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "araknis-520-backup.cfg")
SECRET_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "araknis-switch.enc.yaml")

DEFAULT_ROUTER_IP = "192.168.1.1"
DEFAULT_USER = "meek2100"
BASE_PATH = "/api/cgi-bin/v1"

_tunnel_proc = None

def get_ssh_key():
    for candidate in [
        os.path.expanduser("~/.ssh/proxmox_ed25519"),
        "/home/agentsvc/.ssh/proxmox_ed25519",
        "/home/dtheurer/.ssh/proxmox_ed25519",
        os.path.expanduser("~/.ssh/id_ed25519"),
        "/home/dtheurer/.ssh/id_ed25519"
    ]:
        if os.path.exists(candidate):
            return candidate
    return None

def cleanup_tunnel():
    global _tunnel_proc
    if _tunnel_proc:
        try:
            _tunnel_proc.terminate()
            _tunnel_proc.wait(timeout=2)
        except Exception:
            pass
        _tunnel_proc = None

def get_reachable_host(target_host=None):
    global _tunnel_proc
    target = target_host or DEFAULT_ROUTER_IP
    # Check if target is directly reachable on port 443
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((target, 443)) == 0:
                return target
    except Exception:
        pass

    # If direct connection timed out/failed (e.g. from WSL2 NAT due to router management ACL),
    # establish an ephemeral tunnel through Proxmox pve on VLAN 1
    pve_ip = "192.168.1.250"
    local_port = 18443
    key = get_ssh_key()
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=accept-new",
        "-N", "-L", f"{local_port}:192.168.1.1:443"
    ]
    if key:
        cmd.extend(["-i", key])
    cmd.append(f"root@{pve_ip}")
    try:
        import atexit, time
        _tunnel_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)
        atexit.register(cleanup_tunnel)
        return f"127.0.0.1:{local_port}"
    except Exception:
        return target

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
    host = os.environ.get("ARAKNIS_HOST")

    if password:
        return host or get_reachable_host(DEFAULT_ROUTER_IP), user, password

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
        # Secret file has switch_ip; router IP auto-detected across VLANs or tunnel
        host = os.environ.get("ARAKNIS_HOST") or get_reachable_host(DEFAULT_ROUTER_IP)

    if not password:
        raise RuntimeError(
            "No router password found. Set ARAKNIS_PASSWORD env var or ensure "
            f"{SECRET_FILE} exists and is decryptable."
        )

    return host, user, password


def create_session(host, user, password):
    """Create an authenticated requests.Session using HTTP Basic Auth (GET /authorize)."""
    if requests is None:
        raise RuntimeError("requests library not installed. Run: pip install requests")

    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    s = requests.Session()
    s.verify = False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    s.headers.update({
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "Accept": "*/*",
    })

    url = f"https://{host}{BASE_PATH}/authorize"
    resp = s.get(url, allow_redirects=False, timeout=10)
    if resp.status_code not in (200, 302, 307):
        raise RuntimeError(
            f"Authentication failed: GET {url} returned {resp.status_code}. "
            f"Check credentials in {SECRET_FILE}."
        )
    return s


def api_get(s, host, path, timeout=10):
    url = f"https://{host}{BASE_PATH}{path}"
    resp = s.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_put(s, host, path, data, timeout=15):
    url = f"https://{host}{BASE_PATH}{path}"
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
        "static_routes":     "/config/static-route",
    }

    results = {}
    errors = []
    for key, path in endpoints.items():
        try:
            results[key] = api_get(s, host, path)
        except Exception as e:
            errors.append(f"{key}: {e}")
            results[key] = {"error": str(e)}
    try:
        v_resp = s.get(f"https://{host}/api/cgi-bin/v2/config/vlans", timeout=10)
        v_resp.raise_for_status()
        results["vlans_v2"] = v_resp.json()
    except Exception as e:
        errors.append(f"vlans_v2: {e}")
        results["vlans_v2"] = {"error": str(e)}

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
                          ("Firewall", "firewall"), ("Static Routes", "static_routes"),
                          ("VLANs v2", "vlans_v2"), ("LAN Subnets", "lan_subnets"),
                          ("DHCP Reservations", "dhcp_reservations")]:
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
    url = f"https://{host}{BASE_PATH}/command/export-config"
    resp = s.post(url, json={}, timeout=30)
    if resp.status_code not in (200, 201):
        resp = s.get(url, timeout=30)

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


def cmd_apply_dhcp(s, host, payload_file):
    """Apply DHCP reservations from a JSON file."""
    with open(payload_file, "r") as f:
        payload = json.load(f)
    resp = api_put(s, host, "/config/lan/dhcp-reservation", payload)
    return {"status": "success", "response": resp}


def cmd_get_subnets(s, host):
    """Fetch live LAN subnets and assigned DHCP options."""
    return api_get(s, host, "/config/lan/subnets")


def cmd_get_dhcp_options(s, host):
    """Fetch global DHCP options catalog."""
    return api_get(s, host, "/config/lan/dhcp-options")


def api_put_with_retry(s, host, path, data, timeout=20, v2=False):
    import time
    url = f"https://{host}/api/cgi-bin/v2{path}" if v2 else f"https://{host}{BASE_PATH}{path}"
    for attempt in range(8):
        resp = s.put(url, json=data, timeout=timeout)
        resp.raise_for_status()
        try:
            j = resp.json()
            if j.get("resultMessage", {}).get("code") == 100 and attempt < 7:
                time.sleep(3.5)
                continue
            return j
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}
    return j


def cmd_apply_subnets(s, host, payload_file):
    """Apply LAN subnet configurations, DHCP reservations, VLANs, or static routes from a JSON file based on payload keys."""
    with open(payload_file, "r") as f:
        payload = json.load(f)
    if "dhcpReservations" in payload:
        resp = api_put_with_retry(s, host, "/config/lan/dhcp-reservation", payload, timeout=30)
        return {"status": "success", "endpoint": "/config/lan/dhcp-reservation", "response": resp}
    elif "vlanConfigV2" in payload:
        resp = api_put_with_retry(s, host, "/config/vlans", payload, timeout=30, v2=True)
        return {"status": "success", "endpoint": "/v2/config/vlans", "response": resp}
    elif "staticRoute" in payload:
        resp = api_put_with_retry(s, host, "/config/static-route", payload, timeout=30)
        return {"status": "success", "endpoint": "/config/static-route", "response": resp}
    else:
        resp = api_put_with_retry(s, host, "/config/lan/subnets", payload, timeout=30)
        return {"status": "success", "endpoint": "/config/lan/subnets", "response": resp}


def cmd_set_upnp(s, host, enable=True):
    """Enable or disable UPnP discovery helper on router firewall."""
    url = f"https://{host}/api/cgi-bin/v2/config/firewall"
    resp = s.put(url, json={"enableUPnP": enable}, timeout=15)
    resp.raise_for_status()
    try:
        return {"status": "success", "response": resp.json()}
    except Exception:
        return {"status": "success", "status_code": resp.status_code, "text": resp.text}


def cmd_restore(s, host, backup_file=None):
    """Restore router configuration from a backup file."""
    target = backup_file or CONFIG_BACKUP_FILE
    if not os.path.exists(target):
        return {"status": "error", "message": f"Backup file not found: {target}"}

    with open(target, "rb") as f:
        config_data = f.read()

    for endpoint in ["/command/restore-config", "/command/upload-config"]:
        url = f"https://{host}{BASE_PATH}{endpoint}"
        resp = s.post(url, data=config_data,
                      headers={"Content-Type": "application/octet-stream"}, timeout=60)
        if resp.status_code in (200, 302):
            return {"status": "success", "http_status": resp.status_code,
                    "response": resp.text[:300], "file": target, "bytes": len(config_data)}

    return {"status": "error", "http_status": resp.status_code, "response": resp.text[:300]}


def cmd_get_vlans(s, host):
    """Retrieve 802.1Q port and inter-zone routing configuration (v2 API)."""
    url = f"https://{host}/api/cgi-bin/v2/config/vlans"
    resp = s.get(url, timeout=10)
    resp.raise_for_status()
    return {"status": "success", "vlans": resp.json()}


def cmd_apply_vlans(s, host, payload_file):
    """Apply 802.1Q port and inter-zone routing configuration from JSON file (v2 API)."""
    with open(payload_file, "r") as f:
        payload = json.load(f)
    url = f"https://{host}/api/cgi-bin/v2/config/vlans"
    resp = s.put(url, json=payload, timeout=20)
    resp.raise_for_status()
    try:
        return {"status": "success", "response": resp.json()}
    except Exception:
        return {"status": "success", "status_code": resp.status_code, "text": resp.text}


def cmd_get_static_routes(s, host):
    """Retrieve static routes configuration (v1 API)."""
    data = api_get(s, host, "/config/static-route")
    return {"status": "success", "static_routes": data}


def cmd_apply_static_routes(s, host, payload_file):
    """Apply static routes configuration from JSON file (v1 API)."""
    with open(payload_file, "r") as f:
        payload = json.load(f)
    resp = api_put(s, host, "/config/static-route", payload, timeout=20)
    return {"status": "success", "response": resp}


def main():
    parser = argparse.ArgumentParser(description="Araknis 520 Router REST API Management Tool")
    parser.add_argument("action", choices=["backup", "status", "dhcp-table", "get-acls", "apply-acls", "apply-dhcp", "get-subnets", "apply-subnets", "get-dhcp-options", "get-vlans", "apply-vlans", "get-static-routes", "apply-static-routes", "enable-upnp", "restore"])
    parser.add_argument("--backup-file", help="Path to backup file (for restore)")
    parser.add_argument("--payload-file", help="Path to JSON file containing payload (for apply-acls, apply-dhcp, apply-subnets, apply-vlans, apply-static-routes)")
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
        elif args.action == "apply-dhcp":
            if not args.payload_file:
                raise ValueError("--payload-file required for apply-dhcp")
            result = cmd_apply_dhcp(s, host, args.payload_file)
        elif args.action == "get-subnets":
            result = cmd_get_subnets(s, host)
        elif args.action == "apply-subnets":
            if not args.payload_file:
                raise ValueError("--payload-file required for apply-subnets")
            result = cmd_apply_subnets(s, host, args.payload_file)
        elif args.action == "get-dhcp-options":
            result = cmd_get_dhcp_options(s, host)
        elif args.action == "get-vlans":
            result = cmd_get_vlans(s, host)
        elif args.action == "apply-vlans":
            if not args.payload_file:
                raise ValueError("--payload-file required for apply-vlans")
            result = cmd_apply_vlans(s, host, args.payload_file)
        elif args.action == "get-static-routes":
            result = cmd_get_static_routes(s, host)
        elif args.action == "apply-static-routes":
            if not args.payload_file:
                raise ValueError("--payload-file required for apply-static-routes")
            result = cmd_apply_static_routes(s, host, args.payload_file)
        elif args.action == "enable-upnp":
            result = cmd_set_upnp(s, host, enable=True)
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
