#!/usr/bin/env python3
"""
External Services Diagnostic & Zero-Trust Verification Tool
Audits theurer.dev web and mail.theurer.dev mail infrastructure without requiring elevated
internal credentials or compromising network security boundaries.
"""

import argparse
import json
import ssl
import socket
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

TARGETS = {
    "web": {
        "host": "theurer.dev",
        "url": "https://theurer.dev",
        "port": 443,
    },
    "mail": {
        "host": "mail.theurer.dev",
        "url": "https://mail.theurer.dev",
        "smtp_port": 587,
        "imaps_port": 993,
        "https_port": 443,
    }
}

def get_ssl_expiry(hostname, port=443, timeout=5):
    """Retrieve SSL/TLS certificate expiration date and days remaining."""
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                expiry_str = cert['notAfter']
                # Format: 'Nov 24 18:17:50 2026 GMT'
                expiry_dt = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                now_dt = datetime.now(timezone.utc)
                days_remaining = (expiry_dt - now_dt).total_seconds() / 86400.0
                return {
                    "valid": True,
                    "subject": dict(x[0] for x in cert.get('subject', [])),
                    "issuer": dict(x[0] for x in cert.get('issuer', [])),
                    "expires_at": expiry_dt.isoformat(),
                    "days_remaining": round(days_remaining, 1),
                    "expired": days_remaining <= 0
                }
    except Exception as e:
        return {"valid": False, "error": str(e), "days_remaining": 0, "expired": True}

def probe_http(url, timeout=5):
    """Probe HTTP/HTTPS endpoint for status code, latency, and headers."""
    t0 = time.time()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Homelab-Observability-Agent/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = (time.time() - t0) * 1000.0
            return {
                "status_code": resp.status,
                "latency_ms": round(latency, 2),
                "server": resp.headers.get("Server", "Unknown"),
                "healthy": resp.status < 400
            }
    except urllib.error.HTTPError as e:
        latency = (time.time() - t0) * 1000.0
        return {
            "status_code": e.code,
            "latency_ms": round(latency, 2),
            "server": e.headers.get("Server", "Unknown"),
            "healthy": False,
            "error": str(e)
        }
    except Exception as e:
        latency = (time.time() - t0) * 1000.0
        return {
            "status_code": 0,
            "latency_ms": round(latency, 2),
            "healthy": False,
            "error": str(e)
        }

def probe_tcp_banner(hostname, port, timeout=5):
    """Test TCP handshake and retrieve initial service greeting banner."""
    t0 = time.time()
    try:
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            latency = (time.time() - t0) * 1000.0
            sock.settimeout(2.0)
            banner = ""
            try:
                banner = sock.recv(1024).decode('utf-8', errors='replace').strip()
            except socket.timeout:
                pass
            return {
                "reachable": True,
                "latency_ms": round(latency, 2),
                "banner": banner
            }
    except Exception as e:
        return {
            "reachable": False,
            "latency_ms": 0,
            "error": str(e)
        }

def audit_dns():
    """Query standard public DNS records for theurer.dev email and web infrastructure."""
    records = {}
    try:
        # Resolve A records
        for host in ["theurer.dev", "mail.theurer.dev"]:
            try:
                addrs = socket.gethostbyname_ex(host)[2]
                records[host] = {"ip_addresses": addrs, "resolves": True}
            except Exception as e:
                records[host] = {"ip_addresses": [], "resolves": False, "error": str(e)}
    except Exception as e:
        records["error"] = str(e)
    return records

def check_all_services():
    """Perform comprehensive zero-trust health audit of external web and mail servers."""
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "theurer_dev_web": {
            "http": probe_http(TARGETS["web"]["url"]),
            "ssl": get_ssl_expiry(TARGETS["web"]["host"], 443),
        },
        "mail_theurer_dev": {
            "https": probe_http(TARGETS["mail"]["url"]),
            "ssl_https": get_ssl_expiry(TARGETS["mail"]["host"], 443),
            "smtp_submission_587": probe_tcp_banner(TARGETS["mail"]["host"], TARGETS["mail"]["smtp_port"]),
            "imaps_993": probe_tcp_banner(TARGETS["mail"]["host"], TARGETS["mail"]["imaps_port"]),
            "ssl_imaps": get_ssl_expiry(TARGETS["mail"]["host"], TARGETS["mail"]["imaps_port"]),
        },
        "dns": audit_dns()
    }
    return results

def main():
    parser = argparse.ArgumentParser(description="External Services Zero-Trust Diagnostic Tool")
    parser.add_argument("action", choices=["status", "ssl", "mail", "dns"], default="status", nargs="?")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format")
    args = parser.parse_args()

    data = check_all_services()

    if args.json:
        print(json.dumps(data, indent=2))
        return

    if args.action == "status":
        print("\n=======================================================")
        print("🌐 EXTERNAL INFRASTRUCTURE HEALTH STATUS")
        print("=======================================================")
        
        # Web
        w_http = data["theurer_dev_web"]["http"]
        w_ssl = data["theurer_dev_web"]["ssl"]
        w_status = "🟢 HEALTHY" if w_http.get("healthy") and not w_ssl.get("expired") else "🔴 UNHEALTHY"
        print(f"\n1. Web Server (theurer.dev): {w_status}")
        print(f"   - HTTP Response : {w_http.get('status_code')} ({w_http.get('latency_ms')} ms, Server: {w_http.get('server')})")
        print(f"   - TLS / SSL     : Expires in {w_ssl.get('days_remaining')} days ({w_ssl.get('expires_at')})")

        # Mail
        m = data["mail_theurer_dev"]
        m_http = m["https"]
        m_smtp = m["smtp_submission_587"]
        m_imap = m["imaps_993"]
        m_ssl = m["ssl_imaps"]
        m_status = "🟢 HEALTHY" if m_smtp.get("reachable") and m_imap.get("reachable") else "🔴 DEGRADED"
        print(f"\n2. Mail Server (mail.theurer.dev): {m_status}")
        print(f"   - Webmail HTTP  : {m_http.get('status_code')} ({m_http.get('latency_ms')} ms)")
        print(f"   - SMTP (:587)   : {'🟢 Open' if m_smtp.get('reachable') else '🔴 Closed'} ({m_smtp.get('latency_ms')} ms) -> Banner: {m_smtp.get('banner', 'N/A')}")
        print(f"   - IMAPS (:993)  : {'🟢 Open' if m_imap.get('reachable') else '🔴 Closed'} ({m_imap.get('latency_ms')} ms)")
        print(f"   - Mail TLS Cert : Expires in {m_ssl.get('days_remaining')} days ({m_ssl.get('expires_at')})")

        # DNS
        print(f"\n3. Public DNS Resolution:")
        for host, info in data["dns"].items():
            if host == "error": continue
            ips = ", ".join(info.get("ip_addresses", []))
            print(f"   - {host:<20} -> {ips}")
        print("\n=======================================================\n")

    elif args.action == "ssl":
        print("\n🔒 SSL / TLS CERTIFICATE LIFECYCLES")
        print("-------------------------------------------------------")
        for name, host, port in [
            ("Web (theurer.dev)", "theurer.dev", 443),
            ("Webmail (mail.theurer.dev)", "mail.theurer.dev", 443),
            ("IMAPS (mail.theurer.dev)", "mail.theurer.dev", 993),
        ]:
            cert = get_ssl_expiry(host, port)
            print(f"{name:<30}: {cert.get('days_remaining', 0)} days remaining ({cert.get('expires_at', 'Failed')})")
        print("-------------------------------------------------------\n")

    elif args.action == "mail":
        m = data["mail_theurer_dev"]
        print("\n📧 EMAIL PIPELINE DIAGNOSTIC")
        print(f"SMTP Submission (587): {m['smtp_submission_587']}")
        print(f"IMAPS (993)          : {m['imaps_993']}")
        print(f"Webmail / HTTPS      : {m['https']}\n")

    elif args.action == "dns":
        print(json.dumps(data["dns"], indent=2))

if __name__ == "__main__":
    main()
