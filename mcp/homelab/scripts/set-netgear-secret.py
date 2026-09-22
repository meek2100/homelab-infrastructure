#!/usr/bin/env python3
"""
Interactive helper to securely store the Netgear GS108Ev2 switch password
into the SOPS-encrypted vault (infrastructure/secrets/araknis-switch.enc.yaml).
"""

import getpass
import json
import os
import shutil
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SECRET_FILE = os.path.join(REPO_ROOT, "infrastructure", "secrets", "araknis-switch.enc.yaml")
SOPS_BIN = shutil.which("sops") or os.path.expanduser("~/.local/bin/sops")
AGE_KEY_FILE = os.path.join(REPO_ROOT, "homelab-infrastructure.key")


def main():
    if not SOPS_BIN or not os.path.exists(SOPS_BIN):
        print(f"[ERROR] sops binary not found: {SOPS_BIN}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(AGE_KEY_FILE):
        print(f"[ERROR] Age key file not found: {AGE_KEY_FILE}", file=sys.stderr)
        sys.exit(1)

    print("=== Netgear Switch Secret Setup ===")
    print(f"Vault: {SECRET_FILE}")
    print("This will encrypt and save the Netgear switch password using your local Age key.\n")

    # Prompt securely without echo
    password = getpass.getpass("Enter Netgear GS108Ev2 switch password: ")
    if not password:
        print("[ERROR] Password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    # Optional IP prompt
    ip_input = input("Enter switch IP [default: 192.168.1.220]: ").strip()
    switch_ip = ip_input if ip_input else "192.168.1.220"

    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = AGE_KEY_FILE

    # Decrypt existing vault
    if os.path.exists(SECRET_FILE):
        res = subprocess.run([SOPS_BIN, "-d", SECRET_FILE], capture_output=True, text=True, env=env)
        if res.returncode != 0:
            print(f"[ERROR] Decryption failed: {res.stderr}", file=sys.stderr)
            sys.exit(1)
        data = yaml.safe_load(res.stdout) if yaml else json.loads(res.stdout)
    else:
        data = {}

    # Update Netgear fields
    data["netgear_switch_ip"] = switch_ip
    data["netgear_password"] = password

    # Convert to YAML or JSON for re-encryption
    plain_text = yaml.dump(data, default_flow_style=False) if yaml else json.dumps(data, indent=2)

    # Encrypt directly back to file
    proc = subprocess.Popen(
        [SOPS_BIN, "-e", "--input-type", "yaml", "--output-type", "yaml", "/dev/stdin"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    enc_out, enc_err = proc.communicate(input=plain_text)
    if proc.returncode != 0:
        print(f"[ERROR] Encryption failed: {enc_err}", file=sys.stderr)
        sys.exit(1)

    with open(SECRET_FILE, "w") as f:
        f.write(enc_out)

    print(f"\n[SUCCESS] Successfully encrypted Netgear credentials into {SECRET_FILE}!")
    print("The credentials are encrypted with age and ready for use by FastMCP tools.\n")


if __name__ == "__main__":
    main()
