#!/usr/bin/env python3
"""
OvrC Cloud API Device Renaming & Alignment Tool.

Uses the OvrC Cloud API (https://api.ovrc.com/v2 or https://app.ovrc.com/api/v1)
to bulk-update device names and room assignments matching ovrc-device-list-aligned.csv.

Authentication:
  Supply an OvrC Bearer token (from browser DevTools on app.ovrc.com or OvrC API key)
  via --token or the OVRC_TOKEN environment variable.

Usage:
  python3 scripts/ovrc_bulk_rename.py --token "<bearer_token>" [--dry-run]
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_ALIGNED_CSV = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "ovrc-device-list-aligned.csv")
OVRC_API_BASE = "https://app.ovrc.com/api/v1"

def normalize_mac(mac):
    if not mac:
        return ""
    return mac.strip().upper().replace("-", ":")

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

def main():
    parser = argparse.ArgumentParser(description="Bulk rename devices in OvrC via Cloud API")
    parser.add_argument("--token", default=os.environ.get("OVRC_TOKEN", ""),
                        help="OvrC Bearer Token or API key (or set OVRC_TOKEN)")
    parser.add_argument("--csv", default=DEFAULT_ALIGNED_CSV,
                        help="Path to ovrc-device-list-aligned.csv")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview API calls without executing them")
    args = parser.parse_args()

    if not args.token and not args.dry_run:
        print("Error: OvrC Bearer token is required. Pass --token '<token>' or set OVRC_TOKEN.")
        print("\nHow to get your OvrC Bearer Token:")
        print("1. Log into https://app.ovrc.com in Chrome or Edge.")
        print("2. Open Developer Tools (F12) -> Network tab.")
        print("3. Click on any device or page refresh.")
        print("4. Find any request to '/api/' and copy the value of the 'Authorization' header (after 'Bearer ').")
        sys.exit(1)

    if not os.path.exists(args.csv):
        print(f"Error: Aligned CSV not found at {args.csv}")
        sys.exit(1)

    with open(args.csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        aligned_devices = list(reader)

    print(f"Loaded {len(aligned_devices)} devices from {os.path.basename(args.csv)}")

    # Filter to devices needing renaming
    to_rename = []
    for d in aligned_devices:
        name = d.get("Device Name", "").strip()
        mac = normalize_mac(d.get("MAC Address", ""))
        room = d.get("Room", "").strip()
        if name and name.lower() not in ("unspecified", "unknown") and mac:
            to_rename.append(d)

    print(f"Identified {len(to_rename)} devices with authoritative names ready for OvrC.")

    if args.dry_run:
        print("\n[DRY RUN PREVIEW - First 10 Devices]:")
        for d in to_rename[:10]:
            print(f"  MAC: {d['MAC Address']:<18} IP: {d['IP Address']:<16} Name: {d['Device Name']:<32} Room: {d['Room']}")
        print(f"  ... and {len(to_rename) - 10} more devices.")
        print("\nPass without --dry-run and provide --token to execute.")
        return

    # 1. Fetch live OvrC devices to get device UUIDs
    print("\nConnecting to OvrC Cloud API...")
    status, resp = api_call(f"{OVRC_API_BASE}/devices", token=args.token)
    if status != 200:
        print(f"Failed to query OvrC devices (HTTP {status}): {resp}")
        print("Check if the token is valid or expired.")
        sys.exit(1)

    ovrc_list = resp if isinstance(resp, list) else resp.get("devices", [])
    print(f"Found {len(ovrc_list)} devices in your OvrC account.")

    # Index by MAC
    ovrc_by_mac = {}
    for dev in ovrc_list:
        dev_mac = normalize_mac(dev.get("macAddress", dev.get("mac", "")))
        if dev_mac:
            ovrc_by_mac[dev_mac] = dev

    success_count = 0
    skipped_count = 0
    error_count = 0

    for d in to_rename:
        mac = normalize_mac(d["MAC Address"])
        target_name = d["Device Name"]
        target_room = d["Room"]

        ovrc_dev = ovrc_by_mac.get(mac)
        if not ovrc_dev:
            skipped_count += 1
            continue

        dev_id = ovrc_dev.get("id") or ovrc_dev.get("deviceId")
        current_name = ovrc_dev.get("name", "")

        if current_name == target_name:
            skipped_count += 1
            continue

        # Prepare update payload
        payload = {"name": target_name}
        if target_room and target_room != "Unassigned":
            payload["room"] = target_room

        up_status, up_resp = api_call(f"{OVRC_API_BASE}/devices/{dev_id}", method="PUT", data=payload, token=args.token)
        if up_status in (200, 204):
            print(f" [UPDATED] {d['IP Address']:<15} {target_name}")
            success_count += 1
        else:
            # Try PATCH
            up_status, up_resp = api_call(f"{OVRC_API_BASE}/devices/{dev_id}", method="PATCH", data=payload, token=args.token)
            if up_status in (200, 204):
                print(f" [UPDATED] {d['IP Address']:<15} {target_name}")
                success_count += 1
            else:
                print(f" [ERROR] {d['IP Address']} ({target_name}): HTTP {up_status} {up_resp}")
                error_count += 1

    print("\n" + "=" * 50)
    print(f"OvrC Renaming Complete: {success_count} updated, {skipped_count} skipped/unchanged, {error_count} errors.")
    print("=" * 50)

if __name__ == "__main__":
    main()
