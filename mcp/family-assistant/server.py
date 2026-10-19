"""
Family Assistant & Personal Second Brain FastMCP Server
Exposes action-oriented tools for Microsoft To Do, Paprika recipes & meal planning,
Obsidian Second Brain integration, and local AI daily morning briefings.
"""

import os
import sys
import subprocess
from typing import Annotated, Literal, Optional
from pydantic import Field

# Ensure repository virtualenv site-packages is in sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_venv_lib = os.path.join(_repo_root, ".venv", "lib")
if os.path.exists(_venv_lib):
    for _pyver in os.listdir(_venv_lib):
        _sp = os.path.join(_venv_lib, _pyver, "site-packages")
        if os.path.isdir(_sp) and _sp not in sys.path:
            sys.path.insert(0, _sp)

from fastmcp import FastMCP

mcp = FastMCP("Family Assistant & Second Brain")

MAX_OUTPUT_CHARS = 30000

def resolve_script_path(script_name: str) -> str:
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    direct = os.path.join(scripts_dir, script_name)
    if os.path.exists(direct):
        return direct
    for root, _, files in os.walk(scripts_dir):
        if script_name in files:
            return os.path.join(root, script_name)
    return direct

def run_script(script_name: str, args: list[str] = None, timeout: int = 180) -> str:
    if args is None:
        args = []
    repo_root = _repo_root
    script_path = resolve_script_path(script_name)
    python_bin = os.path.join(repo_root, ".venv", "bin", "python3")
    if not os.path.exists(python_bin):
        python_bin = sys.executable
    cmd = [python_bin, script_path] + args
    try:
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=timeout)
        output = res.stdout if res.returncode == 0 else f"Error ({res.returncode}):\n{res.stderr}\n{res.stdout}"
        return output[:MAX_OUTPUT_CHARS]
    except subprocess.TimeoutExpired:
        return f"Error: Execution of {script_name} timed out after {timeout} seconds."
    except Exception as e:
        return f"Exception executing {script_name}: {e}"


# ==============================================================================
# 1. MICROSOFT TO DO & TASK MANAGEMENT
# ==============================================================================

@mcp.tool()
def manage_todo(
    action: Annotated[Literal["add", "complete", "lists", "sync"], Field(
        description="Action to perform: 'add' new task/grocery, 'complete' task, 'lists' view all lists, 'sync' mirror to Obsidian."
    )],
    title: Annotated[Optional[str], Field(
        description="Title or content of task or grocery item (required for 'add' and 'complete').",
        default=None
    )] = None,
    list_name: Annotated[Optional[str], Field(
        description="Target list name or keyword (e.g. 'Home - Groceries', 'Home - Todo List', 'Groceries').",
        default="Home - Groceries"
    )] = "Home - Groceries",
    due_date: Annotated[Optional[str], Field(
        description="Optional due date in YYYY-MM-DD format (e.g. '2026-10-31').",
        default=None
    )] = None,
    notes: Annotated[Optional[str], Field(
        description="Optional notes or details for the task.",
        default=None
    )] = None,
    dry_run: Annotated[bool, Field(
        description="When syncing, perform dry-run without writing files.",
        default=False
    )] = False
) -> str:
    """Manage Microsoft To Do tasks, family shopping lists, and Obsidian vault task mirrors."""
    if action == "sync":
        args = ["--dry-run"] if dry_run else []
        return run_script("sync-todo-to-vault.py", args)

    if action == "lists":
        return run_script("manage-todo-cli.py", ["lists"])

    if action == "add":
        if not title:
            return "Error: 'title' is required for action='add'."
        args = ["add", title]
        if list_name:
            args.extend(["--list", list_name])
        if due_date:
            args.extend(["--due", due_date])
        if notes:
            args.extend(["--notes", notes])
        return run_script("manage-todo-cli.py", args)

    if action == "complete":
        if not title:
            return "Error: 'title' is required for action='complete'."
        args = ["complete", title]
        if list_name:
            args.extend(["--list", list_name])
        return run_script("manage-todo-cli.py", args)

    return f"Unsupported action: {action}"


# ==============================================================================
# 2. PAPRIKA RECIPES & MEAL PLANNING
# ==============================================================================

@mcp.tool()
def manage_recipes(
    action: Annotated[Literal["sync", "import"], Field(
        description="Action to perform: 'sync' pull Paprika recipes and meal plans to vault, 'import' parse and upload recipe from URL or text."
    )],
    url: Annotated[Optional[str], Field(
        description="URL of recipe to scrape and import (for action='import').",
        default=None
    )] = None,
    text: Annotated[Optional[str], Field(
        description="Raw recipe text to parse via local LLM (for action='import').",
        default=None
    )] = None,
    category: Annotated[Optional[str], Field(
        description="Optional Paprika category name (e.g. 'Oven Baked Dinner', 'Cookies', 'Crockpot Dinners').",
        default=None
    )] = None,
    force: Annotated[bool, Field(
        description="When syncing, force re-download all recipes regardless of hash cache.",
        default=False
    )] = False,
    dry_run: Annotated[bool, Field(
        description="Dry-run without writing files to vault or uploading.",
        default=False
    )] = False
) -> str:
    """Synchronize Paprika Recipe Manager recipes, meal calendar, and active groceries to Obsidian, or import new recipes."""
    if action == "import":
        if not url and not text:
            return "Error: Either 'url' or 'text' must be provided for action='import'."
        args = []
        if url:
            args.extend(["--url", url])
        if text:
            args.extend(["--text", text])
        if category:
            args.extend(["--category", category])
        return run_script("import-paprika-recipe.py", args, timeout=120)

    args = []
    if dry_run:
        args.append("--dry-run")
    if force:
        args.append("--force")
    return run_script("sync-paprika-to-vault.py", args)


# ==============================================================================
# 3. DAILY MORNING BRIEFING & NOTIFICATIONS
# ==============================================================================

@mcp.tool()
def generate_morning_briefing(
    dry_run: Annotated[bool, Field(
        description="If True, print briefing to output without saving Daily note or sending mobile alert.",
        default=False
    )] = False,
    model: Annotated[str, Field(
        description="Ollama model to use on CT 104 GPU.",
        default="qwen2.5:3b-instruct"
    )] = "qwen2.5:3b-instruct"
) -> str:
    """Synthesizes the daily AI morning briefing from vault tasks and maintenance records, and dispatches via Pushover."""
    args = ["--model", model]
    if dry_run:
        args.append("--dry-run")
    return run_script("generate-daily-briefing.py", args, timeout=240)


# ==============================================================================
# 4. GOOGLE FAMILY CALENDAR
# ==============================================================================

@mcp.tool()
def manage_calendar(
    action: Annotated[Literal["sync", "list", "add"], Field(
        description="Action to perform: 'sync' mirror family calendar to vault, 'list' view upcoming events, 'add' schedule new event."
    )],
    days: Annotated[int, Field(
        description="Days ahead to fetch or search (for 'sync' and 'list').",
        default=14
    )] = 14,
    search: Annotated[Optional[str], Field(
        description="Search keyword for events (for action='list').",
        default=None
    )] = None,
    summary: Annotated[Optional[str], Field(
        description="Event title/summary (for action='add').",
        default=None
    )] = None,
    start_time: Annotated[Optional[str], Field(
        description="Start time in YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS format (for action='add').",
        default=None
    )] = None,
    end_time: Annotated[Optional[str], Field(
        description="Optional end time in ISO format (for action='add').",
        default=None
    )] = None,
    location: Annotated[Optional[str], Field(
        description="Optional event location.",
        default=None
    )] = None,
    dry_run: Annotated[bool, Field(
        description="When syncing, dry-run without writing files.",
        default=False
    )] = False
) -> str:
    """Manage Google Family Calendar events, sync schedule to Obsidian vault, or query appointments."""
    if action == "sync":
        args = ["--days", str(days)]
        if dry_run:
            args.append("--dry-run")
        return run_script("sync-google-calendar-to-vault.py", args)

    if action == "list":
        args = ["list", "--days", str(days)]
        if search:
            args.extend(["--search", search])
        return run_script("manage-calendar-cli.py", args)

    if action == "add":
        if not summary or not start_time:
            return "Error: 'summary' and 'start_time' are required for action='add'."
        args = ["add", summary, "--start", start_time]
        if end_time:
            args.extend(["--end", end_time])
        if location:
            args.extend(["--location", location])
        return run_script("manage-calendar-cli.py", args)

    return f"Unsupported action: {action}"


# ==============================================================================
# 5. ZERO-TRUST CREDENTIALS BACKUP & RESTORATION
# ==============================================================================

@mcp.tool()
def manage_family_secrets(
    action: Annotated[Literal["backup", "restore", "status"], Field(
        description="Action to perform: 'backup' encrypt credentials with master age key to Git repo, 'restore' decrypt credentials on a new machine, 'status' verify sync and checksums."
    )],
    force: Annotated[bool, Field(
        description="When restoring, force overwrite existing local files.",
        default=False
    )] = False
) -> str:
    """Manage zero-trust SOPS encrypted backup and disaster recovery for Family Assistant tokens and credentials."""
    args = [action]
    if action == "restore" and force:
        args.append("--force")
    return run_script("manage-family-secrets.py", args)


if __name__ == "__main__":
    mcp.run()
