#!/usr/bin/env python3
"""
Microsoft To Do to Obsidian Vault Mirror Engine
Synchronizes active tasks from Microsoft To Do into static markdown files in the local Obsidian vault.
Zero-cloud privacy: local LLMs read the resulting markdown without authentication tokens or cloud APIs in the loop.
"""

import os
import sys
import json
import argparse
import datetime
import urllib.request
import urllib.error
import msal

DEFAULT_CLIENT_ID = "d3590ed6-52b3-4102-aeff-aad2292ab01c"
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Tasks.ReadWrite"]
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

DEFAULT_VAULT_DIR = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/dtheurer/Obsidian/Vault/Personal"
)
CONFIG_DIR = os.path.expanduser("~/.config/homelab-todo")
CACHE_FILE = os.path.join(CONFIG_DIR, "token_cache.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def get_client_id(cli_client_id=None):
    if cli_client_id:
        return cli_client_id
    if os.environ.get("MS_CLIENT_ID"):
        return os.environ.get("MS_CLIENT_ID")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("client_id"):
                    return cfg.get("client_id")
        except Exception as e:
            print(f"Warning reading {CONFIG_FILE}: {e}")
    return DEFAULT_CLIENT_ID


def load_token_cache():
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache.deserialize(f.read())
    return cache


def save_token_cache(cache):
    if cache.has_state_changed:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(cache.serialize())
        os.chmod(CACHE_FILE, 0o600)


def get_msal_app(cache, client_id=None):
    cid = get_client_id(client_id)
    return msal.PublicClientApplication(
        cid,
        authority=AUTHORITY,
        token_cache=cache
    )


def authenticate_interactive(client_id=None):
    cache = load_token_cache()
    app = get_msal_app(cache, client_id=client_id)
    cid = get_client_id(client_id)

    # Save client_id to config for future background runs
    try:
        os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"client_id": cid}, f, indent=2)
    except Exception as e:
        print(f"Warning writing config: {e}")

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print(f"Error initiating device flow: {flow}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🔑 Microsoft To Do Authentication Required")
    print("=" * 60)
    print(f"1. Open in your browser: {flow['verification_uri']}")
    print(f"2. Enter the code:       {flow['user_code']}")
    print("=" * 60)
    print("Waiting for login approval in your browser...")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        save_token_cache(cache)
        print("✅ Authentication successful! Token saved for background sync.")
        return result["access_token"]
    else:
        print(f"❌ Login failed: {result.get('error_description')}")
        sys.exit(1)


def get_access_token():
    cache = load_token_cache()
    app = get_msal_app(cache)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            save_token_cache(cache)
            return result["access_token"]

    print("⚠️ No valid cached token found. Run with --auth first.")
    return None


def graph_get(access_token, path, params=None):
    import urllib.parse
    url = f"{GRAPH_API_ENDPOINT}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))


def sync_todo_to_vault(vault_dir, dry_run=False):
    token = get_access_token()
    if not token:
        sys.exit(1)

    print("📡 Fetching Microsoft To Do task lists from Microsoft Graph API...")
    lists_data = graph_get(token, "/me/todo/lists")
    lists = lists_data.get("value", [])

    sync_dir = os.path.join(vault_dir, "_Sync")
    if not dry_run:
        os.makedirs(sync_dir, exist_ok=True)

    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    all_summary = [f"# 📋 All Active Tasks (Microsoft To Do Mirror)\n\n*Last synchronized: {timestamp_str}*\n"]

    for t_list in lists:
        list_id = t_list.get("id")
        list_name = t_list.get("displayName", "Tasks")
        print(f"  • Processing list: '{list_name}'...")

        tasks_data = graph_get(token, f"/me/todo/lists/{list_id}/tasks", params={"$filter": "status ne 'completed'"})
        tasks = tasks_data.get("value", [])

        # Slugify list name for file output
        clean_slug = "".join(c if c.isalnum() else "-" for c in list_name.lower()).strip("-")
        clean_slug = "-".join(filter(None, clean_slug.split("-")))
        if "grocer" in clean_slug:
            clean_slug = "groceries"

        out_lines = [
            f"# {list_name} (Mirrored from Microsoft To Do)\n",
            f"*Last synchronized: {timestamp_str}*\n"
        ]

        if not tasks:
            out_lines.append("*No open tasks in this list.*\n")
        else:
            for t in tasks:
                title = t.get("title", "").strip()
                due_info = ""
                due = t.get("dueDateTime")
                if due and isinstance(due, dict) and "dateTime" in due:
                    due_date = due["dateTime"].split("T")[0]
                    due_info = f" (due: {due_date})"

                out_lines.append(f"- [ ] {title}{due_info}")

                # Optional body notes
                body = t.get("body", {})
                if isinstance(body, dict) and body.get("content"):
                    raw_content = body.get("content").strip()
                    if raw_content:
                        for line in raw_content.splitlines():
                            if line.strip():
                                out_lines.append(f"  - {line.strip()}")

        content = "\n".join(out_lines) + "\n"
        all_summary.append(f"\n## {list_name}\n\n" + "\n".join(out_lines[2:]))

        if dry_run:
            print(f"\n--- [DRY-RUN] File: _Sync/todo-{clean_slug}.md ---\n{content}")
        else:
            out_path = os.path.join(sync_dir, f"todo-{clean_slug}.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"    ✓ Written to {out_path} ({len(tasks)} tasks)")

    if not dry_run:
        summary_path = os.path.join(sync_dir, "todo-all.md")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_summary) + "\n")
        print(f"  ✓ Written consolidated tasks to {summary_path}")

    print("\n✅ Microsoft To Do mirror sync complete!")


def main():
    parser = argparse.ArgumentParser(description="Mirror Microsoft To Do lists to Obsidian Vault markdown.")
    parser.add_argument("--auth", action="store_true", help="Perform initial interactive OAuth login via Device Code Flow.")
    parser.add_argument("--client-id", default=None, help="Azure App Registration Application (client) ID.")
    parser.add_argument("--vault-dir", default=DEFAULT_VAULT_DIR, help=f"Path to Obsidian Vault root (default: {DEFAULT_VAULT_DIR})")
    parser.add_argument("--dry-run", action="store_true", help="Print mirrored tasks to console without writing files.")
    args = parser.parse_args()

    if args.auth:
        authenticate_interactive(client_id=args.client_id)
    else:
        sync_todo_to_vault(args.vault_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
