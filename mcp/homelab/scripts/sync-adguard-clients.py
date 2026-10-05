#!/usr/bin/env python3
"""
Sync DHCP Reservations from dhcp-reservations-reorganized.json to AdGuard Home.

This tool reads authoritative DHCP reservations and upserts them into AdGuard Home's
Persistent Clients list via the AdGuard Home REST API.
Applied to Primary AdGuard Home (nexus-server @ 192.168.40.185:8081).
adguardhome-sync automatically replicates them to Secondary AdGuard Home (nexus-server2).
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_RESERVATIONS_PATH = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "dhcp-reservations-reorganized.json")
DEFAULT_HOST = "http://192.168.40.185:8081"

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

def sync_clients(reservations_path=DEFAULT_RESERVATIONS_PATH, host=DEFAULT_HOST, user=None, password=None, dry_run=False):
    if not os.path.exists(reservations_path):
        return f"Error: reservations file not found at {reservations_path}"

    with open(reservations_path, "r") as f:
        res_data = json.load(f)

    reservations = res_data.get("dhcpReservations", [])
    output_lines = [f"Loaded {len(reservations)} DHCP reservations from GitOps blueprint."]

    user = user or os.environ.get("ADGUARD_USER", os.environ.get("ADGUARD_USERNAME"))
    password = password or os.environ.get("ADGUARD_PASSWORD")
    auth_headers = get_auth_header(user, password)

    # 1. Fetch current clients
    status, resp = api_request(f"{host}/control/clients", headers=auth_headers)
    if status != 200:
        return f"Failed to connect to AdGuard Home at {host} (HTTP {status}): {resp}\nNote: Check if AdGuard Home requires authentication."

    existing_clients = resp.get("clients", []) if isinstance(resp, dict) else []
    output_lines.append(f"AdGuard Home currently has {len(existing_clients)} persistent clients.")

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

        matched_client = by_name.get(name.lower())
        if not matched_client and mac:
            matched_client = by_id.get(mac)
        if not matched_client:
            matched_client = by_id.get(ip.lower())

        if matched_client:
            curr_ids = [cid.strip().lower() for cid in matched_client.get("ids", [])]
            if ip.lower() not in curr_ids or (mac and mac not in curr_ids):
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
                if dry_run:
                    output_lines.append(f"[DRY-RUN UPDATE] '{matched_client['name']}' -> '{name}' IDs: {merged_ids}")
                else:
                    up_status, up_resp = api_request(f"{host}/control/clients/update", method="POST", data=payload, headers=auth_headers)
                    if up_status == 200:
                        output_lines.append(f"[UPDATED] '{name}' -> IDs: {merged_ids}")
                    else:
                        output_lines.append(f"[ERROR UPDATING] '{name}': HTTP {up_status} {up_resp}")
                updated_count += 1
            else:
                unchanged_count += 1
        else:
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
            if dry_run:
                output_lines.append(f"[DRY-RUN ADD] '{name}' IDs: {target_ids}")
            else:
                add_status, add_resp = api_request(f"{host}/control/clients/add", method="POST", data=payload, headers=auth_headers)
                if add_status == 200:
                    output_lines.append(f"[ADDED] '{name}' -> IDs: {target_ids}")
                else:
                    output_lines.append(f"[ERROR ADDING] '{name}': HTTP {add_status} {add_resp}")
            added_count += 1

    output_lines.append("\n" + "=" * 50)
    action_str = "Previewed" if dry_run else "Synchronized"
    output_lines.append(f"{action_str}: {added_count} to add, {updated_count} to update, {unchanged_count} already current.")
    output_lines.append("Replication: adguardhome-sync will automatically mirror changes to Secondary AdGuard Home.")
    output_lines.append("=" * 50)

    return "\n".join(output_lines)

def main():
    parser = argparse.ArgumentParser(description="Sync DHCP reservations to AdGuard Home clients")
    parser.add_argument("--reservations", default=DEFAULT_RESERVATIONS_PATH)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = sync_clients(args.reservations, args.host, args.user, args.password, args.dry_run)
    print(result)

if __name__ == "__main__":
    main()
