#!/usr/bin/env python3
"""
Automated Promtail Log Shipper Deployment for External Cloud VPS Instances
Installs and configures Promtail on web-server (theurer.dev) and email-server (mail.theurer.dev)
to stream access, error, mail, and Fail2Ban security logs outward via Cloudflare Tunnel.
"""

import argparse
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

HOST_PROFILES = {
    "web": {
        "name": "web-server",
        "fqdn": "theurer.dev",
        "ip": "146.235.203.133",
        "user": "meek2100",
        "key_path": os.path.expanduser("~/.ssh/free-main-server_id_ed25519"),
        "fallback_key": os.path.expanduser("~/.ssh/id_ed25519"),
    },
    "email": {
        "name": "email-server",
        "fqdn": "mail.theurer.dev",
        "ip": "35.212.229.212",
        "user": "meek2100",
        "key_path": os.path.expanduser("~/.ssh/free-email-server_id_ed25519"),
        "fallback_key": os.path.expanduser("~/.ssh/id_ed25519"),
    }
}

PROMTAIL_VERSION = "3.0.0"
DEFAULT_PUSH_URL = "https://logs.theurer.dev/loki/api/v1/push"

def resolve_key(profile: dict) -> str:
    if os.path.exists(profile["key_path"]):
        return profile["key_path"]
    if os.path.exists(profile["fallback_key"]):
        return profile["fallback_key"]
    return ""

def run_remote_ssh(profile: dict, remote_cmd: str, timeout: int = 120) -> tuple[int, str, str]:
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

def generate_promtail_config(host_key: str, push_url: str, tenant_id: str = "external-cloud-vps", bearer_token: str = "") -> str:
    auth_lines = []
    if tenant_id:
        auth_lines.append(f'    tenant_id: "{tenant_id}"')
    if bearer_token:
        auth_lines.append(f'    bearer_token: "{bearer_token}"')
    auth_block = ("\n" + "\n".join(auth_lines)) if auth_lines else ""

    if host_key == "web":
        return f"""server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/log/promtail-positions.yaml

clients:
  - url: {push_url}{auth_block}

scrape_configs:
  - job_name: nginx-access
    static_configs:
      - targets: [localhost]
        labels:
          job: nginx
          service: web
          stream: access
          host: theurer.dev
          __path__: /var/log/nginx/*access.log

  - job_name: nginx-error
    static_configs:
      - targets: [localhost]
        labels:
          job: nginx
          service: web
          stream: error
          host: theurer.dev
          __path__: /var/log/nginx/*error.log

  - job_name: security-auth
    static_configs:
      - targets: [localhost]
        labels:
          job: security
          service: auth
          host: theurer.dev
          __path__: /var/log/auth.log

  - job_name: security-fail2ban
    static_configs:
      - targets: [localhost]
        labels:
          job: security
          service: fail2ban
          host: theurer.dev
          __path__: /var/log/fail2ban.log
"""
    else:
        return f"""server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/log/promtail-positions.yaml

clients:
  - url: {push_url}{auth_block}

scrape_configs:
  - job_name: mail-logs
    static_configs:
      - targets: [localhost]
        labels:
          job: mail
          service: postfix-dovecot
          host: mail.theurer.dev
          __path__: /var/log/mail.log

  - job_name: roundcube-webmail
    static_configs:
      - targets: [localhost]
        labels:
          job: webmail
          service: roundcube
          host: mail.theurer.dev
          __path__: /var/log/nginx/*access.log

  - job_name: security-auth
    static_configs:
      - targets: [localhost]
        labels:
          job: security
          service: auth
          host: mail.theurer.dev
          __path__: /var/log/auth.log

  - job_name: security-fail2ban
    static_configs:
      - targets: [localhost]
        labels:
          job: security
          service: fail2ban
          host: mail.theurer.dev
          __path__: /var/log/fail2ban.log
"""

def deploy_host(target: str, push_url: str, tenant_id: str = "external-cloud-vps", bearer_token: str = "", dry_run: bool = False) -> dict:
    p = HOST_PROFILES[target]
    config_yaml = generate_promtail_config(target, push_url, tenant_id, bearer_token)

    if dry_run:
        return {
            "status": "dry_run",
            "host": p["name"],
            "target_ip": p["ip"],
            "push_url": push_url,
            "generated_config": config_yaml
        }

    install_script = f"""
    set -e
    echo "📦 Checking Promtail installation on {p['fqdn']}..."
    if ! command -v promtail >/dev/null 2>&1; then
        echo "⬇️ Downloading Promtail v{PROMTAIL_VERSION}..."
        curl -fsSL -o /tmp/promtail.zip "https://github.com/grafana/loki/releases/download/v{PROMTAIL_VERSION}/promtail-linux-amd64.zip"
        if [ -f /tmp/promtail.zip ]; then
            if command -v unzip >/dev/null 2>&1; then
                unzip -o /tmp/promtail.zip -d /tmp/
            else
                python3 -m zipfile -e /tmp/promtail.zip /tmp/
            fi
            sudo mv /tmp/promtail-linux-amd64 /usr/local/bin/promtail
            sudo chmod +x /usr/local/bin/promtail
            rm -f /tmp/promtail*
        fi
    fi

    sudo mkdir -p /etc/promtail
    cat << 'PROMTAIL_CONF' | sudo tee /etc/promtail/promtail.yaml > /dev/null
{config_yaml}
PROMTAIL_CONF

    cat << 'SYSTEMD_UNIT' | sudo tee /etc/systemd/system/promtail.service > /dev/null
[Unit]
Description=Promtail Log Shipper Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/promtail -config.file=/etc/promtail/promtail.yaml
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
SYSTEMD_UNIT

    sudo systemctl daemon-reload
    sudo systemctl enable promtail
    sudo systemctl restart promtail
    systemctl is-active promtail
    """

    code, out, err = run_remote_ssh(p, install_script)
    return {
        "status": "success" if code == 0 else "error",
        "host": p["name"],
        "code": code,
        "output": out.strip(),
        "error": err.strip() if code != 0 else ""
    }

def main():
    parser = argparse.ArgumentParser(description="Deploy Promtail to External Cloud VPS Hosts")
    parser.add_argument("--host", choices=["web", "email", "all"], default="all", help="Target host")
    parser.add_argument("--url", default=DEFAULT_PUSH_URL, help="Loki push endpoint URL")
    parser.add_argument("--tenant-id", default="external-cloud-vps", help="Loki tenant ID for multi-tenant labeling")
    parser.add_argument("--token", default="", help="Optional Bearer authentication token")
    parser.add_argument("--dry-run", action="store_true", help="Generate configuration without applying")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    targets = ["web", "email"] if args.host == "all" else [args.host]
    results = {}
    for t in targets:
        results[t] = deploy_host(t, args.url, args.tenant_id, args.token, args.dry_run)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for t, res in results.items():
            print(f"\n{'='*55}\n🚀 PROMTAIL DEPLOYMENT: {t.upper()}\n{'='*55}")
            if res.get("status") == "dry_run":
                print(f"Target: {res['host']} ({res['target_ip']})")
                print(f"Push URL: {res['push_url']}")
                print("\nConfiguration Preview:\n" + res["generated_config"])
            elif res.get("status") == "success":
                print(f"✅ Promtail successfully deployed and active!")
                print(res.get("output", ""))
            else:
                print(f"⚠️ Deployment failed (exit code {res.get('code')}):")
                print(res.get("error", res.get("output", "")))

if __name__ == "__main__":
    main()
