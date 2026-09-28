#!/usr/bin/env python3
"""
Automated Portainer Stack Adoption Tool
Adopts CLI-created Docker Compose stacks (like telemetry-agent or 71-monitoring)
into Portainer's internal database via the Portainer REST API.
Unlocks the Portainer Web Editor with ZERO container restarts or downtime.
"""

import argparse
import getpass
import json
import os
import ssl
import sys
import urllib.request
import urllib.error

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

KNOWN_PORTAINER_INSTANCES = [
    {
        "name": "media-server",
        "url": "https://media.secure.theurer.dev",
        "local_ip": "192.168.40.247",
        "stacks": ["telemetry-agent"]
    },
    {
        "name": "luna-server",
        "url": "https://luna.secure.theurer.dev",
        "local_ip": "192.168.40.249",
        "stacks": ["telemetry-agent"]
    },
    {
        "name": "nexus-server2",
        "url": "https://nexus2.secure.theurer.dev",
        "local_ip": "192.168.40.186",
        "stacks": ["telemetry-agent"]
    },
    {
        "name": "minecraft-docker",
        "url": "https://minecraft.secure.theurer.dev",
        "local_ip": "192.168.40.175",
        "stacks": ["telemetry-agent"]
    },
    {
        "name": "nexus-server",
        "url": "https://nexus.secure.theurer.dev",
        "local_ip": "192.168.40.185",
        "stacks": ["71-monitoring"]
    },
]

def get_compose_content(stack_name):
    """Retrieve compose file content from repository for the stack."""
    if stack_name == "telemetry-agent":
        compose_path = os.path.join(REPO_ROOT, "infrastructure", "docker-stacks", "_shared", "telemetry-pod", "docker-compose.yml")
    elif stack_name == "71-monitoring":
        compose_path = os.path.join(REPO_ROOT, "infrastructure", "docker-stacks", "nexus-server", "71-monitoring", "docker-compose.yml")
    else:
        raise ValueError(f"Unknown stack name: {stack_name}")

    if not os.path.exists(compose_path):
        raise FileNotFoundError(f"Compose file not found at: {compose_path}")

    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    # For telemetry-agent, ensure absolute path is used for promtail config so Portainer resolves it
    if stack_name == "telemetry-agent":
        content = content.replace("./promtail.yml:", "/home/meek2100/docker/telemetry-agent/promtail.yml:")

    return content

def make_request(url, method="GET", headers=None, data=None, insecure=True):
    """Make an HTTP/HTTPS request with SSL verification bypass for internal self-signed certs."""
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req_headers = headers or {}
    req_data = None
    if data is not None:
        req_headers["Content-Type"] = "application/json"
        req_data = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(body)
            return e.code, err_json
        except Exception:
            return e.code, {"message": body or str(e)}
    except Exception as e:
        return 0, {"message": str(e)}

def authenticate(base_url, username, password):
    """Obtain JWT token from Portainer."""
    url = f"{base_url.rstrip('/')}/api/auth"
    status, res = make_request(url, method="POST", data={"username": username, "password": password})
    if status == 200 and "jwt" in res:
        return res["jwt"]
    raise RuntimeError(f"Authentication failed: {res.get('message', res.get('details', status))}")

def get_endpoint_id(base_url, token):
    """Retrieve the primary Docker environment/endpoint ID."""
    url = f"{base_url.rstrip('/')}/api/endpoints"
    headers = {"Authorization": f"Bearer {token}"}
    status, res = make_request(url, headers=headers)
    if status == 200 and isinstance(res, list) and len(res) > 0:
        return res[0]["Id"]
    raise RuntimeError(f"Failed to retrieve endpoints: {res}")

def get_existing_stacks(base_url, token):
    """List all stacks currently tracked in Portainer."""
    url = f"{base_url.rstrip('/')}/api/stacks"
    headers = {"Authorization": f"Bearer {token}"}
    status, res = make_request(url, headers=headers)
    if status == 200 and isinstance(res, list):
        return {s["Name"]: s["Id"] for s in res}
    return {}

def adopt_stack(base_url, token, endpoint_id, stack_name, compose_content):
    """Create the standalone stack in Portainer DB."""
    url = f"{base_url.rstrip('/')}/api/stacks/create/standalone/string?endpointId={endpoint_id}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "name": stack_name,
        "stackFileContent": compose_content,
        "env": []
    }
    status, res = make_request(url, method="POST", headers=headers, data=payload)
    if status in (200, 201) and "Id" in res:
        return res["Id"]
    raise RuntimeError(f"Portainer stack creation failed (HTTP {status}): {res.get('message', res.get('details', res))}")

def process_instance(instance, username, password, stack_filter=None):
    name = instance["name"]
    url = instance["url"]
    print(f"\n==================================================")
    print(f"🔗 Processing Portainer on: {name} ({url})")
    print(f"==================================================")

    try:
        token = authenticate(url, username, password)
        print("  ✓ Authenticated successfully")
    except Exception as e:
        print(f"  ❌ Failed connecting/authenticating to {url}: {e}")
        return False

    try:
        endpoint_id = get_endpoint_id(url, token)
        print(f"  ✓ Connected to Docker Environment (Endpoint ID: {endpoint_id})")
    except Exception as e:
        print(f"  ❌ Failed finding endpoint: {e}")
        return False

    existing_stacks = get_existing_stacks(url, token)
    stacks_to_adopt = instance["stacks"]
    if stack_filter:
        stacks_to_adopt = [s for s in stacks_to_adopt if s == stack_filter]

    success = True
    for stack_name in stacks_to_adopt:
        if stack_name in existing_stacks:
            print(f"  ℹ️ Stack '{stack_name}' is ALREADY adopted in Portainer (Stack ID: {existing_stacks[stack_name]}).")
            continue

        print(f"  ⏳ Adopting stack '{stack_name}' into Portainer...")
        try:
            compose_content = get_compose_content(stack_name)
            new_id = adopt_stack(url, token, endpoint_id, stack_name, compose_content)
            print(f"  🎉 SUCCESS: Stack '{stack_name}' adopted! Assigned Portainer Stack ID: {new_id}")
            print(f"     Web Editor is now UNLOCKED with zero container downtime.")
        except Exception as e:
            print(f"  ❌ Failed adopting stack '{stack_name}': {e}")
            success = False

    return success

def main():
    parser = argparse.ArgumentParser(description="Adopt CLI Docker Compose stacks into Portainer Web UI")
    parser.add_argument("--url", help="Target Portainer base URL (e.g. https://media.secure.theurer.dev)")
    parser.add_argument("--stack", help="Stack name to adopt (e.g. telemetry-agent or 71-monitoring)")
    parser.add_argument("--all", action="store_true", help="Adopt telemetry-agent across all fleet Portainer instances")
    parser.add_argument("-u", "--user", default="admin", help="Portainer admin username (default: admin)")
    parser.add_argument("-p", "--password", help="Portainer admin password (or prompt if omitted)")

    args = parser.parse_args()

    password = args.password or os.environ.get("PORTAINER_PASSWORD")
    if not password:
        password = getpass.getpass(f"Enter Portainer password for '{args.user}': ")

    if args.url:
        target_name = args.url.split("//")[-1].split(".")[0]
        stack_name = args.stack or "telemetry-agent"
        instance = {
            "name": target_name,
            "url": args.url,
            "stacks": [stack_name]
        }
        process_instance(instance, args.user, password, stack_filter=args.stack)
    else:
        print("🚀 Starting Fleet-Wide Portainer Stack Adoption...")
        for inst in KNOWN_PORTAINER_INSTANCES:
            process_instance(inst, args.user, password, stack_filter=args.stack)

if __name__ == "__main__":
    main()
