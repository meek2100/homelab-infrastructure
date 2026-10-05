#!/usr/bin/env python3
"""
Correlate, align, and sync OvrC device list with authoritative DHCP reservations.

Matches OvrC devices by MAC Address (and IP) against dhcp-reservations-reorganized.json.
Identifies all 'Unspecified' or generic device names in OvrC and allows previewing
or applying accurate device names and room assignments directly via OvrC Cloud API.

Authentication:
  Credentials can be loaded automatically from SOPS-encrypted secret file:
    infrastructure/secrets/ovrc.enc.yaml (keys: username, password, token, api_key)
  Or from environment variables:
    OVRC_TOKEN, OVRC_API_KEY, OVRC_USERNAME, OVRC_PASSWORD
"""

import argparse
import base64
import csv
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_RESERVATIONS = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "dhcp-reservations-reorganized.json")
DEFAULT_OVRC_CSV = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "ovrc-device-list-latest.csv")
OUTPUT_ALIGNED_CSV = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "ovrc-device-list-aligned.csv")
SECRET_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "ovrc.enc.yaml")

OVRC_API_BASE = "https://app.ovrc.com/api/v1"


def normalize_mac(mac):
    if not mac:
        return ""
    return mac.strip().upper().replace("-", ":")


def get_room_from_name(name):
    lower = name.lower()
    if "rack" in lower or "520" in lower or "920" in lower or "pve" in lower or "rt-n66u" in lower:
        return "Rack Room"
    if "living" in lower:
        return "Living Room"
    if "primary bed" in lower or "master bed" in lower:
        return "Primary Bedroom"
    if "guest" in lower:
        return "Guest Room"
    if "kitchen" in lower:
        return "Kitchen"
    if "office" in lower or "desktop" in lower:
        return "Office"
    if "garage" in lower:
        return "Garage"
    if "landing" in lower:
        return "Landing"
    if "bathroom" in lower:
        return "Bathroom"
    return "Unassigned"


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
    """Load OvrC credentials from SOPS-encrypted file or environment variables."""
    token = os.environ.get("OVRC_TOKEN", os.environ.get("OVRC_API_KEY", ""))
    username = os.environ.get("OVRC_USERNAME", os.environ.get("OVRC_USER", ""))
    password = os.environ.get("OVRC_PASSWORD", "")

    if os.path.exists(SECRET_FILE):
        sops_bin = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
        if sops_bin and os.path.exists(sops_bin):
            key_file = get_age_key_path()
            env = os.environ.copy()
            if key_file:
                env["SOPS_AGE_KEY_FILE"] = key_file

            result = subprocess.run(
                [sops_bin, "-d", SECRET_FILE],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
            )
            if result.returncode == 0 and result.stdout:
                try:
                    data = yaml.safe_load(result.stdout) if yaml else json.loads(result.stdout)
                    if isinstance(data, dict):
                        token = token or data.get("token") or data.get("api_key") or ""
                        username = username or data.get("username") or data.get("user") or ""
                        password = password or data.get("password") or ""
                except Exception:
                    pass

    return token, username, password


def api_call(url, method="GET", data=None, token=""):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Homelab-Automation/1.0"
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            if content:
                try:
                    return resp.status, json.loads(content)
                except json.JSONDecodeError:
                    return resp.status, content
            return resp.status, None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        return e.code, err_body
    except Exception as e:
        return 0, str(e)


def align_ovrc(action="preview", token=None, username=None, password=None,
               ovrc_csv_path=DEFAULT_OVRC_CSV, reservations_path=DEFAULT_RESERVATIONS,
               output_csv_path=OUTPUT_ALIGNED_CSV):
    """
    Correlates and aligns OvrC device names with authoritative DHCP reservations.
    Actions:
      - 'preview': Non-destructive dry-run showing devices to rename (using local CSV blueprint).
      - 'csv'    : Generates the updated ovrc-device-list-aligned.csv blueprint.
      - 'apply'  : Connects to live OvrC Cloud API and pushes aligned names and rooms.
    """
    if not os.path.exists(reservations_path):
        return f"Error: reservations file not found at {reservations_path}"

    with open(reservations_path, "r") as f:
        res_data = json.load(f)

    reservations = res_data.get("dhcpReservations", [])
    res_by_mac = {}
    res_by_ip = {}
    for r in reservations:
        mac = normalize_mac(r.get("macAddress", ""))
        ip = r.get("staticIPAddress", "").strip()
        if mac:
            res_by_mac[mac] = r
        if ip:
            res_by_ip[ip] = r

    loaded_token, loaded_user, loaded_pass = load_credentials()
    token = token or loaded_token
    username = username or loaded_user
    password = password or loaded_pass

    # Handle live API apply
    if action == "apply":
        if not token:
            return (
                "Error: OvrC authentication token is required to apply changes to the cloud API.\n"
                f"Please ensure {SECRET_FILE} is created and encrypted via SOPS, or set OVRC_TOKEN env var."
            )

        status, resp = api_call(f"{OVRC_API_BASE}/devices", token=token)
        if status != 200:
            return f"Failed to query live OvrC devices (HTTP {status}): {resp}\nToken may be invalid or expired."

        ovrc_list = resp if isinstance(resp, list) else resp.get("devices", [])
        output_lines = [
            f"=== OvrC Live Cloud API Device Synchronization ===",
            f"Loaded {len(ovrc_list)} devices from OvrC Cloud Account.",
            f"Correlating against {len(reservations)} authoritative DHCP reservations...\n",
            f"{'IP Address':<16} {'MAC Address':<18} {'Current OvrC Name':<28} {'Authoritative Name':<35} {'Result'}",
            "-" * 115
        ]

        success_count = 0
        skipped_count = 0
        error_count = 0

        for dev in ovrc_list:
            mac = normalize_mac(dev.get("macAddress", dev.get("mac", "")))
            ip = dev.get("ipAddress", dev.get("ip", "")).strip()
            curr_name = dev.get("name", "").strip()
            dev_id = dev.get("id") or dev.get("deviceId")

            matched = res_by_mac.get(mac) or res_by_ip.get(ip)
            if not matched:
                output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {'(No DHCP Reservation)':<35} [SKIPPED]")
                skipped_count += 1
                continue

            auth_name = matched.get("name", "").strip()
            if curr_name == auth_name:
                output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [ALIGNED]")
                skipped_count += 1
                continue

            payload = {"name": auth_name}
            room = get_room_from_name(auth_name)
            if room and room != "Unassigned":
                payload["room"] = room

            up_status, up_resp = api_call(f"{OVRC_API_BASE}/devices/{dev_id}", method="PUT", data=payload, token=token)
            if up_status in (200, 204):
                output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [SUCCESS]")
                success_count += 1
            else:
                up_status, up_resp = api_call(f"{OVRC_API_BASE}/devices/{dev_id}", method="PATCH", data=payload, token=token)
                if up_status in (200, 204):
                    output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [SUCCESS]")
                    success_count += 1
                else:
                    output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [ERROR {up_status}]")
                    error_count += 1

        output_lines.append("-" * 115)
        output_lines.append(f"OvrC Cloud Sync Complete: {success_count} updated, {skipped_count} unchanged/skipped, {error_count} errors.")
        output_lines.append("=" * 115)
        return "\n".join(output_lines)

    # Handle local blueprint correlation (preview or csv)
    if not os.path.exists(ovrc_csv_path):
        return f"Error: OvrC CSV file not found at {ovrc_csv_path}"

    with open(ovrc_csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    aligned_rows = []
    renamed_count = 0
    unchanged_count = 0
    unmatched_count = 0

    output_lines = [
        f"=== OvrC Device Inventory Blueprint Alignment ({action.upper()}) ===",
        f"Loaded {len(rows)} OvrC devices from {os.path.basename(ovrc_csv_path)}",
        f"Correlating against {len(reservations)} authoritative DHCP reservations...\n",
        f"{'IP Address':<16} {'MAC Address':<18} {'Current OvrC Name':<28} {'Authoritative Name':<35} {'Action'}",
        "-" * 115
    ]

    for row in rows:
        mac = normalize_mac(row.get("MAC Address", ""))
        ip = row.get("IP Address", "").strip()
        curr_name = row.get("Device Name", "").strip()
        curr_room = row.get("Room", "").strip()

        matched = res_by_mac.get(mac) or res_by_ip.get(ip)

        new_row = dict(row)
        if matched:
            auth_name = matched.get("name", "").strip()
            is_generic = (
                curr_name.lower() in ("unspecified", "unknown", "") or
                curr_name.startswith("NPID") or
                curr_name.lower() in ("samsung", "tuya smart inc.", "apple, inc.", "pakedge-hostname")
            )

            if is_generic or (auth_name and curr_name != auth_name and curr_name.lower() != auth_name.lower()):
                new_row["Device Name"] = auth_name
                if curr_room == "Unassigned" or not curr_room:
                    new_row["Room"] = get_room_from_name(auth_name)
                output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [RENAME]")
                renamed_count += 1
            else:
                output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [MATCHED]")
                unchanged_count += 1
        else:
            output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {'(No DHCP Reservation)':<35} [UNTRACKED]")
            unmatched_count += 1

        aligned_rows.append(new_row)

    if action == "csv":
        with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(aligned_rows)
        output_lines.append(f"\nAligned blueprint CSV saved to: {output_csv_path}")

    output_lines.append("-" * 115)
    output_lines.append(f"Summary: {renamed_count} devices to rename, {unchanged_count} already accurate, {unmatched_count} untracked.")
    if action == "preview":
        output_lines.append("To push changes to the cloud, ensure secrets/ovrc.enc.yaml is present and run with action='apply'.")
    output_lines.append("=" * 115)

    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(description="Correlate, align, and sync OvrC devices with DHCP reservations")
    parser.add_argument("action", nargs="?", default="preview", choices=["preview", "csv", "apply"],
                        help="Action to perform: 'preview' (dry-run), 'csv' (write blueprint), 'apply' (push to OvrC API)")
    parser.add_argument("--token", default=None, help="OvrC Bearer token or API key")
    parser.add_argument("--user", default=None, help="OvrC username")
    parser.add_argument("--password", default=None, help="OvrC password")
    parser.add_argument("--ovrc-csv", default=DEFAULT_OVRC_CSV, help="Path to input OvrC CSV")
    parser.add_argument("--reservations", default=DEFAULT_RESERVATIONS, help="Path to DHCP reservations JSON")
    parser.add_argument("--output", default=OUTPUT_ALIGNED_CSV, help="Path to output aligned CSV")
    args = parser.parse_args()

    result = align_ovrc(
        action=args.action,
        token=args.token,
        username=args.user,
        password=args.password,
        ovrc_csv_path=args.ovrc_csv,
        reservations_path=args.reservations,
        output_csv_path=args.output
    )
    print(result)


if __name__ == "__main__":
    main()
