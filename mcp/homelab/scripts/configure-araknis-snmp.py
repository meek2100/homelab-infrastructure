#!/usr/bin/env python3
"""
Configure SNMP 'homelab-metrics' across the entire Araknis Network Fleet via REST API & CLI.
1. Araknis 520 Router (192.168.1.1): REST API PUT /config/snmp
2. Araknis 920 Switch (192.168.1.215): FASTPATH CLI over SSH (Paramiko)
3. Araknis 830 AP 1 (192.168.1.231): REST API POST /api/gui/sys/snmpv2 + /api/gui/sys/apply
4. Araknis 830 AP 2 (192.168.1.236): REST API POST /api/gui/sys/snmpv2 + /api/gui/sys/apply
5. Araknis 830 AP 3 (192.168.1.237): REST API POST /api/gui/sys/snmpv2 + /api/gui/sys/apply
"""

import argparse
import base64
import importlib.util
import json
import os
import re
import socket
import sys
import time
import urllib3

urllib3.disable_warnings()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
COMMUNITY = "homelab-metrics"

APS = [
    ("192.168.1.231", "House Front"),
    ("192.168.1.236", "House Back"),
    ("192.168.1.237", "Office Bridge"),
]

def load_router_module():
    spec = importlib.util.spec_from_file_location("mar", os.path.join(os.path.dirname(__file__), "manage-araknis-router.py"))
    mar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mar)
    return mar

def load_switch_module():
    spec = importlib.util.spec_from_file_location("mas", os.path.join(os.path.dirname(__file__), "manage-araknis-switch.py"))
    mas = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mas)
    return mas

def configure_router():
    print(f"\n📡 [Router] Configuring Araknis 520 Router (192.168.1.1)...")
    mar = load_router_module()
    host, user, pwd = mar.load_credentials()
    s = mar.create_session(host, user, pwd)
    
    current = mar.api_get(s, host, "/config/snmp")
    cfg = current.get("snmpConfig", {})
    cfg["snmpv1v2Enable"] = True
    cfg["getCommunityName"] = COMMUNITY
    cfg["setCommunityName"] = ""  # Read-only
    cfg["trapCommunityName"] = ""
    
    payload = {"snmpConfig": cfg}
    res = mar.api_put(s, host, "/config/snmp", payload)
    
    # Verify
    verify = mar.api_get(s, host, "/config/snmp")
    v_cfg = verify.get("snmpConfig", {})
    if v_cfg.get("snmpv1v2Enable") is True and v_cfg.get("getCommunityName") == COMMUNITY:
        print(f"  ✓ Araknis 520 Router successfully configured with SNMP community '{COMMUNITY}' (Read-Only)")
        return True
    else:
        print(f"  ❌ Verification failed: {v_cfg}")
        return False

def configure_switch():
    print(f"\n📡 [Switch] Configuring Araknis 920 Switch (192.168.1.215)...")
    mas = load_switch_module()
    host, user, pwd = mas.load_credentials()
    client, chan = mas.connect_switch(host, user, pwd, timeout=20)
    
    mas._send_cmd(chan, "configure")
    out = mas._send_cmd(chan, f"snmp-server community {COMMUNITY} ro")
    mas._send_cmd(chan, "exit")
    
    # Send write memory with confirmation
    while chan.recv_ready(): chan.recv(4096)
    chan.send("write memory\n")
    for _ in range(50):
        if chan.recv_ready():
            chunk = chan.recv(4096).decode("utf-8", errors="ignore")
            if "(y/n)" in chunk:
                chan.send("y")
                break
        time.sleep(0.1)
    mas._read_until_prompt(chan, timeout=30)
    
    # Verify
    check = mas._send_cmd(chan, "show snmp")
    client.close()
    
    if COMMUNITY in check and "READ-ONLY" in check:
        print(f"  ✓ Araknis 920 Switch successfully configured with SNMP community '{COMMUNITY}' (Read-Only)")
        return True
    else:
        print(f"  ❌ Verification failed:\n{check}")
        return False

def configure_ap(ap_ip, location_name):
    import requests
    print(f"\n📡 [AP] Configuring Araknis 830 AP ({ap_ip} - {location_name})...")
    mar = load_router_module()
    _, user, pwd = mar.load_credentials()
    
    # 1. Authenticate to AP REST API
    try:
        r_login = requests.post(
            f"https://{ap_ip}/api/gui/sys/login",
            json={"login": {"username": user, "password": pwd}},
            verify=False,
            timeout=8
        )
        login_data = r_login.json()
        token = login_data["login"]["token"]
        device_id = login_data["deviceId"]
    except Exception as e:
        print(f"  ❌ Failed to login to AP {ap_ip}: {e}")
        return False
        
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Post SNMPv2 configuration
    snmpv2_payload = {
        "snmpv2": {
            "enable": True,
            "contact": "homelab-admin",
            "location": location_name,
            "port": 161,
            "readCommunity": COMMUNITY,
            "writeCommunity": "disabled-rw-key",
            "trapServerIPAddress": "",
            "trapServerPort": 162,
            "trapCommunity": "public"
        }
    }
    try:
        r_v2 = requests.post(f"https://{ap_ip}/api/gui/sys/snmpv2", json=snmpv2_payload, headers=headers, verify=False, timeout=8)
        v2_res = r_v2.json()
        if v2_res.get("errCode") != 0:
            print(f"  ❌ SNMPv2 POST returned error: {v2_res}")
            return False
            
        # 3. Apply settings
        r_apply = requests.post(f"https://{ap_ip}/api/gui/sys/apply", json={"deviceMAC": device_id}, headers=headers, verify=False, timeout=12)
        apply_res = r_apply.json()
        if apply_res.get("errCode") != 0:
            print(f"  ❌ Apply returned error: {apply_res}")
            return False
            
        time.sleep(2)
        
        # 4. Verify via GET
        r_verify = requests.get(f"https://{ap_ip}/api/gui/sys/snmp", headers=headers, verify=False, timeout=8)
        v_cfg = r_verify.json().get("snmpConfs", {}).get("snmpv2", {})
        if v_cfg.get("enable") is True and v_cfg.get("readCommunity") == COMMUNITY:
            print(f"  ✓ Araknis 830 AP ({ap_ip}) successfully configured with SNMP community '{COMMUNITY}'")
            return True
        else:
            print(f"  ❌ Verification failed: {v_cfg}")
            return False
    except Exception as e:
        print(f"  ❌ Error configuring AP {ap_ip}: {e}")
        return False

def test_snmp_udp(ip, timeout=2.5):
    community = COMMUNITY.encode("utf-8")
    oid = bytes([0x2b, 0x06, 0x01, 0x02, 0x01, 0x01, 0x01, 0x00]) # 1.3.6.1.2.1.1.1.0
    varbind = bytes([0x30, len(oid) + 4, 0x06, len(oid)]) + oid + bytes([0x05, 0x00])
    varbind_list = bytes([0x30, len(varbind)]) + varbind
    pdu = bytes([0xa0, len(varbind_list) + 9, 0x02, 0x01, 0x01, 0x02, 0x01, 0x00, 0x02, 0x01, 0x00]) + varbind_list
    packet = bytes([0x30, 3 + len(community) + 2 + len(pdu), 0x02, 0x01, 0x01, 0x04, len(community)]) + community + pdu

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (ip, 161))
        data, _ = sock.recvfrom(4096)
        printable = "".join(chr(b) if 32 <= b <= 126 else " " for b in data)
        return True, printable[-70:].strip()
    except Exception as e:
        return False, str(e)
    finally:
        sock.close()

def main():
    parser = argparse.ArgumentParser(description="Configure SNMP across Araknis Fleet")
    parser.add_argument("--target", choices=["all", "router", "switch", "aps"], default="all")
    args = parser.parse_args()

    print("=== Configuring SNMP across Araknis Fleet via REST API & CLI ===")
    results = {}
    
    if args.target in ["all", "router"]:
        results["Araknis 520 Router (192.168.1.1)"] = configure_router()
        
    if args.target in ["all", "switch"]:
        results["Araknis 920 Switch (192.168.1.215)"] = configure_switch()
        
    if args.target in ["all", "aps"]:
        for ip, name in APS:
            results[f"Araknis 830 AP ({ip} - {name})"] = configure_ap(ip, name)
            
    print("\n" + "="*50)
    print("📊 LIVE SNMP UDP PORT 161 PROBE VERIFICATION")
    print("="*50)
    all_targets = [("192.168.1.1", "Araknis 520 Router"), ("192.168.1.215", "Araknis 920 Switch")] + [(ip, f"Araknis 830 AP ({name})") for ip, name in APS]
    for ip, label in all_targets:
        ok, detail = test_snmp_udp(ip)
        status = "🟢 PASS" if ok else "🔴 FAIL"
        print(f"{status} | {ip:15} | {label:28} | {detail}")

if __name__ == "__main__":
    main()
