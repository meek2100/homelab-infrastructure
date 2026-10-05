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
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
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

OVRC_API_BASE = "https://api.ovrc.com/v1"
DEFAULT_CLIENT_API_KEY = "lefqsmukfgrfr2cvxya6cxnlc22i79h97a4bcp76"


def normalize_mac(mac):
    if not mac:
        return ""
    # Strip any non-hex characters and format as standard uppercase colon-separated
    clean = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    if len(clean) == 12:
        return ":".join(clean[i:i+2] for i in range(0, 12, 2))
    return mac.strip().upper().replace("-", ":")


def get_room_from_name(name):
    lower = name.lower()
    # Tuya lights stay Unassigned for manual room assignment
    if "tuya" in lower:
        return "Unassigned"
    # Garage
    if any(k in lower for k in ["garage", "myq", "rachio", "sprinkler", "moen flo", "flo smart water"]):
        return "Garage"
    # Rack Room
    if any(k in lower for k in [
        "rack", "520", "920", "pve", "rt-n66u", "ca-10", "ca10", "director",
        "proxmox", "dell precision", "awow", "elitedesk", "wattbox", "moip",
        "pbs", "nexus", "luna", "nas", "media server", "discovery server", "vxlan server"
    ]):
        return "Rack Room"
    # Office
    if any(k in lower for k in ["office", "desktop", "mac mini", "laserjet", "brother", "netgear", "pakedge"]):
        return "Office"
    # Living Room
    if "living" in lower:
        return "Living Room"
    # Primary Bedroom
    if "primary bed" in lower or "master bed" in lower:
        return "Primary Bedroom"
    # Downstairs Guest Room
    if "guest" in lower:
        return "Downstairs Guest Room"
    # Kitchen
    if "kitchen" in lower:
        return "Kitchen"
    # Emme's Play Area / Landing
    if any(k in lower for k in ["play area", "landing", "emmy landing"]):
        return "Emme's Play Area"
    # Emme's Bedroom
    if "emme" in lower or "hatch" in lower:
        return "Emme's Bedroom"
    # Bathrooms
    if "bathroom" in lower:
        return "Upstairs Bathroom"
    if "sewing" in lower:
        return "Upstairs Sewing Room"
    if "laundry" in lower:
        return "Laundry Room"
    # Foyer
    if any(k in lower for k in ["foyer", "door station", "ds2"]):
        return "Foyer"
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
    token = os.environ.get("OVRC_TOKEN", "")
    api_key = os.environ.get("OVRC_API_KEY", DEFAULT_CLIENT_API_KEY)
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
                        token = token or data.get("token") or ""
                        api_key = data.get("api_key") or api_key
                        username = username or data.get("username") or data.get("user") or ""
                        password = password or data.get("password") or ""
                except Exception:
                    pass

    return token, api_key, username, password


class OvrCClient:
    def __init__(self, username=None, password=None, token=None, api_key=None):
        loaded_token, loaded_key, loaded_user, loaded_pass = load_credentials()
        self.username = username or loaded_user
        self.password = password or loaded_pass
        self.token = token or loaded_token
        self.api_key = api_key or loaded_key or DEFAULT_CLIENT_API_KEY

    def _headers(self):
        headers = {
            "X-API-KEY": self.api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, url, method="GET", data=None, max_retries=3):
        body = json.dumps(data).encode("utf-8") if data is not None else None
        for attempt in range(max_retries):
            req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    raw = resp.read().decode("utf-8")
                    if raw:
                        try:
                            return True, json.loads(raw)
                        except json.JSONDecodeError:
                            return True, raw
                    return True, "Success"
            except urllib.error.HTTPError as e:
                err = e.read().decode("utf-8", errors="ignore") if e.fp else ""
                if e.code == 429 and attempt < max_retries - 1:
                    wait_time = 32
                    try:
                        err_obj = json.loads(err)
                        wait_time = max(int(err_obj.get("retry_after", 30)) + 2, wait_time)
                    except Exception:
                        pass
                    sys.stderr.write(f"\n[Cloudflare 429 Rate Limit] Waiting {wait_time}s before retrying (attempt {attempt+1}/{max_retries})...\n")
                    sys.stderr.flush()
                    time.sleep(wait_time)
                    continue
                return False, f"HTTP {e.code}: {err}"
            except Exception as e:
                return False, str(e)
        return False, "Max retries exceeded"

    def authenticate(self):
        if self.token:
            return True, "Existing token provided"
        if not self.username or not self.password:
            return False, "Missing OvrC username and password"

        url = f"{OVRC_API_BASE}/users/login"
        ok, res = self._request(url, method="POST", data={"username": self.username, "password": self.password})
        if ok and isinstance(res, dict):
            self.token = res.get("accessToken")
            if self.token:
                return True, "Successfully authenticated"
            return False, f"No accessToken returned: {res}"
        return False, str(res)

    def get_locations(self):
        url = f"{OVRC_API_BASE}/locations/simple?limit=50"
        ok, res = self._request(url, method="GET")
        if ok and isinstance(res, dict):
            return True, res.get("items", [])
        return ok, res

    def find_target_location(self, location_name="Theurer Home"):
        ok, locs = self.get_locations()
        if not ok:
            return None, f"Failed to retrieve locations: {locs}"
        for loc in locs:
            if location_name.lower() in loc.get("name", "").lower():
                return loc, ""
        if locs:
            return locs[0], ""
        return None, "No locations found in OvrC account"

    def get_rooms(self, location_id):
        url = f"{OVRC_API_BASE}/locations/rooms?locationId={location_id}"
        ok, res = self._request(url, method="GET")
        if ok and isinstance(res, dict):
            rooms = res.get("items", res.get("rooms", []))
            return True, rooms
        return ok, res

    def trigger_scan(self, location_id):
        url = f"{OVRC_API_BASE}/locations/scan"
        return self._request(url, method="POST", data={"locationId": location_id})

    def get_devices(self, location_id):
        url = f"{OVRC_API_BASE}/devices?filter=locationId:{location_id}&limit=200"
        ok, res = self._request(url, method="GET")
        if ok and isinstance(res, dict):
            devices = res.get("items", res.get("devices", []))
            return True, devices
        return ok, res

    def rename_device(self, device_id, new_name):
        url = f"{OVRC_API_BASE}/devices"
        return self._request(url, method="PUT", data={"deviceId": device_id, "name": new_name})

    def assign_room(self, device_id, location_id, room_id):
        url = f"{OVRC_API_BASE}/devices/room"
        return self._request(url, method="PUT", data={
            "ids": [device_id],
            "locationId": location_id,
            "roomId": room_id
        })


def align_ovrc(action="preview", token=None, username=None, password=None,
               location_name="Theurer Home",
               ovrc_csv_path=DEFAULT_OVRC_CSV, reservations_path=DEFAULT_RESERVATIONS,
               output_csv_path=OUTPUT_ALIGNED_CSV):
    """
    Correlates and aligns OvrC device names with authoritative DHCP reservations.
    Actions:
      - 'status' : Display OvrC location details, device count, and Unspecified count.
      - 'scan'   : Trigger a fresh network discovery scan via OvrC Cloud API.
      - 'preview': Non-destructive dry-run showing devices to rename and room assignments.
      - 'csv'    : Generates the updated ovrc-device-list-aligned.csv blueprint.
      - 'apply'  : Connects to live OvrC Cloud API and applies aligned names and rooms.
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

    client = OvrCClient(username=username, password=password, token=token)
    auth_ok, auth_msg = client.authenticate()

    # If action is status or scan or live operations and auth failed, report error
    if action in ("status", "scan", "apply") and not auth_ok:
        return (
            f"Error: Unable to authenticate with OvrC Cloud ({auth_msg}).\n"
            f"Please verify {SECRET_FILE} exists and is decryptable, or pass valid credentials."
        )

    # 1. Action: scan
    if action == "scan":
        loc, loc_err = client.find_target_location(location_name)
        if not loc:
            return f"Error locating site: {loc_err}"
        loc_id = loc.get("locationId")
        ok, res = client.trigger_scan(loc_id)
        if ok:
            return f"Successfully initiated network scan for location '{loc.get('name')}' (ID: {loc_id})."
        return f"Failed to initiate network scan: {res}"

    # 2. Action: status
    if action == "status":
        loc, loc_err = client.find_target_location(location_name)
        if not loc:
            return f"Error locating site: {loc_err}"
        loc_id = loc.get("locationId")
        ok_dev, devs = client.get_devices(loc_id)
        if not ok_dev:
            return f"Failed to retrieve devices: {devs}"

        unspecified = [d for d in devs if d.get("name") in ("Unspecified", "Unknown", "") or not d.get("name")]
        out = [
            f"=== OvrC Location Status ===",
            f"Location Name: {loc.get('name')}",
            f"Location ID  : {loc_id}",
            f"Address      : {loc.get('address')}",
            f"Total Devices: {len(devs)}",
            f"Unspecified  : {len(unspecified)}",
            f"Degraded Devs: {loc.get('degradedDeviceCount', 0)}"
        ]
        return "\n".join(out)

    # For preview / apply / csv: Fetch live devices if authenticated, else fallback to CSV
    live_mode = auth_ok
    devices_to_process = []
    location_id = None
    rooms_map = {}  # name.lower() -> roomId

    if live_mode:
        loc, loc_err = client.find_target_location(location_name)
        if loc:
            location_id = loc.get("locationId")
            ok_rooms, rooms_list = client.get_rooms(location_id)
            if ok_rooms:
                for rm in rooms_list:
                    rooms_map[rm.get("name", "").strip().lower()] = rm.get("roomId") or rm.get("id")

            ok_dev, live_devs = client.get_devices(location_id)
            if ok_dev:
                devices_to_process = live_devs

    # Fallback to local CSV if live query was not possible
    if not devices_to_process:
        if not os.path.exists(ovrc_csv_path):
            return f"Error: Neither live OvrC query nor local CSV ({ovrc_csv_path}) are available."
        with open(ovrc_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                devices_to_process.append({
                    "deviceId": None,
                    "macAddress": r.get("MAC Address", ""),
                    "lanAddress": r.get("IP Address", ""),
                    "name": r.get("Device Name", ""),
                    "roomName": r.get("Room", ""),
                    "_is_csv": True
                })

    output_lines = [
        f"=== OvrC Device Inventory Alignment ({action.upper()}) ===",
        f"Source: {'Live OvrC Cloud API' if live_mode else 'Local Blueprint CSV'}",
        f"Total Devices Evaluated: {len(devices_to_process)}",
        f"Authoritative Reservations: {len(reservations)}\n",
        f"{'IP Address':<16} {'MAC Address':<18} {'Current OvrC Name':<28} {'Target Authoritative Name':<35} {'Result / Action'}",
        "-" * 125
    ]

    aligned_csv_rows = []
    renamed_count = 0
    matched_count = 0
    untracked_count = 0
    error_count = 0

    for dev in devices_to_process:
        mac = normalize_mac(dev.get("macAddress") or dev.get("activeMacAddress", ""))
        ip = (dev.get("lanAddress") or dev.get("ipAddress") or "").split(":")[0].strip()
        curr_name = (dev.get("name") or "").strip()
        dev_id = dev.get("deviceId")
        curr_room_id = dev.get("roomId")

        matched = res_by_mac.get(mac) or res_by_ip.get(ip)

        if not matched:
            output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {'(No DHCP Reservation)':<35} [UNTRACKED]")
            untracked_count += 1
            aligned_csv_rows.append({
                "Device Name": curr_name,
                "Room": "Unassigned",
                "IP Address": ip,
                "MAC Address": mac,
                "Status": "Untracked"
            })
            continue

        auth_name = matched.get("name", "").strip()
        target_room_name = get_room_from_name(auth_name)
        target_room_id = rooms_map.get(target_room_name.lower())

        is_generic = (
            curr_name.lower() in ("unspecified", "unknown", "") or
            curr_name.startswith("NPID") or
            curr_name.lower() in ("samsung", "tuya smart inc.", "apple, inc.", "pakedge-hostname")
        )
        needs_rename = is_generic or (curr_name != auth_name)

        if action == "apply" and live_mode and dev_id:
            status_text = []
            mutated = False
            if needs_rename:
                ok_rn, err_rn = client.rename_device(dev_id, auth_name)
                if ok_rn:
                    status_text.append("RENAMED")
                    renamed_count += 1
                else:
                    status_text.append(f"RENAME_FAILED({err_rn})")
                    error_count += 1
                mutated = True
                time.sleep(0.75)
            else:
                status_text.append("NAME_ALIGNED")
                matched_count += 1

            if target_room_id and location_id and (curr_room_id != target_room_id):
                ok_rm, err_rm = client.assign_room(dev_id, location_id, target_room_id)
                if ok_rm:
                    status_text.append(f"ROOM->{target_room_name}")
                else:
                    status_text.append(f"ROOM_FAILED({err_rm})")
                mutated = True
                time.sleep(0.75)

            output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [{', '.join(status_text)}]")

        else:
            # Preview / CSV mode
            if needs_rename:
                output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [RENAME -> {target_room_name}]")
                renamed_count += 1
            else:
                output_lines.append(f"{ip:<16} {mac:<18} {curr_name:<28} {auth_name:<35} [MATCHED]")
                matched_count += 1

        aligned_csv_rows.append({
            "Device Name": auth_name,
            "Room": target_room_name,
            "IP Address": ip,
            "MAC Address": mac,
            "Status": "Aligned"
        })

    if action == "csv":
        fieldnames = ["Device Name", "Room", "IP Address", "MAC Address", "Status"]
        with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(aligned_csv_rows)
        output_lines.append(f"\nAligned blueprint CSV saved to: {output_csv_path}")

    output_lines.append("-" * 125)
    output_lines.append(
        f"Summary: {renamed_count} to rename/renamed, {matched_count} already matched, "
        f"{untracked_count} untracked, {error_count} errors."
    )
    if action == "preview":
        output_lines.append("To push these updates live to OvrC Cloud, run with action='apply'.")
    output_lines.append("=" * 125)

    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(description="Correlate, align, and sync OvrC devices with DHCP reservations")
    parser.add_argument("action", nargs="?", default="preview", choices=["status", "scan", "preview", "csv", "apply"],
                        help="Action to perform: 'status', 'scan', 'preview' (dry-run), 'csv' (export blueprint), 'apply' (push to OvrC API)")
    parser.add_argument("--token", default=None, help="OvrC Bearer token or API key")
    parser.add_argument("--user", default=None, help="OvrC username")
    parser.add_argument("--password", default=None, help="OvrC password")
    parser.add_argument("--location", default="Theurer Home", help="Target location name (default: 'Theurer Home')")
    parser.add_argument("--ovrc-csv", default=DEFAULT_OVRC_CSV, help="Path to input OvrC CSV")
    parser.add_argument("--reservations", default=DEFAULT_RESERVATIONS, help="Path to DHCP reservations JSON")
    parser.add_argument("--output", default=OUTPUT_ALIGNED_CSV, help="Path to output aligned CSV")
    args = parser.parse_args()

    result = align_ovrc(
        action=args.action,
        token=args.token,
        username=args.user,
        password=args.password,
        location_name=args.location,
        ovrc_csv_path=args.ovrc_csv,
        reservations_path=args.reservations,
        output_csv_path=args.output
    )
    print(result)


if __name__ == "__main__":
    main()
