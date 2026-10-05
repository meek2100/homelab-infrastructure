#!/usr/bin/env python3
"""
Sync DHCP Reservations from dhcp-reservations-reorganized.json to AdGuard Home.

This script reads the authoritative 90 DHCP reservations and upserts them
into AdGuard Home's Persistent Clients list via the AdGuard Home REST API
(POST /control/clients/add or POST /control/clients/update).

Once applied to Primary AdGuard Home (nexus-server), adguardhome-sync
automatically replicates them to Secondary AdGuard Home (nexus-server2).

Usage:
  python3 sync_adguard_clients.py [--host http://192.168.40.185:8081] [--user USER] [--password PASS] [--dry-run]
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

def get_auth_header(user, password):
    if user and password:
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}"}
    return {}

def api_request(url, method="GET", data=None, headers=None):
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
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
    parser = argparse.ArgumentParser(description="Sync DHCP reservations to AdGuard Home clients")
    parser.add_argument("--reservations", default="infrastructure/network/configs/dhcp-reservations-reorganized.json",
                        help="Path to dhcp-reservations-reorganized.json")
    parser.add_argument("--host", default="http://192.168.40.185:8081",
                        help="AdGuard Home base URL (default: http://192.168.40.185:8081)")
    parser.add_argument("--user", default=None, help="AdGuard Home admin username")
    parser.add_argument("--password", default=None, help="AdGuard Home admin password")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying AdGuard")
    args = parser.parse_args()

    # Load reservations
    if not os.path.exists(args.reservations):
        # Try finding relative to script dir
        script_dir = os.path.dirname(os.path.abspath(__file__))
        alt_path = os.path.abspath(os.path.join(script_dir, "..", args.reservations))
        if os.path.exists(alt_path):
            args.reservations = alt_path
        else:
            print(f"Error: reservations file not found at {args.reservations}")
            sys.exit(1)

    with open(args.reservations, "r") as f:
        res_data = json.load(f)

    reservations = res_data.get("dhcpReservations", [])
    print(f"Loaded {len(reservations)} DHCP reservations from {args.reservations}")

    auth_headers = get_auth_header(args.user, args.password)

    # 1. Fetch current clients
    status, resp = api_request(f"{args.host}/control/clients", headers=auth_headers)
    if status != 200:
        print(f"Failed to connect to AdGuard Home at {args.host} (HTTP {status}): {resp}")
        print("Note: If AdGuard Home requires authentication, supply --user and --password.")
        sys.exit(1)

    existing_clients = resp.get("clients", []) if isinstance(resp, dict) else []
    print(f"AdGuard Home currently has {len(existing_clients)} persistent clients.")

    # Index existing clients by name and by ID/IP/MAC
    by_name = {c["name"].strip().lower(): c for c in existing_clients if "name" in c}
    by_id = {}
    for c in existing_clients:
        for cid in c.get("ids", []):
            by_id[cid.strip().lower()] = c

    added_count = 0
    updated_count = 0
    unchanged_count = 0

    for r in reservations:
        name = r.get("name", "").strip()
        ip = r.get("staticIPAddress", "").strip()
        mac = r.get("macAddress", "").strip().lower()

        if not name or not ip:
            continue

        target_ids = [ip]
        if mac:
            target_ids.append(mac)

        # Check if client exists by name or by MAC/IP
        matched_client = by_name.get(name.lower())
        if not matched_client and mac:
            matched_client = by_id.get(mac)
        if not matched_client:
            matched_client = by_id.get(ip.lower())

        if matched_client:
            # Check if IDs need updating
            curr_ids = [cid.strip().lower() for cid in matched_client.get("ids", [])]
            
            # If IP is not in current IDs or changed
            if ip.lower() not in curr_ids or (mac and mac not in curr_ids):
                # Merge target IDs with any non-IP/MAC custom IDs (like tags or client IDs)
                other_ids = [cid for cid in matched_client.get("ids", []) if not cid.startswith("192.168.") and ":" not in cid]
                merged_ids = list(dict.fromkeys(target_ids + other_ids))
                payload = {
                    "name": matched_client["name"],
                    "data": {
                        "name": name,
                        "ids": merged_ids,
                        "use_global_settings": matched_client.get("use_global_settings", True),
                        "filtering_enabled": matched_client.get("filtering_enabled", True),
                        "parental_enabled": matched_client.get("parental_enabled", False),
                        "safesearch_enabled": matched_client.get("safesearch_enabled", False),
                        "use_global_blocked_services": matched_client.get("use_global_blocked_services", True),
                        "upstreams": matched_client.get("upstreams", []),
                        "tags": matched_client.get("tags", [])
                    }
                }
                if args.dry_run:
                    print(f"[DRY-RUN UPDATE] '{matched_client['name']}' -> '{name}' IDs: {merged_ids}")
                else:
                    up_status, up_resp = api_request(f"{args.host}/control/clients/update", method="POST", data=payload, headers=auth_headers)
                    if up_status == 200:
                        print(f"[UPDATED] '{name}' -> IDs: {merged_ids}")
                    else:
                        print(f"[ERROR UPDATING] '{name}': HTTP {up_status} {up_resp}")
                updated_count += 1
            else:
                unchanged_count += 1
        else:
            # Add new persistent client
            payload = {
                "name": name,
                "ids": target_ids,
                "use_global_settings": True,
                "filtering_enabled": True,
                "parental_enabled": False,
                "safesearch_enabled": False,
                "use_global_blocked_services": True,
                "upstreams": [],
                "tags": []
            }
            if args.dry_run:
                print(f"[DRY-RUN ADD] '{name}' IDs: {target_ids}")
            else:
                add_status, add_resp = api_request(f"{args.host}/control/clients/add", method="POST", data=payload, headers=auth_headers)
                if add_status == 200:
                    print(f"[ADDED] '{name}' -> IDs: {target_ids}")
                else:
                    print(f"[ERROR ADDING] '{name}': HTTP {add_status} {add_resp}")
            added_count += 1

    print("\n" + "="*50)
    print(f"Summary: {added_count} to add, {updated_count} to update, {unchanged_count} already current.")
    print("="*50)

if __name__ == "__main__":
    main()
