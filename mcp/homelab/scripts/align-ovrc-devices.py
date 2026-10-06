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

PROJECT_LOCATIONS = ["Theurer Home", "CA1 Test", "Core5 Test", "Ryff Standalone Test"]
EXCLUDED_LOCATIONS = ["Nicola Home"]

LOCATION_VLAN_MAP = {
    "theurer home": "VLAN 1, 10, 20, 30, 40",
    "ca1 test": "VLAN 150 (CA-1 Test)",
    "ryff standalone test": "VLAN 175 (SA-1 Ryff)",
    "core5 test": "VLAN 200 (Core-5 Test)"
}


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

    def get_homelab_locations(self, target_name="all"):
        ok, locs = self.get_locations()
        if not ok:
            return None, f"Failed to retrieve locations: {locs}"
        
        filtered = []
        for loc in locs:
            name = loc.get("name", "")
            if any(ex.lower() in name.lower() for ex in EXCLUDED_LOCATIONS):
                continue
            if target_name.lower() == "all":
                if any(p.lower() in name.lower() for p in PROJECT_LOCATIONS):
                    filtered.append(loc)
            elif target_name.lower() in name.lower():
                filtered.append(loc)
        return filtered, ""

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

    def get_relationship_types(self):
        if hasattr(self, "_relationship_types") and self._relationship_types:
            return True, self._relationship_types
        url = f"{OVRC_API_BASE}/devices/relationships/types"
        ok, res = self._request(url, method="GET")
        if ok and isinstance(res, dict):
            types_list = res.get("types", [])
            types_map = {t.get("code"): t.get("id") for t in types_list}
            self._relationship_types = types_map
            return True, types_map
        return False, res

    def get_device_relationships(self, device_id):
        url = f"{OVRC_API_BASE}/devices/{device_id}/relationships"
        return self._request(url, method="GET")

    def set_device_relationship(self, device_id, parent_device_id, relationship_type_code, details, is_manual=True):
        ok, types = self.get_relationship_types()
        if not ok:
            return False, f"Failed to get relationship types: {types}"
        type_id = types.get(relationship_type_code)
        if not type_id:
            return False, f"Unknown relationship type code: {relationship_type_code}"
        url = f"{OVRC_API_BASE}/devices/{device_id}/relationships"
        body = {
            "parent_device_id": parent_device_id,
            "relationship_type_id": type_id,
            "is_manual": is_manual,
            "details": details
        }
        return self._request(url, method="POST", data=body)

    def delete_device_relationship(self, device_id, relationship_id):
        url = f"{OVRC_API_BASE}/devices/{device_id}/relationships"
        return self._request(url, method="DELETE", data={"relationshipId": relationship_id})


AUTHORITATIVE_TOPOLOGY = {
    # Wattbox WB-800 PDU (MAC: 14:3F:C3:02:25:71) Outlets:
    "power": {
        "14:3F:C3:91:50:8C": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 2},   # Araknis 520 Router
        "14:3F:C3:91:0F:8B": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 3},   # Araknis 920 Switch
        "8C:DC:D4:3E:A7:D8": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 4},   # pve3 HP EliteDesk
        "9C:EB:E8:96:11:44": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 5},   # pve Dell Precision
        "EC:B5:FA:8D:E0:05": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 6},   # Philips Hue Bridge
        "38:F7:CD:C1:67:E0": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 8},   # pve2 Awow Mini PC
        "38:2C:4A:69:90:90": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 9},   # Asus RT-N66U (DD-WRT Aurora)
        "00:0F:FF:20:74:D0": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 10},  # Control4 CA-10 Director
        "90:A7:C1:9E:D9:26": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 11},  # Pakedge SX-8P Switch
        "00:0F:FF:0C:33:AE": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 11},  # Control4 Core-5 Test
        "00:0F:FF:0C:41:CA": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 11},  # Triad SA1 Ryff Test
        "88:6A:E3:D8:EB:1C": {"parent_mac": "14:3F:C3:02:25:71", "parent_name": "Wattbox WB-800 PDU", "outlet": 12},  # Vivint Security Panel
    },
    # Switch Port Topology:
    "network": {
        # Araknis AN-920-SW-F-24-POE (MAC: 14:3F:C3:91:0F:8B)
        "9C:EB:E8:96:11:44": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 2, "has_poe": False},   # pve Dell
        "14:3F:C3:E8:B9:93": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 3, "has_poe": True},    # AP Front
        "14:3F:C3:E8:B9:A2": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 4, "has_poe": True},    # AP Back
        "00:0F:FF:0C:41:CA": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 5, "has_poe": False},   # Triad SA1 Ryff
        "90:A7:C1:9E:D9:26": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 7, "has_poe": False},   # Pakedge SX-8P
        "00:0F:FF:0C:33:AE": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 8, "has_poe": False},   # Core-5 Test
        "00:0F:FF:20:74:D0": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 11, "has_poe": False},  # CA-10 Director
        "14:3F:C3:02:25:71": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 12, "has_poe": False},  # Wattbox PDU
        "00:0F:FF:0B:31:AF": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 13, "has_poe": False},  # Core-5 Dev
        "EC:B5:FA:8D:E0:05": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 14, "has_poe": False},  # Hue Bridge
        "88:6A:E3:D8:EB:1C": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 17, "has_poe": False},  # Vivint Panel
        "8C:DC:D4:3E:A7:D8": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 21, "has_poe": False},  # pve3 HP
        "38:F7:CD:C1:67:E0": {"parent_mac": "14:3F:C3:91:0F:8B", "parent_name": "Araknis 920 POE Switch", "port": 23, "has_poe": False},  # pve2 Awow
        # Pakedge SX-8P Switch (MAC: 90:A7:C1:9E:D9:26)
        "7C:1E:B3:F0:26:55": {"parent_mac": "90:A7:C1:9E:D9:26", "parent_name": "Pakedge SX-8P Switch", "port": 2, "has_poe": True},     # Control4 DS2
        "D4:6A:91:9C:00:69": {"parent_mac": "90:A7:C1:9E:D9:26", "parent_name": "Pakedge SX-8P Switch", "port": 3, "has_poe": True},     # Luma X20 Cam 3
        "D4:6A:91:9C:00:8A": {"parent_mac": "90:A7:C1:9E:D9:26", "parent_name": "Pakedge SX-8P Switch", "port": 4, "has_poe": True},     # Luma X20 Cam 2
        "D4:6A:91:9C:00:67": {"parent_mac": "90:A7:C1:9E:D9:26", "parent_name": "Pakedge SX-8P Switch", "port": 5, "has_poe": True},     # Luma X20 Cam 1
        "00:0F:FF:51:92:2F": {"parent_mac": "90:A7:C1:9E:D9:26", "parent_name": "Pakedge SX-8P Switch", "port": 8, "has_poe": True},     # Control4 CA-1 Test
    }
}


def align_ovrc(action="preview", token=None, username=None, password=None,
               location_name="all",
               ovrc_csv_path=DEFAULT_OVRC_CSV, reservations_path=DEFAULT_RESERVATIONS,
               output_csv_path=OUTPUT_ALIGNED_CSV):
    """
    Correlates and aligns OvrC device names with authoritative DHCP reservations.
    Actions:
      - 'status' : Display multi-location homelab status, device count, and Unspecified count.
      - 'scan'   : Trigger a fresh network discovery scan across homelab locations.
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
        locs, loc_err = client.get_homelab_locations(location_name)
        if not locs:
            return f"Error locating site(s): {loc_err}"
        results = []
        for loc in locs:
            loc_id = loc.get("locationId")
            name = loc.get("name")
            ok, res = client.trigger_scan(loc_id)
            if ok:
                results.append(f"  ✓ Initiated scan for '{name}' (ID: {loc_id})")
            else:
                results.append(f"  ✗ Failed scan for '{name}': {res}")
            time.sleep(0.5)
        return "=== OvrC Homelab Multi-Location Scan Initiation ===\n" + "\n".join(results)

    # 2. Action: status
    if action == "status":
        locs, loc_err = client.get_homelab_locations(location_name)
        if not locs:
            return f"Error locating site(s): {loc_err}"

        out = [
            f"=== OvrC Homelab Multi-Location Status ===",
            f"{'Location Name':<24} {'Location ID':<26} {'VLAN / Subnet':<28} {'Devices':<9} {'Unspecified'}",
            "-" * 105
        ]
        total_devs = 0
        total_unspec = 0
        for loc in locs:
            loc_id = loc.get("locationId")
            lname = loc.get("name", "")
            vlan_desc = LOCATION_VLAN_MAP.get(lname.lower(), "Homelab Scope")
            ok_dev, devs = client.get_devices(loc_id)
            d_count = len(devs) if ok_dev else 0
            u_count = len([d for d in devs if d.get("name") in ("Unspecified", "Unknown", "") or not d.get("name")]) if ok_dev else 0
            total_devs += d_count
            total_unspec += u_count
            out.append(f"{lname:<24} {loc_id:<26} {vlan_desc:<28} {d_count:<9} {u_count}")
            time.sleep(0.2)

        out.append("-" * 105)
        out.append(f"Total Fleet: {total_devs} devices across {len(locs)} homelab locations ({total_unspec} unspecified).")
        out.append(f"[Excluded External Location: Nicola Home]")
        out.append("=" * 105)
        return "\n".join(out)

    # 3. Action: topology / topology-apply
    if action in ("topology", "topology-apply"):
        if not auth_ok:
            return (
                f"Error: Unable to authenticate with OvrC Cloud ({auth_msg}).\n"
                f"Please verify {SECRET_FILE} exists and is decryptable, or pass valid credentials."
            )
        locs, loc_err = client.get_homelab_locations(location_name)
        if not locs:
            return f"Error locating site(s): {loc_err}"

        all_devices = []
        dev_by_mac = {}
        dev_by_id = {}
        for loc in locs:
            loc_id = loc.get("locationId")
            lname = loc.get("name")
            ok_dev, devs = client.get_devices(loc_id)
            if ok_dev:
                for d in devs:
                    d["_locationId"] = loc_id
                    d["_locationName"] = lname
                    all_devices.append(d)
                    dev_by_id[d.get("deviceId")] = d
                    nmac = normalize_mac(d.get("macAddress", ""))
                    if nmac:
                        dev_by_mac[nmac] = d
            time.sleep(0.2)

        apply_mode = (action == "topology-apply")
        out = [
            f"=== OvrC Network & Power Topology Alignment ({'APPLY' if apply_mode else 'DRY-RUN PREVIEW'}) ===",
            f"{'Device Name':<28} {'Location':<14} {'Connected To (Switch/Port)':<34} {'Powered By (Outlet/PoE)':<30} {'Status'}",
            "-" * 125
        ]

        aligned_count = 0
        updated_count = 0
        error_count = 0

        target_macs = sorted(list(set(list(AUTHORITATIVE_TOPOLOGY["network"].keys()) + list(AUTHORITATIVE_TOPOLOGY["power"].keys()))))

        for mac in target_macs:
            dev = dev_by_mac.get(mac)
            if not dev:
                continue

            did = dev.get("deviceId")
            dname = dev.get("name", "Unknown")
            dloc = dev.get("_locationName", "Homelab")

            ok_r, rels = client.get_device_relationships(did)
            time.sleep(0.2)
            r_data = rels.get("relationships", {}) if ok_r and isinstance(rels, dict) else {}
            curr_power = r_data.get("power", {}).get("parent")
            curr_network = r_data.get("wired_network", {}).get("parent")

            target_net = AUTHORITATIVE_TOPOLOGY["network"].get(mac)
            target_pwr = AUTHORITATIVE_TOPOLOGY["power"].get(mac)

            curr_net_str = "None"
            if curr_network:
                p_dev = dev_by_id.get(curr_network.get("device_id"), {})
                p_name = p_dev.get("name", f"Dev {curr_network.get('device_id')[-6:]}")
                curr_net_str = f"{p_name} Port {curr_network.get('details', {}).get('port')}"

            curr_pwr_str = "None"
            if curr_power:
                p_dev = dev_by_id.get(curr_power.get("device_id"), {})
                p_name = p_dev.get("name", f"Dev {curr_power.get('device_id')[-6:]}")
                curr_pwr_str = f"{p_name} Outlet {curr_power.get('details', {}).get('outlet')}"
            elif curr_network and curr_network.get("details", {}).get("hasPoe"):
                p_dev = dev_by_id.get(curr_network.get("device_id"), {})
                p_name = p_dev.get("name", f"Dev {curr_network.get('device_id')[-6:]}")
                curr_pwr_str = f"PoE ({p_name})"

            target_net_str = "Unchanged"
            target_pwr_str = "Unchanged"
            needs_net_update = False
            needs_pwr_update = False

            if target_net:
                target_net_str = f"{target_net['parent_name']} Port {target_net['port']}"
                parent_dev = dev_by_mac.get(normalize_mac(target_net["parent_mac"]))
                if not parent_dev:
                    target_net_str += " (Parent Not Found)"
                else:
                    if (not curr_network or 
                        curr_network.get("device_id") != parent_dev.get("deviceId") or 
                        curr_network.get("details", {}).get("port") != target_net["port"] or 
                        bool(curr_network.get("details", {}).get("hasPoe")) != bool(target_net.get("has_poe", False))):
                        needs_net_update = True

            if target_pwr:
                target_pwr_str = f"{target_pwr['parent_name']} Outlet {target_pwr['outlet']}"
                parent_dev = dev_by_mac.get(normalize_mac(target_pwr["parent_mac"]))
                if not parent_dev:
                    target_pwr_str += " (Parent Not Found)"
                else:
                    if (not curr_power or 
                        curr_power.get("device_id") != parent_dev.get("deviceId") or 
                        curr_power.get("details", {}).get("outlet") != target_pwr["outlet"]):
                        needs_pwr_update = True

            if target_net and target_net.get("has_poe"):
                target_pwr_str = f"PoE ({target_net['parent_name']})"

            status = "Aligned"
            if needs_net_update or needs_pwr_update:
                status = "Drift (Will Align)" if not apply_mode else "Updating..."

                if apply_mode:
                    success = True
                    if needs_net_update:
                        p_dev = dev_by_mac.get(normalize_mac(target_net["parent_mac"]))
                        if p_dev:
                            if curr_network:
                                client.delete_device_relationship(did, curr_network.get("relationship_id"))
                                time.sleep(0.3)
                            ok_set, set_res = client.set_device_relationship(
                                did, p_dev.get("deviceId"), "wired_network",
                                {"port": target_net["port"], "hasPoe": target_net.get("has_poe", False)}
                            )
                            if not ok_set:
                                success = False
                                status = f"Err Net: {set_res}"
                            time.sleep(0.4)

                    if needs_pwr_update and not (target_net and target_net.get("has_poe")):
                        p_dev = dev_by_mac.get(normalize_mac(target_pwr["parent_mac"]))
                        if p_dev:
                            if curr_power:
                                client.delete_device_relationship(did, curr_power.get("relationship_id"))
                                time.sleep(0.3)
                            ok_set, set_res = client.set_device_relationship(
                                did, p_dev.get("deviceId"), "power",
                                {"outlet": target_pwr["outlet"]}
                            )
                            if not ok_set:
                                success = False
                                status = f"Err Pwr: {set_res}"
                            time.sleep(0.4)

                    if success:
                        status = "✓ Applied"
                        updated_count += 1
                    else:
                        error_count += 1
            else:
                aligned_count += 1

            disp_net = curr_net_str if not needs_net_update else f"{curr_net_str} -> {target_net_str}"
            disp_pwr = curr_pwr_str if not needs_pwr_update else f"{curr_pwr_str} -> {target_pwr_str}"
            out.append(f"{dname:<28} {dloc:<14} {disp_net:<34} {disp_pwr:<30} {status}")

        out.append("-" * 125)
        out.append(f"Topology Summary: {aligned_count} aligned, {updated_count} updated, {error_count} errors.")
        if not apply_mode:
            out.append("Run with action='topology-apply' to write these relationships live to OvrC Cloud.")
        out.append("=" * 125)
        return "\n".join(out)

    # For preview / apply / csv: Fetch live devices if authenticated, else fallback to CSV
    live_mode = auth_ok
    devices_to_process = []
    location_rooms_map = {}  # loc_id -> {room_name.lower(): room_id}

    if live_mode:
        locs, loc_err = client.get_homelab_locations(location_name)
        if locs:
            for loc in locs:
                loc_id = loc.get("locationId")
                lname = loc.get("name", "")
                rooms_map = {}
                ok_rooms, rooms_list = client.get_rooms(loc_id)
                if ok_rooms:
                    for rm in rooms_list:
                        rooms_map[rm.get("name", "").strip().lower()] = rm.get("roomId") or rm.get("id")
                location_rooms_map[loc_id] = rooms_map

                ok_dev, live_devs = client.get_devices(loc_id)
                if ok_dev:
                    for d in live_devs:
                        d["_locationId"] = loc_id
                        d["_locationName"] = lname
                        devices_to_process.append(d)
                time.sleep(0.3)

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
                    "_locationId": "local",
                    "_locationName": "Theurer Home",
                    "_is_csv": True
                })

    aligned_csv_path = OUTPUT_ALIGNED_CSV if os.path.exists(OUTPUT_ALIGNED_CSV) else ovrc_csv_path
    csv_overrides = {}
    if os.path.exists(aligned_csv_path):
        with open(aligned_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                nmac = normalize_mac(r.get("MAC Address", ""))
                if nmac:
                    csv_overrides[nmac] = {
                        "name": r.get("Device Name", "").strip(),
                        "room": r.get("Room", "").strip(),
                        "location": r.get("Location", "").strip()
                    }

    output_lines = [
        f"=== OvrC Device Inventory Alignment ({action.upper()}) ===",
        f"Scope: {location_name.upper()} ({len(location_rooms_map)} locations queried)",
        f"Source: {'Live OvrC Cloud API' if live_mode else 'Local Blueprint CSV'}",
        f"Total Devices Evaluated: {len(devices_to_process)}",
        f"Authoritative Reservations: {len(reservations)}\n",
        f"{'Location':<18} {'IP Address':<16} {'MAC Address':<18} {'Current OvrC Name':<28} {'Target Authoritative Name':<30} {'Result / Action'}",
        "-" * 135
    ]

    aligned_csv_rows = []
    renamed_count = 0
    room_updated_count = 0
    matched_count = 0
    untracked_count = 0
    error_count = 0

    for dev in devices_to_process:
        mac = normalize_mac(dev.get("macAddress") or dev.get("activeMacAddress", ""))
        ip = (dev.get("lanAddress") or dev.get("ipAddress") or "").split(":")[0].strip()
        curr_name = (dev.get("name") or "").strip()
        dev_id = dev.get("deviceId")
        dev_loc_id = dev.get("_locationId")
        dev_loc_name = dev.get("_locationName", "Theurer Home")
        curr_room_id = dev.get("roomId")

        matched = res_by_mac.get(mac) or res_by_ip.get(ip)
        csv_info = csv_overrides.get(mac, {})

        if not matched and not csv_info:
            output_lines.append(f"{dev_loc_name:<18} {ip:<16} {mac:<18} {curr_name:<28} {'(No DHCP Reservation)':<30} [UNTRACKED]")
            untracked_count += 1
            aligned_csv_rows.append({
                "Location": dev_loc_name,
                "Device Name": curr_name,
                "Room": "Unassigned",
                "IP Address": ip,
                "MAC Address": mac,
                "Status": "Untracked"
            })
            continue

        matched_name = matched.get("name", "").strip() if matched else ""
        csv_name = csv_info.get("name", "").strip()
        if matched_name and matched_name.lower() not in ("unspecified", "unknown", "none", ""):
            auth_name = matched_name
        elif csv_name and csv_name.lower() not in ("unspecified", "unknown", "none", ""):
            auth_name = csv_name
        else:
            auth_name = curr_name

        # If matched reservation exists, infer room from authoritative name first
        inferred_room = get_room_from_name(auth_name)
        csv_room = csv_info.get("room", "").strip()
        if inferred_room and inferred_room != "Unassigned":
            target_room_name = inferred_room
        elif csv_room and csv_room.lower() not in ("unassigned", "none", ""):
            target_room_name = csv_room
        else:
            target_room_name = "Unassigned"
        rooms_map = location_rooms_map.get(dev_loc_id, {})
        target_room_id = rooms_map.get(target_room_name.lower())

        is_generic = (
            curr_name.lower() in ("unspecified", "unknown", "") or
            curr_name.startswith("NPID") or
            curr_name.lower() in ("samsung", "tuya smart inc.", "apple, inc.", "pakedge-hostname", "sa1", "core5")
        )
        needs_rename = is_generic or (curr_name != auth_name)
        needs_room_update = bool(target_room_id and dev_loc_id and (curr_room_id != target_room_id))

        if action == "apply" and live_mode and dev_id:
            status_text = []
            if needs_rename:
                ok_rn, err_rn = client.rename_device(dev_id, auth_name)
                if ok_rn:
                    status_text.append("RENAMED")
                    renamed_count += 1
                else:
                    status_text.append(f"RENAME_FAILED({err_rn})")
                    error_count += 1
                time.sleep(0.5)
            else:
                status_text.append("NAME_ALIGNED")
                matched_count += 1

            if needs_room_update:
                ok_rm, err_rm = client.assign_room(dev_id, dev_loc_id, target_room_id)
                if ok_rm:
                    status_text.append(f"ROOM->{target_room_name}")
                    room_updated_count += 1
                else:
                    status_text.append(f"ROOM_FAILED({err_rm})")
                    error_count += 1
                time.sleep(0.5)

            output_lines.append(f"{dev_loc_name:<18} {ip:<16} {mac:<18} {curr_name:<28} {auth_name:<30} [{', '.join(status_text)}]")

        else:
            # Preview / CSV mode
            actions = []
            if needs_rename:
                actions.append(f"RENAME -> {auth_name}")
                renamed_count += 1
            if needs_room_update:
                actions.append(f"ROOM -> {target_room_name}")
                room_updated_count += 1
            if not actions:
                actions.append("MATCHED")
                matched_count += 1
            output_lines.append(f"{dev_loc_name:<18} {ip:<16} {mac:<18} {curr_name:<28} {auth_name:<30} [{', '.join(actions)}]")

        aligned_csv_rows.append({
            "Location": dev_loc_name,
            "Device Name": auth_name,
            "Room": target_room_name,
            "IP Address": ip,
            "MAC Address": mac,
            "Status": "Aligned"
        })

    if action == "csv":
        fieldnames = ["Location", "Device Name", "Room", "IP Address", "MAC Address", "Status"]
        with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(aligned_csv_rows)
        output_lines.append(f"\nAligned blueprint CSV saved to: {output_csv_path}")

    output_lines.append("-" * 135)
    output_lines.append(
        f"Summary: {renamed_count} to rename/renamed, {matched_count} already matched, "
        f"{untracked_count} untracked, {error_count} errors."
    )
    if action == "preview":
        output_lines.append("To push these updates live to OvrC Cloud, run with action='apply'.")
    output_lines.append("=" * 135)

    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(description="Correlate, align, and sync OvrC devices with DHCP reservations")
    parser.add_argument("action", nargs="?", default="preview",
                        choices=["status", "scan", "preview", "csv", "apply", "topology", "topology-apply"],
                        help="Action to perform: 'status', 'scan', 'preview' (dry-run), 'csv' (export blueprint), 'apply' (push names/rooms), 'topology' (audit network & power topology), 'topology-apply' (link switch ports & outlets)")
    parser.add_argument("--token", default=None, help="OvrC Bearer token or API key")
    parser.add_argument("--user", default=None, help="OvrC username")
    parser.add_argument("--password", default=None, help="OvrC password")
    parser.add_argument("--location", default="all", help="Target location name (or 'all' for all 4 project locations)")
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
