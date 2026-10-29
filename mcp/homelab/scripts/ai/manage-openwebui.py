#!/usr/bin/env python3
"""
manage-openwebui.py - Manage, synchronize, and inspect Open WebUI tools, models, valves, and chats.
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import glob

def get_config():
    cfg_path = os.path.expanduser("~/.config/homelab-todo/openwebui.json")
    if not os.path.exists(cfg_path):
        print(f"Error: Open WebUI config not found at {cfg_path}", file=sys.stderr)
        sys.exit(1)
    with open(cfg_path) as f:
        return json.load(f)

def api_req(endpoint: str, method: str = "GET", payload: dict = None):
    cfg = get_config()
    base = cfg.get("base_url", "http://192.168.40.246:3000")
    key = cfg.get("api_key")
    url = f"{base}{endpoint}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Authorization": f"Bearer {key}"}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as res:
        content = res.read().decode("utf-8")
        return json.loads(content) if content else {}

def list_tools():
    tools = api_req("/api/v1/tools/")
    print(f"🛠️  Registered Open WebUI Tools ({len(tools)} total):")
    for t in tools:
        t_detail = api_req(f"/api/v1/tools/id/{t['id']}")
        specs = [s.get("name") for s in t_detail.get("specs", [])]
        print(f"  • {t['id']:<35} | Specs: {', '.join(specs)}")

def sync_tools():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    tools_dir = os.path.join(repo_root, "infrastructure", "open-webui", "tools")
    if not os.path.exists(tools_dir):
        print(f"Error: Directory {tools_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    py_files = glob.glob(os.path.join(tools_dir, "*.py"))
    print(f"🔄 Synchronizing {len(py_files)} local tools to Open WebUI...")

    # Load local secret caches for valves
    todo_cache_file = os.path.expanduser("~/.config/homelab-todo/token_cache.json")
    google_token_file = os.path.expanduser("~/.config/homelab-todo/google_token.json")
    
    ms_token = ""
    if os.path.exists(todo_cache_file):
        with open(todo_cache_file) as f:
            c = json.load(f)
            # Find RefreshToken
            for k, v in c.get("RefreshToken", {}).items():
                if v.get("secret"):
                    ms_token = v.get("secret")
                    break

    google_token = ""
    if os.path.exists(google_token_file):
        with open(google_token_file) as f:
            google_token = f.read()

    for fpath in py_files:
        tool_id = os.path.splitext(os.path.basename(fpath))[0]
        # Map filenames to tool IDs if necessary
        if tool_id == "microsoft_todo":
            tool_id = "microsoft_to_do_groceries_manager"
        elif tool_id == "google_calendar":
            tool_id = "google_family_calendar"

        with open(fpath) as f:
            code = f.read()

        # Check if exists
        try:
            existing = api_req(f"/api/v1/tools/id/{tool_id}")
            payload = {
                "id": tool_id,
                "name": existing.get("name", tool_id),
                "content": code,
                "meta": existing.get("meta", {})
            }
            res = api_req(f"/api/v1/tools/id/{tool_id}/update", method="POST", payload=payload)
            print(f"  ✅ Updated '{tool_id}' ({len(res.get('specs', []))} specs)")
        except Exception:
            payload = {
                "id": tool_id,
                "name": tool_id.replace("_", " ").title(),
                "content": code,
                "meta": {"description": f"Tool for {tool_id}"}
            }
            res = api_req("/api/v1/tools/create", method="POST", payload=payload)
            print(f"  ✨ Created '{tool_id}'")

        # Set valves if credentials available
        if tool_id == "microsoft_to_do_groceries_manager" and ms_token:
            valves = {
                "CLIENT_ID": "8edff306-100e-49e9-b523-883a026dc633",
                "REFRESH_TOKEN": ms_token
            }
            api_req(f"/api/v1/tools/id/{tool_id}/valves/update", method="POST", payload=valves)
            print(f"     🔐 Synchronized Microsoft To Do valves")

        if tool_id == "google_family_calendar" and google_token:
            valves = {
                "CALENDAR_ID": "family17480042687465380396@group.calendar.google.com",
                "TOKEN_JSON": google_token,
                "TOKEN_PATH": ""
            }
            api_req(f"/api/v1/tools/id/{tool_id}/valves/update", method="POST", payload=valves)
            print(f"     🔐 Synchronized Google Family Calendar valves")

def deploy_model(model_id: str, base_model: str, system_prompt: str = None, tools: list = None):
    print(f"🚀 Deploying model preset '{model_id}' (base: {base_model})...")
    try:
        existing = api_req(f"/api/v1/models/model?id={model_id}")
    except Exception:
        existing = {
            "id": model_id,
            "name": model_id.replace("-", " ").title(),
            "meta": {},
            "params": {}
        }

    existing["base_model_id"] = base_model
    if tools is not None:
        existing.setdefault("meta", {})["tools"] = tools
        existing["meta"]["toolIds"] = tools
    existing.setdefault("params", {})["function_calling"] = "native"
    if system_prompt:
        existing["params"]["system"] = system_prompt

    api_req("/api/v1/models/model/update", method="POST", payload=existing)
    print(f"✅ Successfully deployed model '{model_id}' with {len(existing['meta'].get('tools', []))} attached tools.")

def inspect_valves(tool_id: str):
    v = api_req(f"/api/v1/tools/id/{tool_id}/valves")
    print(f"🔐 Valves for '{tool_id}':")
    for k, val in v.items():
        masked = f"{val[:10]}... ({len(val)} chars)" if len(str(val)) > 15 else val
        print(f"  • {k}: {masked}")

def list_chats(limit: int = 5):
    chats = api_req("/api/v1/chats/")
    print(f"💬 Recent Chats ({len(chats)} total, showing top {limit}):")
    for c in chats[:limit]:
        print(f"  • ID: {c.get('id')} | Title: {c.get('title')} | Updated: {c.get('updated_at')}")

def get_chat_history(chat_id: str):
    chat = api_req(f"/api/v1/chats/{chat_id}")
    msgs = chat.get("chat", {}).get("history", {}).get("messages", {})
    print(f"📜 Chat Transcript for {chat_id} ({chat.get('chat', {}).get('title')}):")
    for mid, m in msgs.items():
        role = m.get("role", "unknown").upper()
        content = m.get("content", "")
        if content:
            print(f"  [{role}]: {content[:200]}")
        if "output" in m:
            for item in m["output"]:
                if item.get("type") == "function_call":
                    print(f"    ⚙️ Call: {item.get('name')}({item.get('arguments')})")
                elif item.get("type") == "function_call_output":
                    print(f"    📥 Return: {repr(item.get('output'))[:150]}")

def main():
    parser = argparse.ArgumentParser(description="Manage Open WebUI configuration, tools, models, and chat history")
    parser.add_argument("action", choices=["list_tools", "sync_tools", "deploy_model", "inspect_valves", "list_chats", "chat_history"])
    parser.add_argument("--tool-id", type=str, help="Tool ID")
    parser.add_argument("--model-id", type=str, default="family-assistant", help="Model ID")
    parser.add_argument("--base-model", type=str, default="llama3.2:3b", help="Base Ollama model")
    parser.add_argument("--system-prompt", type=str, help="Custom system prompt")
    parser.add_argument("--chat-id", type=str, help="Chat ID for transcript inspection")
    args = parser.parse_args()

    if args.action == "list_tools":
        list_tools()
    elif args.action == "sync_tools":
        sync_tools()
    elif args.action == "inspect_valves":
        if not args.tool_id:
            print("Error: --tool-id required", file=sys.stderr)
            sys.exit(1)
        inspect_valves(args.tool_id)
    elif args.action == "deploy_model":
        deploy_model(args.model_id, args.base_model, args.system_prompt)
    elif args.action == "list_chats":
        list_chats()
    elif args.action == "chat_history":
        if not args.chat_id:
            print("Error: --chat-id required", file=sys.stderr)
            sys.exit(1)
        get_chat_history(args.chat_id)

if __name__ == "__main__":
    main()
