#!/usr/bin/env python3
"""
Correlate and align OvrC device list with authoritative DHCP reservations.

Matches OvrC devices by MAC Address (and IP) against dhcp-reservations-reorganized.json.
Identifies all 'Unspecified' or generic device names in OvrC and generates an enriched
CSV blueprint (ovrc-device-list-aligned.csv) with accurate human-readable names and rooms.
"""

import argparse
import csv
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_RESERVATIONS = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "dhcp-reservations-reorganized.json")
DEFAULT_OVRC_CSV = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "ovrc-device-list-latest.csv")
OUTPUT_ALIGNED_CSV = os.path.join(REPO_ROOT, "infrastructure", "network", "configs", "ovrc-device-list-aligned.csv")

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

def align_ovrc(ovrc_csv_path=DEFAULT_OVRC_CSV, reservations_path=DEFAULT_RESERVATIONS, output_csv_path=OUTPUT_ALIGNED_CSV):
    if not os.path.exists(reservations_path):
        return f"Error: reservations file not found at {reservations_path}"
    if not os.path.exists(ovrc_csv_path):
        return f"Error: OvrC CSV file not found at {ovrc_csv_path}"

    with open(reservations_path, "r") as f:
        res_data = json.load(f)

    reservations = res_data.get("dhcpReservations", [])
    res_by_mac = {}
    res_by_ip = {}
    for r in reservations:
        mac = normalize_mac(r.get("macAddress", ""))
        ip = r.get("staticIPAddress", "").strip()
        name = r.get("name", "").strip()
        if mac:
            res_by_mac[mac] = r
        if ip:
            res_by_ip[ip] = r

    with open(ovrc_csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    aligned_rows = []
    renamed_count = 0
    unchanged_count = 0
    unmatched_count = 0

    output_lines = [
        f"=== OvrC Device Inventory Alignment ===",
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
            # Determine if rename is needed
            # e.g. Unspecified, NPID93247, Samsung, or missing
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

    # Write aligned CSV
    with open(output_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(aligned_rows)

    output_lines.append("-" * 115)
    output_lines.append(f"Summary: {renamed_count} devices to rename, {unchanged_count} already accurate, {unmatched_count} untracked.")
    output_lines.append(f"Aligned blueprint saved to: {output_csv_path}")
    output_lines.append("=" * 115)

    return "\n".join(output_lines)

def main():
    parser = argparse.ArgumentParser(description="Correlate and align OvrC devices with DHCP reservations")
    parser.add_argument("--ovrc-csv", default=DEFAULT_OVRC_CSV)
    parser.add_argument("--reservations", default=DEFAULT_RESERVATIONS)
    parser.add_argument("--output", default=OUTPUT_ALIGNED_CSV)
    args = parser.parse_args()

    result = align_ovrc(args.ovrc_csv, args.reservations, args.output)
    print(result)

if __name__ == "__main__":
    main()
