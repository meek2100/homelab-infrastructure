#!/usr/bin/env python3
"""Manage Araknis AN-830-AP-I access points via their native REST API.

Commands: status, backup, get, apply, restore, list-endpoints.
Credentials come from the same SOPS secret as the Araknis router (load_credentials).
Native encrypted exports go to infrastructure/network/configs/araknis-830-<ip>.config;
readable REST snapshots (secrets redacted by field name) go to araknis-830-<ip>.rest.json.
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import sys

import requests
import urllib3

urllib3.disable_warnings()

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CFG_DIR = os.path.join(REPO, "infrastructure", "network", "configs")
AP_IPS = {"ap1": "192.168.1.231", "ap2": "192.168.1.236", "ap3": "192.168.1.237"}
SNAPSHOT_ENDPOINTS = [
    "sys/device-info", "wireless/vlans", "wireless/ssidsConfig", "wireless/networks",
    "wireless/settings", "wireless/bridge", "wireless/stations", "wireless/radiostatus",
    "wireless/radioconfig?interface=2.4GHZ", "wireless/radioconfig?interface=5GHZ",
    "wireless/radioconfig?interface=6GHZ",
]
SECRET_KEY = re.compile(r"(pass|psk|key|secret|token|pwd|sae)", re.I)
SECRET_VAL = re.compile(r"(Bearer|sk-)[A-Za-z0-9_-]{6,}")


def _creds():
    spec = importlib.util.spec_from_file_location("mar", os.path.join(HERE, "manage-araknis-router.py"))
    mar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mar)
    _, user, pw = mar.load_credentials()
    return user, pw


def resolve(target):
    t = target.lower()
    if t in AP_IPS:
        return [AP_IPS[t]]
    if t == "all":
        return list(AP_IPS.values())
    return [target]


def login(ip, user, pw):
    r = requests.post(f"https://{ip}/api/gui/sys/login",
                      json={"login": {"username": user, "password": pw}}, verify=False, timeout=15)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["login"]["token"]}


def redact(o):
    if isinstance(o, dict):
        return {k: ("<redacted>" if SECRET_KEY.search(k) and isinstance(v, (str, int)) and v != "" else redact(v))
                for k, v in o.items()}
    if isinstance(o, list):
        return [redact(i) for i in o]
    if isinstance(o, str):
        return SECRET_VAL.sub(r"\1<redacted>", o)
    return o


def api_get(ip, h, ep):
    r = requests.get(f"https://{ip}/api/gui/{ep}", headers=h, verify=False, timeout=15)
    try:
        return r.json()
    except Exception:
        return {"http_status": r.status_code, "text": r.text[:500]}


def do_backup(ip, h, tag=""):
    os.makedirs(CFG_DIR, exist_ok=True)
    blob = requests.get(f"https://{ip}/api/getCFG", headers=h, verify=False, timeout=30)
    blob.raise_for_status()
    stamp = f"-{tag}" if tag else ""
    cfg = os.path.join(CFG_DIR, f"araknis-830-{ip}{stamp}.config")
    with open(cfg, "wb") as f:
        f.write(blob.content)
    snap = {ep: redact(api_get(ip, h, ep)) for ep in SNAPSHOT_ENDPOINTS}
    sp = os.path.join(CFG_DIR, f"araknis-830-{ip}{stamp}.rest.json")
    with open(sp, "w") as f:
        json.dump(snap, f, indent=1)
    return {"ip": ip, "config": cfg, "config_bytes": len(blob.content), "snapshot": sp}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("status", "backup", "list-endpoints"):
        s = sub.add_parser(name)
        s.add_argument("--target", default="all")
    g = sub.add_parser("get")
    g.add_argument("--target", required=True)
    g.add_argument("--endpoint", required=True)
    a = sub.add_parser("apply")
    a.add_argument("--target", required=True)
    a.add_argument("--endpoint", required=True)
    a.add_argument("--payload-file", required=True)
    a.add_argument("--method", default="POST", choices=["POST", "PATCH"])
    a.add_argument("--confirm", action="store_true")
    r = sub.add_parser("restore")
    r.add_argument("--target", required=True)
    r.add_argument("--file", required=True)
    r.add_argument("--confirm", action="store_true")
    args = p.parse_args()

    user, pw = _creds()
    out = []
    for ip in resolve(args.target):
        h = login(ip, user, pw)
        if args.cmd == "status":
            out.append({"ip": ip, "device": api_get(ip, h, "sys/device-info"),
                        "radios": api_get(ip, h, "wireless/radiostatus"),
                        "vlans": api_get(ip, h, "wireless/vlans")})
        elif args.cmd == "backup":
            out.append(do_backup(ip, h))
        elif args.cmd == "get":
            out.append({"ip": ip, "endpoint": args.endpoint, "data": redact(api_get(ip, h, args.endpoint))})
        elif args.cmd == "list-endpoints":
            out.append({"ip": ip, "snapshot_endpoints": SNAPSHOT_ENDPOINTS})
        elif args.cmd == "apply":
            if not args.confirm:
                sys.exit("Error: --confirm required to apply live AP changes.")
            if args.target.lower() == "all":
                sys.exit("Error: apply one AP at a time.")
            bk = do_backup(ip, h, tag="pre-apply-" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
            body = json.load(open(args.payload_file))
            resp = requests.request(args.method, f"https://{ip}/api/gui/{args.endpoint}", headers=h,
                                    json=body, verify=False, timeout=30)
            ap = requests.post(f"https://{ip}/api/gui/sys/apply", headers=h, json={}, verify=False, timeout=60)
            out.append({"ip": ip, "pre_apply_backup": bk, "write_status": resp.status_code,
                        "write_body": redact(resp.text[:500]), "apply_status": ap.status_code})
        elif args.cmd == "restore":
            if not args.confirm:
                sys.exit("Error: --confirm required to restore AP config (device will reboot/reload).")
            if args.target.lower() == "all":
                sys.exit("Error: restore one AP at a time.")
            with open(args.file, "rb") as f:
                resp = requests.post(f"https://{ip}/api/uploadCFG", headers=h,
                                     files={"file": ("uploadFile.des3", f.read())}, verify=False, timeout=60)
            out.append({"ip": ip, "http_status": resp.status_code, "body": resp.text[:500]})
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
