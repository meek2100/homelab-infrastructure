#!/usr/bin/env python3
"""
Microsoft To Do Task Management CLI
Provides programmatic task addition, completion, and list querying for Microsoft Graph API.
Used by local automations, Open WebUI tools, and Obsidian outbox processors.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
from datetime import datetime

CONFIG_DIR = os.path.expanduser("~/.config/homelab-todo")
CACHE_FILE = os.path.join(CONFIG_DIR, "token_cache.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
GRAPH_URL = "https://graph.microsoft.com/v1.0"


def get_credentials():
    if not os.path.exists(CONFIG_FILE) or not os.path.exists(CACHE_FILE):
        print("❌ Error: Microsoft To Do credentials not found in ~/.config/homelab-todo/")
        print("Run 'sync-todo-to-vault.py --auth' first.")
        sys.exit(1)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        client_id = json.load(f).get("client_id")

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)

    rts = cache.get("RefreshToken", {})
    if not rts:
        print("❌ Error: No refresh token found in token cache.")
        sys.exit(1)

    refresh_token = list(rts.values())[0].get("secret")
    return client_id, refresh_token


def get_fresh_access_token():
    client_id, refresh_token = get_credentials()
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "Tasks.ReadWrite offline_access"
    }).encode("utf-8")

    req = urllib.request.Request(TOKEN_URL, data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            return res_data["access_token"]
    except Exception as e:
        print(f"❌ Error refreshing access token: {e}")
        sys.exit(1)


def get_lists(access_token):
    req = urllib.request.Request(
        f"{GRAPH_URL}/me/todo/lists",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data.get("value", [])


def match_list(lists, query):
    if not query:
        # Default to Groceries if available, else first list
        for l in lists:
            if "grocer" in l.get("displayName", "").lower():
                return l
        return lists[0] if lists else None

    query_lower = query.lower().strip()
    # Exact match
    for l in lists:
        if l.get("displayName", "").lower() == query_lower:
            return l

    # Substring match
    for l in lists:
        if query_lower in l.get("displayName", "").lower():
            return l

    return None


def add_task(title, list_query=None, due_date=None, notes=None):
    token = get_fresh_access_token()
    lists = get_lists(token)
    target_list = match_list(lists, list_query)

    if not target_list:
        print(f"❌ Error: Could not find list matching '{list_query}'.")
        sys.exit(1)

    payload = {"title": title}
    if due_date:
        payload["dueDateTime"] = {
            "dateTime": f"{due_date}T00:00:00Z",
            "timeZone": "UTC"
        }
    if notes:
        payload["body"] = {
            "content": notes,
            "contentType": "text"
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{GRAPH_URL}/me/todo/lists/{target_list['id']}/tasks",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=15) as res:
        created = json.loads(res.read().decode("utf-8"))
        due_str = f" (Due: {due_date})" if due_date else ""
        print(f"✅ Added '{title}'{due_str} to list '{target_list['displayName']}'!")
        return created


def complete_task(title_query, list_query=None):
    token = get_fresh_access_token()
    lists = get_lists(token)
    target_list = match_list(lists, list_query)

    if not target_list:
        print(f"❌ Error: Could not find list matching '{list_query}'.")
        sys.exit(1)

    # Get active tasks in list
    encoded_filter = urllib.parse.quote("status ne 'completed'")
    req = urllib.request.Request(
        f"{GRAPH_URL}/me/todo/lists/{target_list['id']}/tasks?$filter={encoded_filter}",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        tasks = json.loads(res.read().decode("utf-8")).get("value", [])

    q = title_query.lower()
    matched_task = None
    for t in tasks:
        if q in t.get("title", "").lower():
            matched_task = t
            break

    if not matched_task:
        print(f"⚠️ No active task found in '{target_list['displayName']}' matching '{title_query}'.")
        return None

    patch_data = json.dumps({"status": "completed"}).encode("utf-8")
    patch_req = urllib.request.Request(
        f"{GRAPH_URL}/me/todo/lists/{target_list['id']}/tasks/{matched_task['id']}",
        data=patch_data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PATCH"
    )
    with urllib.request.urlopen(patch_req, timeout=15) as res:
        print(f"✅ Marked '{matched_task['title']}' as completed in '{target_list['displayName']}'!")
        return matched_task


def list_all():
    token = get_fresh_access_token()
    lists = get_lists(token)
    print("📋 Available Microsoft To Do Lists:")
    for l in lists:
        print(f"  • {l['displayName']}")


def main():
    parser = argparse.ArgumentParser(description="Manage Microsoft To Do tasks from command line.")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # add
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Title of task or grocery item")
    add_parser.add_argument("--list", "-l", default="Home - Groceries", help="Target list name or keyword")
    add_parser.add_argument("--due", "-d", default=None, help="Due date (YYYY-MM-DD)")
    add_parser.add_argument("--notes", "-n", default=None, help="Optional task notes")

    # complete
    comp_parser = subparsers.add_parser("complete", help="Complete an existing task")
    comp_parser.add_argument("title", help="Search title of task to complete")
    comp_parser.add_argument("--list", "-l", default=None, help="Target list name or keyword")

    # list
    subparsers.add_parser("lists", help="List all available task lists")

    args = parser.parse_args()

    if args.command == "add":
        add_task(args.title, list_query=args.list, due_date=args.due, notes=args.notes)
    elif args.command == "complete":
        complete_task(args.title, list_query=args.list)
    elif args.command == "lists":
        list_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
