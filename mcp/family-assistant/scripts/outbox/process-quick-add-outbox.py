#!/usr/bin/env python3
"""
process-quick-add-outbox.py
===========================
Processes the bidirectional Quick Add outbox in Obsidian (_Sync/Quick Add.md).
Parses pending checkboxes (- [ ]) and dispatches them to their respective destinations:
  - Groceries (e.g. - [ ] [groc] Milk or - [ ] Eggs -> Microsoft To Do Groceries)
  - Tasks (e.g. - [ ] [todo] Clean gutters -> Microsoft To Do Tasks)
  - Events (e.g. - [ ] [cal] 2026-10-25 14:00 Dentist -> Google Calendar)
  - Recipes (e.g. - [ ] [recipe] https://example.com/recipe -> Paprika Recipe Importer)

Once processed, the item is marked complete or annotated in place with a timestamp.

Usage:
    .venv/bin/python3 process-quick-add-outbox.py [--vault-dir PATH] [--dry-run]
"""

import os
import sys
import re
import datetime
import argparse
import subprocess
import json
import urllib.request

def find_repo_root():
    cur = os.path.dirname(os.path.abspath(__file__))
    while cur and cur != "/":
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        cur = os.path.dirname(cur)
    return "/home/agentsvc/repos/homelab-infrastructure"

REPO_ROOT = find_repo_root()
DEFAULT_VAULT_DIR = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/dtheurer/Obsidian/Vault/Personal"
)
OUTBOX_REL_PATH = os.path.join("_Sync", "Quick Add.md")

INITIAL_TEMPLATE = """# ⚡ Quick Add Outbox

Type items below in plain text! You do NOT need checkboxes or special tags.
The background AI sync daemon classifies and routes everything automatically:

- **Groceries**: `Cinnamon rolls` or `Milk, eggs, butter` (goes to Microsoft To Do Groceries)
- **Tasks**: `Call accountant about taxes` or `Fix sprinkler` (goes to Microsoft To Do Tasks)
- **Calendar**: `Dentist on Thursday at 2:30pm` (goes to Google Family Calendar)
- **Recipes**: `https://pinchofyum.com/...` (imported to Paprika)

---

## 📥 Pending Outbox
"""


def ensure_outbox_file(vault_dir):
    outbox_path = os.path.join(vault_dir, OUTBOX_REL_PATH)
    os.makedirs(os.path.dirname(outbox_path), exist_ok=True)
    if not os.path.exists(outbox_path):
        with open(outbox_path, "w", encoding="utf-8") as f:
            f.write(INITIAL_TEMPLATE)
        print(f"✨ Created initial Quick Add outbox at {outbox_path}")
    return outbox_path


def run_helper(script_rel_path, args):
    python_bin = sys.executable
    script_path = os.path.join(REPO_ROOT, "mcp", "family-assistant", "scripts", script_rel_path)
    cmd = [python_bin, script_path] + args
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    return res.returncode, res.stdout, res.stderr


def classify_item(raw_text):
    text = raw_text.strip()

    # 1. URL is always a recipe
    if text.startswith("http://") or text.startswith("https://"):
        return "RECIPE", text

    # 2. Check for manual tags if someone chose to use them
    tag_match = re.match(r"^\[([a-zA-Z]+)\]\s*(.*)$", text)
    if tag_match:
        tag = tag_match.group(1).lower()
        content = tag_match.group(2).strip()
        if tag in ["groc", "grocery", "groceries"]:
            return "GROCERIES", content
        elif tag in ["cal", "calendar", "event"]:
            return "CALENDAR", content
        elif tag in ["recipe", "food"]:
            return "RECIPE", content
        elif tag in ["todo", "task", "chore", "work"]:
            return "TASKS", content

    # 3. Intelligent Classification via Local Ollama (llama3.2:3b on CT 104)
    endpoint = os.environ.get("OLLAMA_API_URL", "http://192.168.40.246:11434") + "/api/generate"
    prompt = f"""You are an inbox assistant. Classify this note into exactly one destination: GROCERIES, TASKS, CALENDAR, or RECIPE.
Note: "{text}"
Rules:
- Food, ingredients, groceries, or household supplies (e.g. "Cinnamon rolls", "Paper towels", "Milk, butter, eggs") -> GROCERIES
- Action items, chores, errands, repairs (e.g. "Call accountant", "Fix sprinkler", "Clean garage") -> TASKS
- Events with dates or times (e.g. "Dentist on Thursday at 2:30pm", "Flight at 10am") -> CALENDAR
- Cooking recipe links or instructions -> RECIPE
Respond ONLY with a JSON object: {{"destination": "GROCERIES"|"TASKS"|"CALENDAR"|"RECIPE", "title": "{text}"}}"""

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({
                "model": "llama3.2:3b",
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 40}
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            res_str = json.loads(res.read().decode("utf-8")).get("response", "{}")
            data = json.loads(res_str)
            dest = data.get("destination", "").upper()
            title = data.get("title", text)
            if dest in ["GROCERIES", "TASKS", "CALENDAR", "RECIPE"]:
                return dest, title
    except Exception:
        pass

    # 4. Fast heuristic fallback
    first_word = text.split()[0].lower() if text.split() else ""
    if first_word in ["call", "fix", "repair", "email", "clean", "schedule", "order", "install", "meet"]:
        return "TASKS", text
    return "GROCERIES", text


def process_item(raw_text):
    dest, title = classify_item(raw_text)

    # 1. Recipe
    if dest == "RECIPE":
        print(f"🍳 Dispatching Recipe to Paprika: {title}")
        code, out, err = run_helper("recipes/import-paprika-recipe.py", [title])
        if code == 0:
            return True, "Imported to Paprika"
        return False, f"Failed: {err.strip() or out.strip()}"

    # 2. Calendar
    if dest == "CALENDAR":
        cal_match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\d{2}))?\s+(.*)$", title)
        if cal_match:
            date_str = cal_match.group(1)
            time_str = cal_match.group(2) or "09:00"
            summary = cal_match.group(3).strip()
            start_iso = f"{date_str}T{time_str}:00"
            code, out, err = run_helper("calendar/manage-calendar-cli.py", ["add", summary, "--start", start_iso])
            if code == 0:
                return True, f"Scheduled in Google Calendar ({start_iso})"
            return False, f"Failed: {err.strip() or out.strip()}"
        else:
            code, out, err = run_helper("calendar/manage-calendar-cli.py", ["add", title])
            if code == 0:
                return True, "Scheduled in Google Calendar"
            return False, f"Failed: {err.strip() or out.strip()}"

    # 3. Groceries
    if dest == "GROCERIES":
        items = [i.strip() for i in title.split(",") if i.strip()]
        for item in items:
            print(f"🛒 Adding Grocery item: {item}")
            run_helper("todo/manage-todo-cli.py", ["add", item, "--list", "Groceries"])
        return True, f"Added {len(items)} item(s) to Groceries"

    # 4. Tasks
    list_name = "Tasks"
    print(f"📋 Adding To Do item to '{list_name}': {title}")
    code, out, err = run_helper("todo/manage-todo-cli.py", ["add", title, "--list", list_name])
    if code == 0:
        return True, f"Added to Microsoft To Do ({list_name})"
    return False, f"Failed: {err.strip() or out.strip()}"


def process_outbox(vault_dir, dry_run=False):
    outbox_path = ensure_outbox_file(vault_dir)

    with open(outbox_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    modified = False
    processed_count = 0
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_lines = []
    in_pending_section = False

    for line in lines:
        stripped = line.strip()
        
        # Look for the start of the pending outbox section
        if "Pending Outbox" in stripped:
            in_pending_section = True
            new_lines.append(line)
            continue

        # If not yet in the pending outbox section, preserve existing headers/instructions
        if not in_pending_section:
            new_lines.append(line)
            continue

        # Skip empty lines, headers, comments, and divider lines
        if not stripped or stripped.startswith("#") or stripped == "---" or stripped.startswith("<!--"):
            new_lines.append(line)
            continue

        # Skip already completed items
        if stripped.startswith("- [x] ") or "*(✓ " in stripped:
            new_lines.append(line)
            continue

        # Clean off common prefixes: '- [ ] ', '- ', '* ', or accept plain text
        item_text = stripped
        if item_text.startswith("- [ ] "):
            item_text = item_text[6:].strip()
        elif item_text.startswith("- ") or item_text.startswith("* "):
            item_text = item_text[2:].strip()

        if not item_text:
            new_lines.append(line)
            continue

        if dry_run:
            dest, title = classify_item(item_text)
            print(f"  [DRY-RUN] '{item_text}' -> Classified as {dest} ('{title}')")
            new_lines.append(line)
            continue

        success, note = process_item(item_text)
        if success:
            new_lines.append(f"- [x] {item_text} *(✓ {note} at {now_str})*\n")
            processed_count += 1
            modified = True
        else:
            new_lines.append(f"- [ ] {item_text} *(⚠️ {note})*\n")
            modified = True

    if modified and not dry_run:
        with open(outbox_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"✅ Processed and updated {processed_count} Quick Add items in {outbox_path}")
    elif processed_count == 0 and not dry_run:
        print("ℹ️ No pending items found in Quick Add outbox.")


def main():
    parser = argparse.ArgumentParser(description="Process Obsidian Quick Add Outbox")
    parser.add_argument("--vault-dir", default=DEFAULT_VAULT_DIR, help="Obsidian Vault path")
    parser.add_argument("--dry-run", action="store_true", help="Preview items without executing")
    args = parser.parse_args()

    process_outbox(args.vault_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
