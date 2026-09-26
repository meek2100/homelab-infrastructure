#!/usr/bin/env python3
"""
Configure SNMP 'homelab-metrics' across the Araknis Network Fleet.
1. Araknis 520 Router (192.168.1.1): REST API PUT /config/snmp
2. Araknis 920 Switch (192.168.1.215): FASTPATH CLI over SSH (Paramiko)
3. Araknis 830 APs (192.168.1.231, 236, 237): Web UI / API automation
"""

import base64
import importlib.util
import json
import os
import re
import sys
import time
import urllib3

urllib3.disable_warnings()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
COMMUNITY = "homelab-metrics"

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
    print(f"\n📡 [1/2] Configuring Araknis 520 Router (192.168.1.1)...")
    mar = load_router_module()
    host, user, pwd = mar.load_credentials()
    s = mar.create_session(host, user, pwd)
    
    current = mar.api_get(s, host, "/config/snmp")
    cfg = current.get("snmpConfig", {})
    print(f"  Current router SNMP config: snmpv1v2Enable={cfg.get('snmpv1v2Enable')}, getCommunityName={cfg.get('getCommunityName')}")
    
    cfg["snmpv1v2Enable"] = True
    cfg["getCommunityName"] = COMMUNITY
    cfg["setCommunityName"] = ""  # Read-only
    cfg["trapCommunityName"] = ""
    
    payload = {"snmpConfig": cfg}
    res = mar.api_put(s, host, "/config/snmp", payload)
    print(f"  Router update response: {res}")
    
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
    print(f"\n📡 [2/2] Configuring Araknis 920 Switch (192.168.1.215)...")
    mas = load_switch_module()
    host, user, pwd = mas.load_credentials()
    client, chan = mas.connect_switch(host, user, pwd)
    
    mas._send_cmd(chan, "configure")
    out = mas._send_cmd(chan, f"snmp-server community {COMMUNITY} ro")
    print(f"  Switch command output:\n{out.strip()}")
    
    mas._send_cmd(chan, "exit")
    save_out = mas._send_cmd(chan, "write memory", timeout=30)
    print(f"  Switch write memory output:\n{save_out.strip()}")
    
    # Verify
    check = mas._send_cmd(chan, "show snmp")
    client.close()
    
    if COMMUNITY in check and "READ-ONLY" in check:
        print(f"  ✓ Araknis 920 Switch successfully configured with SNMP community '{COMMUNITY}' (Read-Only)")
        return True
    else:
        print(f"  ❌ Verification failed:\n{check}")
        return False

def main():
    print("=== Configuring SNMP across Araknis Infrastructure ===")
    r_ok = configure_router()
    s_ok = configure_switch()
    
    print("\n--- Summary ---")
    print(f"Araknis 520 Router: {'✅ CONFIGURED' if r_ok else '❌ FAILED'}")
    print(f"Araknis 920 Switch: {'✅ CONFIGURED' if s_ok else '❌ FAILED'}")

if __name__ == "__main__":
    main()
