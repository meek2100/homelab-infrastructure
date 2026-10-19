#!/usr/bin/env python3
"""
Personal & Family Second Brain - Local AI Morning Briefing Engine
Reads static markdown tasks from _Sync/ and Maintenance/ in the Obsidian vault,
synthesizes a crisp daily morning briefing via Ollama on CT 104 (NVIDIA Quadro M1200),
and writes the result to Daily/YYYY-MM-DD.md.
"""

import os
import sys
import glob
import json
import argparse
import datetime
import urllib.request
import urllib.error

DEFAULT_VAULT_DIR = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/dtheurer/Obsidian/Vault/Personal"
)
OLLAMA_ENDPOINT = os.environ.get(
    "OLLAMA_API_URL",
    "http://192.168.40.246:11434"
)
DEFAULT_MODEL = "qwen2.5:3b-instruct"


def collect_vault_context(vault_dir):
    context_chunks = []

    # 1. Mirrored To Do lists
    sync_files = glob.glob(os.path.join(vault_dir, "_Sync", "*.md"))
    for sf in sync_files:
        if os.path.basename(sf) in ["README.md", "todo-all.md"]:
            continue
        try:
            with open(sf, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    context_chunks.append(f"### {os.path.basename(sf)}\n{content}")
        except Exception as e:
            print(f"Warning reading {sf}: {e}")

    # 2. Maintenance files
    maint_files = glob.glob(os.path.join(vault_dir, "Maintenance", "*.md"))
    for mf in maint_files:
        try:
            with open(mf, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    context_chunks.append(f"### Maintenance: {os.path.basename(mf)}\n{content}")
        except Exception as e:
            print(f"Warning reading {mf}: {e}")

    # 3. Dedicated Task files
    task_files = glob.glob(os.path.join(vault_dir, "Tasks", "*.md"))
    for tf in task_files:
        if os.path.basename(tf) == "README.md":
            continue
        try:
            with open(tf, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    context_chunks.append(f"### Task: {os.path.basename(tf)}\n{content}")
        except Exception as e:
            print(f"Warning reading {tf}: {e}")

    return "\n\n".join(context_chunks)


def generate_briefing(vault_dir, model=DEFAULT_MODEL, dry_run=False):
    today = datetime.date.today().strftime("%Y-%m-%d")
    weekday = datetime.date.today().strftime("%A")
    print(f"🧠 Collecting Second Brain context from {vault_dir} for {weekday}, {today}...")

    raw_context = collect_vault_context(vault_dir)
    if not raw_context.strip():
        print("⚠️ No tasks or maintenance files found in vault to summarize.")
        raw_context = "*No external tasks or maintenance items currently on record.*"

    prompt = f"""You are the family household intelligence assistant running locally on the homelab GPU.
Today is {weekday}, {today}.

Below is the raw static markdown extracted from the family Second Brain vault (_Sync/ and Maintenance/):

---
{raw_context}
---

Generate an actionable, concise, well-structured morning briefing for Daily/{today}.md.
Format strictly with these sections in clean Markdown:

# ☀️ Morning Briefing: {weekday}, {today}

## 🎯 Top 3 Priorities for Today
(Highlight the top 3 most urgent tasks or deadlines)

## 🛒 Groceries & Shopping
(List any grocery items needed from _Sync/todo-groceries.md)

## 🛠️ Household & Maintenance Check
(Check due dates from Maintenance/ or upcoming seasonal maintenance)

## 📋 Open Tasks & Follow-ups
(Group remaining open tasks by category)

Keep the tone encouraging, crisp, and direct. Do not include markdown code block backticks around the whole response."""

    print(f"🤖 Sending request to Ollama on {OLLAMA_ENDPOINT} using model '{model}'...")
    req = urllib.request.Request(
        f"{OLLAMA_ENDPOINT}/api/generate",
        data=json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "temperature": 0.4
            }
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            data = json.loads(res.read().decode("utf-8"))
            briefing_text = data.get("response", "").strip()
    except Exception as e:
        print(f"❌ Error communicating with Ollama: {e}")
        sys.exit(1)

    full_note = f"""---
type: daily-briefing
date: {today}
generated_by: {model} (NVIDIA Quadro M1200 CUDA)
status: generated
---

{briefing_text}
"""

    if dry_run:
        print(f"\n--- [DRY-RUN] Daily/{today}.md ---\n{full_note}")
    else:
        daily_dir = os.path.join(vault_dir, "Daily")
        os.makedirs(daily_dir, exist_ok=True)
        out_file = os.path.join(daily_dir, f"{today}.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(full_note)
        print(f"✅ Daily briefing generated and saved to {out_file}!")

    # Pushover mobile alert delivery
    send_pushover_briefing(f"☀️ Morning Briefing: {weekday}, {today}", briefing_text, dry_run=dry_run)


def send_pushover_briefing(title, text, dry_run=False):
    pushover_config_path = os.path.expanduser("~/.config/homelab-todo/pushover.json")
    user_key = os.environ.get("PUSHOVER_USER_KEY")
    api_token = os.environ.get("PUSHOVER_API_TOKEN")

    if (not user_key or not api_token) and os.path.exists(pushover_config_path):
        try:
            with open(pushover_config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                user_key = user_key or cfg.get("user_key")
                api_token = api_token or cfg.get("api_token")
        except Exception as e:
            print(f"⚠️ Error reading {pushover_config_path}: {e}")

    if not user_key or not api_token:
        print("ℹ️ Pushover credentials not configured; skipping mobile push (configure ~/.config/homelab-todo/pushover.json or env vars to enable).")
        return

    # Pushover messages are max 1024 chars
    if len(text) > 1000:
        push_msg = text[:950] + "\n\n... [Full briefing saved in Obsidian Daily note]"
    else:
        push_msg = text

    if dry_run:
        print(f"\n--- [DRY-RUN Pushover Push] Title: {title} ---\n{push_msg}")
        return

    import urllib.parse
    data = urllib.parse.urlencode({
        "token": api_token,
        "user": user_key,
        "title": title,
        "message": push_msg,
        "priority": 0
    }).encode("utf-8")

    req = urllib.request.Request("https://api.pushover.net/1/messages.json", data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            if res.status == 200:
                print("📲 Pushover mobile briefing sent successfully!")
            else:
                print(f"⚠️ Pushover returned HTTP status {res.status}")
    except Exception as e:
        print(f"⚠️ Failed to deliver Pushover notification: {e}")


def main():
    parser = argparse.ArgumentParser(description="Generate daily AI morning briefing from vault context.")
    parser.add_argument("--vault-dir", default=DEFAULT_VAULT_DIR, help="Path to Obsidian Vault root.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true", help="Print briefing to stdout without writing file.")
    args = parser.parse_args()

    generate_briefing(args.vault_dir, model=args.model, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
