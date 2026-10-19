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

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEFAULT_VAULT_DIR = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/dtheurer/Obsidian/Vault/Personal"
)
OUTBOX_REL_PATH = os.path.join("_Sync", "Quick Add.md")

INITIAL_TEMPLATE = """# ⚡ Quick Add Outbox

Type items below as checkboxes (`- [ ] `). The background sync daemon will process them and dispatch to Microsoft To Do, Google Calendar, or Paprika!

### Routing Syntax:
- **Groceries**: `- [ ] [groc] Milk, Eggs, Bread` (or `- [ ] [grocery] ...`)
- **Tasks**: `- [ ] [todo] Replace furnace filter` (or `- [ ] [task] ...`)
- **Calendar**: `- [ ] [cal] 2026-10-26 15:30 Doctor appointment`
- **Recipe**: `- [ ] [recipe] https://pinchofyum.com/recipe-url`
- *(Items without tags default to Microsoft To Do Tasks)*

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
    python_bin = os.path.join(REPO_ROOT, ".venv", "bin", "python3")
    script_path = os.path.join(REPO_ROOT, "mcp", "family-assistant", "scripts", script_rel_path)
    cmd = [python_bin, script_path] + args
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    return res.returncode, res.stdout, res.stderr


def process_item(raw_text):
    text = raw_text.strip()
    tag_match = re.match(r"^\[([a-zA-Z]+)\]\s*(.*)$", text)
    tag = tag_match.group(1).lower() if tag_match else None
    content = tag_match.group(2).strip() if tag_match else text

    # 1. Recipe URL or Import
    if tag in ["recipe", "food"] or content.startswith("http://") or content.startswith("https://"):
        url = content
        print(f"🍳 Dispatching Recipe to Paprika: {url}")
        code, out, err = run_helper("recipes/import-paprika-recipe.py", [url])
        if code == 0:
            return True, "Imported to Paprika"
        return False, f"Failed: {err.strip() or out.strip()}"

    # 2. Calendar Event
    if tag in ["cal", "calendar", "event"]:
        # Match date & time if provided: YYYY-MM-DD HH:MM Title
        cal_match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\d{2}))?\s+(.*)$", content)
        if cal_match:
            date_str = cal_match.group(1)
            time_str = cal_match.group(2) or "09:00"
            summary = cal_match.group(3).strip()
            start_iso = f"{date_str}T{time_str}:00"
            print(f"📅 Dispatching Calendar Event: '{summary}' on {start_iso}")
            code, out, err = run_helper("calendar/manage-calendar-cli.py", ["add", summary, "--start", start_iso])
            if code == 0:
                return True, f"Scheduled in Google Calendar ({start_iso})"
            return False, f"Failed: {err.strip() or out.strip()}"
        else:
            return False, "Invalid calendar format. Use: [cal] YYYY-MM-DD HH:MM Event Title"

    # 3. Groceries
    if tag in ["groc", "grocery", "groceries"]:
        # Handle comma-separated list
        items = [i.strip() for i in content.split(",") if i.strip()]
        for item in items:
            print(f"🛒 Adding Grocery item: {item}")
            run_helper("todo/manage-todo-cli.py", ["add", item, "--list", "Groceries"])
        return True, f"Added {len(items)} items to Groceries"

    # 4. Default: Microsoft To Do Tasks
    list_name = "Tasks"
    if tag in ["chore", "family"]:
        list_name = "Family"
    elif tag in ["work", "project"]:
        list_name = "Home projects"

    print(f"📋 Adding To Do item to '{list_name}': {content}")
    code, out, err = run_helper("todo/manage-todo-cli.py", ["add", content, "--list", list_name])
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

    for line in lines:
        stripped = line.strip()
        # Look for open checkboxes: - [ ] item
        if stripped.startswith("- [ ] "):
            item_text = stripped[6:].strip()
            # Skip if already marked with error or processed comment
            if "<!-- done" in item_text:
                new_lines.append(line)
                continue

            if dry_run:
                print(f"  [DRY-RUN] Would process: {item_text}")
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
        else:
            new_lines.append(line)

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
