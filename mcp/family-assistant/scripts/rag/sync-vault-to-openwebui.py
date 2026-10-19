#!/usr/bin/env python3
"""
sync-vault-to-openwebui.py
==========================
Synchronizes Obsidian Vault notes and Paprika recipes into Open WebUI Knowledge collections.
Uses local embeddings (nomic-embed-text via Ollama on CT 104) for fast, zero-cloud semantic RAG.

Usage:
    .venv/bin/python3 sync-vault-to-openwebui.py [--vault-dir PATH] [--api-key KEY] [--dry-run]
"""

import os
import sys
import glob
import json
import time
import argparse
import urllib.request
import urllib.parse
import mimetypes

DEFAULT_VAULT_DIR = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/dtheurer/Obsidian/Vault/Personal"
)
DEFAULT_OPENWEBUI_URL = os.environ.get(
    "OPENWEBUI_URL",
    "http://192.168.40.246:3000"
)
CONFIG_FILE = os.path.expanduser("~/.config/homelab-todo/openwebui.json")


def load_openwebui_config():
    api_key = os.environ.get("OPENWEBUI_API_KEY")
    base_url = DEFAULT_OPENWEBUI_URL

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                api_key = api_key or cfg.get("api_key")
                base_url = cfg.get("base_url") or base_url
        except Exception as e:
            print(f"⚠️ Error reading {CONFIG_FILE}: {e}")

    return base_url.rstrip("/"), api_key


def api_request(base_url, endpoint, api_key, method="GET", data=None, files=None):
    url = f"{base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}"}

    if files:
        # Multipart form upload
        import uuid
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body = []
        for field_name, (filename, file_bytes, mime) in files.items():
            body.append(f"--{boundary}".encode("utf-8"))
            body.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode("utf-8"))
            body.append(f"Content-Type: {mime}\r\n".encode("utf-8"))
            body.append(file_bytes)
        body.append(f"--{boundary}--\r\n".encode("utf-8"))
        payload = b"\r\n".join(body)
    elif data is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(data).encode("utf-8")
    else:
        payload = None

    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            resp_body = res.read().decode("utf-8")
            return json.loads(resp_body) if resp_body.strip() else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"HTTP {e.code} on {endpoint}: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Request failed on {endpoint}: {e}")


def get_or_create_knowledge_base(base_url, api_key, name, description):
    # List existing knowledge bases
    res = api_request(base_url, "/api/v1/knowledge/", api_key, method="GET")
    kb_list = res.get("items", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])
    for kb in kb_list:
        if isinstance(kb, dict) and kb.get("name") == name:
            return kb.get("id")

    # Create new
    payload = {
        "name": name,
        "description": description
    }
    created = api_request(base_url, "/api/v1/knowledge/create", api_key, method="POST", data=payload)
    return created.get("id")


def get_knowledge_files(base_url, api_key, kb_id):
    try:
        kb_info = api_request(base_url, f"/api/v1/knowledge/{kb_id}", api_key, method="GET")
        files = kb_info.get("files", [])
        return {f.get("meta", {}).get("name") or f.get("filename"): f.get("id") for f in files}
    except Exception:
        return {}


def upload_and_attach_file(base_url, api_key, kb_id, file_path):
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    files = {
        "file": (filename, file_bytes, "text/markdown")
    }

    uploaded = api_request(base_url, "/api/v1/files/", api_key, method="POST", files=files)
    file_id = uploaded.get("id")
    if not file_id:
        raise RuntimeError(f"Upload did not return a valid file ID for {filename}")

    # Wait briefly for processing
    for _ in range(15):
        try:
            status_data = api_request(base_url, f"/api/v1/files/{file_id}/process/status", api_key, method="GET")
            if status_data.get("status") == "completed":
                break
        except Exception:
            pass
        time.sleep(1)

    # Attach to knowledge base
    api_request(base_url, f"/api/v1/knowledge/{kb_id}/file/add", api_key, method="POST", data={"file_id": file_id})
    return file_id


def sync_knowledge_collection(base_url, api_key, kb_name, kb_desc, file_paths, dry_run=False):
    print(f"\n📚 Synchronizing Knowledge Base: '{kb_name}' ({len(file_paths)} candidate files)...")
    if dry_run:
        print(f"  [DRY-RUN] Would sync {len(file_paths)} files to '{kb_name}'.")
        for p in file_paths[:5]:
            print(f"   • {os.path.basename(p)}")
        return

    kb_id = get_or_create_knowledge_base(base_url, api_key, kb_name, kb_desc)
    existing_files = get_knowledge_files(base_url, api_key, kb_id)
    print(f"  Connected to Knowledge Base ID: {kb_id} (currently has {len(existing_files)} files)")

    uploaded_count = 0
    for path in file_paths:
        fname = os.path.basename(path)
        if fname in existing_files:
            continue
        try:
            print(f"  ⬆️ Uploading & indexing {fname}...")
            upload_and_attach_file(base_url, api_key, kb_id, path)
            uploaded_count += 1
        except Exception as e:
            print(f"  ⚠️ Error indexing {fname}: {e}")

    print(f"  ✅ Completed '{kb_name}': {uploaded_count} new files indexed.")


def main():
    parser = argparse.ArgumentParser(description="Sync Obsidian Vault & Recipes to Open WebUI Knowledge Bases")
    parser.add_argument("--vault-dir", default=DEFAULT_VAULT_DIR, help="Obsidian Vault path")
    parser.add_argument("--api-key", default=None, help="Open WebUI API Key")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without uploading")
    args = parser.parse_args()

    base_url, api_key = load_openwebui_config()
    api_key = args.api_key or api_key

    if not api_key and not args.dry_run:
        print("❌ Error: Open WebUI API Key not found.")
        print(f"   Please save it in {CONFIG_FILE} as: {{\"api_key\": \"your_api_key\"}}")
        print("   Or pass it via --api-key <KEY> or OPENWEBUI_API_KEY environment variable.")
        print("   (Generate your key in Open WebUI: Settings -> Account -> API Keys)")
        sys.exit(1)

    print(f"🤖 Open WebUI Endpoint: {base_url}")
    print(f"📂 Vault Directory: {args.vault_dir}")

    # 1. Family Recipes Collection
    recipes_glob = os.path.join(args.vault_dir, "Recipes", "*.md")
    recipe_files = sorted(glob.glob(recipes_glob))
    sync_knowledge_collection(
        base_url, api_key,
        kb_name="Family Recipes",
        kb_desc="Private Paprika recipe collection with ingredients, cooking instructions, and ratings.",
        file_paths=recipe_files,
        dry_run=args.dry_run
    )

    # 2. Home & Maintenance Collection
    maint_glob = os.path.join(args.vault_dir, "Maintenance", "*.md")
    maint_files = sorted(glob.glob(maint_glob))
    sync_knowledge_collection(
        base_url, api_key,
        kb_name="Home & Maintenance",
        kb_desc="Home maintenance logs, seasonal checklists, service dates, and equipment manuals.",
        file_paths=maint_files,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
