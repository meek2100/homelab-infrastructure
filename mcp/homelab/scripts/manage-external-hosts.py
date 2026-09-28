#!/usr/bin/env python3
"""
External Hosts Lifecycle & Zero-Trust Management Driver
Manages backup, audit, security monitoring (Fail2Ban/UFW), and GitOps configuration restore
for external cloud servers:
  - web-server (theurer.dev / 146.235.203.133)
  - email-server (mail.theurer.dev / 35.212.229.212)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

HOST_PROFILES = {
    "web": {
        "name": "web-server",
        "fqdn": "theurer.dev",
        "ip": "146.235.203.133",
        "user": "meek2100",
        "key_path": os.path.expanduser("~/.ssh/free-main-server_id_ed25519"),
        "fallback_key": os.path.expanduser("~/.ssh/id_ed25519"),
        "dest_dir": os.path.join(REPO_ROOT, "infrastructure", "external-hosts", "web-server")
    },
    "email": {
        "name": "email-server",
        "fqdn": "mail.theurer.dev",
        "ip": "35.212.229.212",
        "user": "meek2100",
        "key_path": os.path.expanduser("~/.ssh/free-email-server_id_ed25519"),
        "fallback_key": os.path.expanduser("~/.ssh/id_ed25519"),
        "dest_dir": os.path.join(REPO_ROOT, "infrastructure", "external-hosts", "email-server")
    }
}

def resolve_key(profile: dict) -> str:
    if os.path.exists(profile["key_path"]):
        return profile["key_path"]
    if os.path.exists(profile["fallback_key"]):
        return profile["fallback_key"]
    return ""

def run_remote_ssh(profile: dict, remote_cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    key = resolve_key(profile)
    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key:
        ssh_cmd.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    ssh_cmd.extend([f"{profile['user']}@{profile['ip']}", remote_cmd])
    try:
        res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"SSH connection to {profile['name']} ({profile['ip']}) timed out"
    except Exception as e:
        return 1, "", str(e)

def run_remote_script(profile: dict, local_script_path: str, timeout: int = 120) -> tuple[int, str, str]:
    key = resolve_key(profile)
    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key:
        ssh_cmd.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    ssh_cmd.extend([f"{profile['user']}@{profile['ip']}", "bash -s"])
    try:
        with open(local_script_path, "r") as f:
            script_content = f.read()
        res = subprocess.run(ssh_cmd, input=script_content, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Script execution on {profile['name']} timed out"
    except Exception as e:
        return 1, "", str(e)

def scp_fetch(profile: dict, remote_pattern: str, local_dest: str) -> tuple[int, str, str]:
    key = resolve_key(profile)
    os.makedirs(local_dest, exist_ok=True)
    scp_cmd = [
        "scp",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    if key:
        scp_cmd.extend(["-i", key, "-o", "IdentitiesOnly=yes"])
    scp_cmd.extend([f"{profile['user']}@{profile['ip']}:{remote_pattern}", local_dest])
    try:
        res = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=60)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)

def audit_host(target: str) -> dict:
    targets = [target] if target in HOST_PROFILES else ["web", "email"]
    audit_script = os.path.join(REPO_ROOT, "mcp", "homelab", "scripts", "audit-external-host.sh")
    results = {}

    for t in targets:
        p = HOST_PROFILES[t]
        print(f"🔍 Auditing {p['name']} ({p['ip']})...")
        code, out, err = run_remote_script(p, audit_script, timeout=180)
        if code != 0:
            results[p["name"]] = {"status": "error", "code": code, "error": err or out}
            continue
        
        # Download generated bundle
        fetch_code, fetch_out, fetch_err = scp_fetch(p, "/tmp/audit_*.tar.gz", p["dest_dir"])
        if fetch_code != 0:
            results[p["name"]] = {"status": "error_fetching_bundle", "error": fetch_err or fetch_out}
            continue

        # Find newest tarball and extract
        tarballs = [f for f in os.listdir(p["dest_dir"]) if f.startswith("audit_") and f.endswith(".tar.gz")]
        if tarballs:
            newest = sorted(tarballs)[-1]
            archive_path = os.path.join(p["dest_dir"], newest)
            extract_dir = os.path.join(p["dest_dir"], newest.replace(".tar.gz", ""))
            os.makedirs(extract_dir, exist_ok=True)
            subprocess.run(["tar", "-xzf", archive_path, "-C", p["dest_dir"]], check=False)
            results[p["name"]] = {
                "status": "success",
                "bundle": newest,
                "extract_path": extract_dir,
                "output": out.strip()
            }
        else:
            results[p["name"]] = {"status": "success_no_bundle_found", "output": out.strip()}

    return results

def get_security_status(target: str) -> dict:
    targets = [target] if target in HOST_PROFILES else ["web", "email"]
    results = {}

    for t in targets:
        p = HOST_PROFILES[t]
        cmd = """
        echo "=== FAIL2BAN ==="
        if command -v fail2ban-client >/dev/null 2>&1; then
            fail2ban-client status 2>/dev/null || echo "Fail2ban not running or requires permissions"
            for jail in $(fail2ban-client status 2>/dev/null | grep "Jail list:" | sed 's/.*Jail list://' | tr -d ',' | tr '\t' ' '); do
                echo "--- Jail: $jail ---"
                fail2ban-client status "$jail" 2>/dev/null || true
            done
        else
            echo "Fail2Ban not installed"
        fi

        echo "=== UFW FIREWALL ==="
        if command -v ufw >/dev/null 2>&1; then
            ufw status verbose 2>/dev/null || echo "UFW requires root or inactive"
        fi

        echo "=== LISTENING PUBLIC PORTS ==="
        ss -tulpn | grep -E ':22|:80|:443|:25|:587|:993|:110|:995' || true
        """
        code, out, err = run_remote_ssh(p, cmd)
        results[p["name"]] = {
            "status": "online" if code == 0 else "unreachable",
            "code": code,
            "report": out if code == 0 else err
        }
    return results

def backup_host_configs(target: str) -> dict:
    targets = [target] if target in HOST_PROFILES else ["web", "email"]
    results = {}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    for t in targets:
        p = HOST_PROFILES[t]
        backup_dir = os.path.join(p["dest_dir"], "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        if t == "web":
            remote_script = f"""
            BDIR="/tmp/backup_web_{ts}"
            mkdir -p "$BDIR"/{{nginx,fail2ban,php}}
            [ -d /etc/nginx ] && cp -r /etc/nginx "$BDIR"/nginx/ 2>/dev/null || true
            [ -d /etc/fail2ban ] && cp -r /etc/fail2ban "$BDIR"/fail2ban/ 2>/dev/null || true
            [ -d /etc/php ] && cp -r /etc/php "$BDIR"/php/ 2>/dev/null || true
            tar -czf /tmp/backup_web_{ts}.tar.gz -C /tmp "backup_web_{ts}"
            rm -rf "$BDIR"
            echo "BACKUP_FILE=/tmp/backup_web_{ts}.tar.gz"
            """
        else:
            remote_script = f"""
            BDIR="/tmp/backup_email_{ts}"
            mkdir -p "$BDIR"/{{postfix,dovecot,opendkim,fail2ban,roundcube,rspamd}}
            [ -d /etc/postfix ] && cp -r /etc/postfix "$BDIR"/postfix/ 2>/dev/null || true
            [ -d /etc/dovecot ] && cp -r /etc/dovecot "$BDIR"/dovecot/ 2>/dev/null || true
            [ -d /etc/fail2ban ] && cp -r /etc/fail2ban "$BDIR"/fail2ban/ 2>/dev/null || true
            [ -d /etc/roundcube ] && cp -r /etc/roundcube "$BDIR"/roundcube/ 2>/dev/null || true
            [ -d /etc/rspamd ] && cp -r /etc/rspamd "$BDIR"/rspamd/ 2>/dev/null || true
            if [ -d /etc/opendkim ]; then
                cp -r /etc/opendkim "$BDIR"/opendkim/ 2>/dev/null || true
                find "$BDIR"/opendkim -type f -name "*.private" -exec rm -f {{}} + 2>/dev/null || true
            fi
            tar -czf /tmp/backup_email_{ts}.tar.gz -C /tmp "backup_email_{ts}"
            rm -rf "$BDIR"
            echo "BACKUP_FILE=/tmp/backup_email_{ts}.tar.gz"
            """

        code, out, err = run_remote_ssh(p, remote_script, timeout=120)
        if code != 0:
            results[p["name"]] = {"status": "error_creating_backup", "error": err or out}
            continue

        remote_archive = f"/tmp/backup_{t}_{ts}.tar.gz"
        fetch_code, fetch_out, fetch_err = scp_fetch(p, remote_archive, backup_dir)
        if fetch_code == 0:
            results[p["name"]] = {
                "status": "success",
                "archive": os.path.join(backup_dir, f"backup_{t}_{ts}.tar.gz"),
                "timestamp": ts
            }
        else:
            results[p["name"]] = {"status": "error_downloading", "error": fetch_err}

    return results

def main():
    parser = argparse.ArgumentParser(description="External Cloud Hosts Lifecycle Manager")
    parser.add_argument("action", choices=["audit", "backup", "security", "status"], help="Action to perform")
    parser.add_argument("--host", choices=["web", "email", "all"], default="all", help="Target host")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    if args.action == "audit":
        res = audit_host(args.host)
    elif args.action == "backup":
        res = backup_host_configs(args.host)
    elif args.action == "security":
        res = get_security_status(args.host)
    elif args.action == "status":
        res = get_security_status(args.host)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        for host_name, details in res.items():
            print(f"\n{'='*55}\n🖥️  {host_name.upper()}\n{'='*55}")
            if "report" in details:
                print(details["report"])
            elif details.get("status") == "success":
                print(f"✅ Success: {details}")
            else:
                print(f"⚠️ Result: {details}")

if __name__ == "__main__":
    main()
