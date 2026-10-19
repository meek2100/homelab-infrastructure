#!/usr/bin/env python3
"""
Master Portainer & Docker Stack Index Generator
Scans infrastructure/docker-stacks/ to generate infrastructure/docker-stacks/STACK-INDEX.md
"""

import os
import glob
import json
import re
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
STACKS_DIR = os.path.join(REPO_ROOT, "infrastructure", "docker-stacks")
OUTPUT_INDEX = os.path.join(STACKS_DIR, "STACK-INDEX.md")

def parse_compose_file(compose_path):
    services_info = []
    if not os.path.exists(compose_path):
        return services_info

    try:
        with open(compose_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return services_info

        services = data.get("services", {})
        if not isinstance(services, dict):
            return services_info

        for svc_name, svc_cfg in services.items():
            if not isinstance(svc_cfg, dict):
                continue
            image = svc_cfg.get("image", "custom-build")
            ports_raw = svc_cfg.get("ports", [])
            ports = []
            if isinstance(ports_raw, list):
                for p in ports_raw:
                    if isinstance(p, (str, int)):
                        ports.append(str(p))
                    elif isinstance(p, dict):
                        target = p.get("target")
                        published = p.get("published", target)
                        ports.append(f"{published}:{target}")

            services_info.append({
                "service": svc_name,
                "image": image,
                "ports": ", ".join(ports) if ports else "Internal / Host"
            })
    except Exception as e:
        # Fallback to basic regex if YAML fails
        try:
            with open(compose_path, 'r', encoding='utf-8') as f:
                content = f.read()
            svc_matches = re.findall(r'^\s\s([a-zA-Z0-9_-]+):\s*$', content, re.MULTILINE)
            img_matches = re.findall(r'image:\s*([^\s]+)', content)
            for i, s in enumerate(svc_matches):
                img = img_matches[i] if i < len(img_matches) else "unknown"
                services_info.append({
                    "service": s,
                    "image": img,
                    "ports": "N/A"
                })
        except Exception:
            pass

    return services_info

def generate_index():
    stack_dirs = sorted(glob.glob(os.path.join(STACKS_DIR, "*", "*")))
    valid_stacks = []

    for s_dir in stack_dirs:
        deploy_json = os.path.join(s_dir, "deploy.json")
        compose_yml = os.path.join(s_dir, "docker-compose.yml")
        if not os.path.exists(deploy_json) or not os.path.exists(compose_yml):
            continue

        vm_name = os.path.basename(os.path.dirname(s_dir))
        stack_id = os.path.basename(s_dir)

        with open(deploy_json, 'r') as f:
            deploy_info = json.load(f)

        has_secrets = os.path.exists(os.path.join(s_dir, "secrets.enc.yaml"))
        services = parse_compose_file(compose_yml)

        valid_stacks.append({
            "vm_name": vm_name,
            "stack_id": stack_id,
            "node": deploy_info.get("node", "unknown"),
            "vmid": deploy_info.get("vmid", "unknown"),
            "has_secrets": has_secrets,
            "services": services
        })

    # Group by VM
    vm_groups = {}
    for s in valid_stacks:
        vm = s["vm_name"]
        if vm not in vm_groups:
            vm_groups[vm] = []
        vm_groups[vm].append(s)

    total_stacks = len(valid_stacks)
    total_services = sum(len(s["services"]) for s in valid_stacks)
    total_with_secrets = sum(1 for s in valid_stacks if s["has_secrets"])

    lines = [
        "# Master Portainer & Docker Stack Index",
        "",
        "This document provides a searchable, friendly service catalog mapping every Portainer stack ID across all virtual machines to its application name, container images, exposed ports, host node, and SOPS secret encryption status.",
        "",
        "## Summary Metrics",
        f"- **Total Stacks Cataloged**: {total_stacks}",
        f"- **Total Docker Services Defined**: {total_services}",
        f"- **Stacks with Encrypted Secrets (`secrets.enc.yaml`)**: {total_with_secrets}",
        f"- **Host Virtual Machines**: {len(vm_groups)} (`" + "`, `".join(sorted(vm_groups.keys())) + "`)",
        "",
        "---",
        ""
    ]

    for vm_name in sorted(vm_groups.keys()):
        stacks = vm_groups[vm_name]
        node = stacks[0]["node"]
        vmid = stacks[0]["vmid"]

        lines.append(f"## VM: `{vm_name}` (Node: `{node}`, VMID: `{vmid}`)")
        lines.append(f"Total Stacks: **{len(stacks)}**\n")
        lines.append("| Stack ID | Primary Services | Container Images | Exposed Ports | Encrypted Secrets | Blueprint Path |")
        lines.append("| :--- | :--- | :--- | :--- | :---: | :--- |")

        for s in sorted(stacks, key=lambda x: (0, int(x["stack_id"])) if x["stack_id"].isdigit() else (1, str(x["stack_id"]))):
            s_id = s["stack_id"]
            svc_names = "<br>".join(f"`{x['service']}`" for x in s["services"]) if s["services"] else "`custom`"
            images = "<br>".join(f"`{x['image']}`" for x in s["services"]) if s["services"] else "`unknown`"
            ports = "<br>".join(f"`{x['ports']}`" for x in s["services"]) if s["services"] else "`none`"
            sec_icon = "🔒 Yes" if s["has_secrets"] else "— None"
            rel_path = f"[{vm_name}/{s_id}](file://{os.path.join(STACKS_DIR, vm_name, s_id)})"

            lines.append(f"| **{s_id}** | {svc_names} | {images} | {ports} | {sec_icon} | {rel_path} |")

        lines.append("\n---\n")

    with open(OUTPUT_INDEX, 'w', encoding='utf-8') as out_f:
        out_f.write("\n".join(lines).strip() + "\n")

    print(f"✅ Generated STACK-INDEX.md with {total_stacks} stacks and {total_services} services at {OUTPUT_INDEX}")

if __name__ == "__main__":
    generate_index()
