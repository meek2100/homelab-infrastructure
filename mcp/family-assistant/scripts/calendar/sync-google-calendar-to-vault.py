#!/usr/bin/env python3
"""
Google Family Calendar to Obsidian Vault Sync Engine
Synchronizes upcoming events from Google Family Calendar into static Markdown in the local Obsidian vault.
Integrates with the daily morning briefing engine for automated schedule alerts.
"""

import os
import sys
import json
import argparse
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly"
]

DEFAULT_VAULT_DIR = os.environ.get(
    "OBSIDIAN_VAULT_PATH",
    "/mnt/c/Users/dtheurer/Obsidian/Vault/Personal"
)
CONFIG_DIR = os.path.expanduser("~/.config/homelab-todo")
CREDENTIALS_FILE = os.path.join(CONFIG_DIR, "google_credentials.json")
CALENDAR_CONFIG_FILE = os.path.join(CONFIG_DIR, "google_calendar.json")
TOKEN_FILE = os.path.join(CONFIG_DIR, "google_token.json")


def get_calendar_id():
    if os.path.exists(CALENDAR_CONFIG_FILE):
        try:
            with open(CALENDAR_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("calendar_id"):
                    return cfg.get("calendar_id")
        except Exception as e:
            print(f"Warning reading {CALENDAR_CONFIG_FILE}: {e}")
    return None


def authenticate(interactive=False):
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"Warning loading token: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired Google Calendar token...")
            try:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w", encoding="utf-8") as token_f:
                    token_f.write(creds.to_json())
                os.chmod(TOKEN_FILE, 0o600)
                return creds
            except Exception as e:
                print(f"Token refresh failed: {e}")

        if interactive:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"❌ Credentials file not found: {CREDENTIALS_FILE}")
                sys.exit(1)
            print("\n" + "=" * 60)
            print("🔑 Google Calendar Authentication Required")
            print("=" * 60)
            print("Opening local authorization server...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            try:
                # In WSL/Linux, open port on local server
                creds = flow.run_local_server(port=0, open_browser=False)
            except Exception as e:
                print(f"Local server flow failed, falling back: {e}")
                creds = flow.run_local_server(port=8080, open_browser=False)

            with open(TOKEN_FILE, "w", encoding="utf-8") as token_f:
                token_f.write(creds.to_json())
            os.chmod(TOKEN_FILE, 0o600)
            print("✅ Google Calendar authentication successful! Token saved.")
        else:
            print("⚠️ No valid Google token found. Run with --auth first.")
            return None

    return creds


def resolve_target_calendar(service):
    configured_id = get_calendar_id()
    if configured_id:
        return configured_id, "Configured Family Calendar"

    # Search for Family calendar by name
    cal_list = service.calendarList().list().execute().get("items", [])
    for c in cal_list:
        summary = c.get("summary", "")
        if "family" in summary.lower():
            return c["id"], summary

    # Fallback to primary
    return "primary", "Primary Calendar"


def sync_calendar(vault_dir=DEFAULT_VAULT_DIR, days=30, dry_run=False):
    creds = authenticate(interactive=False)
    if not creds:
        sys.exit(1)

    service = build("calendar", "v3", credentials=creds)
    calendar_id, calendar_name = resolve_target_calendar(service)
    print(f"📅 Connected to Google Calendar: '{calendar_name}' (ID: {calendar_id})")

    now = datetime.datetime.now(datetime.timezone.utc)
    # Start from beginning of today local
    today_local = datetime.date.today()
    start_time = datetime.datetime.combine(today_local, datetime.time.min).astimezone().isoformat()
    end_time = (now + datetime.timedelta(days=days)).isoformat()

    print(f"📡 Fetching events from {today_local} to {today_local + datetime.timedelta(days=days)}...")
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time,
        timeMax=end_time,
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])

    today_str = today_local.strftime("%Y-%m-%d")
    today_events = []
    upcoming_events = []

    for ev in events:
        summary = ev.get("summary", "Untitled Event").strip()
        start = ev.get("start", {})
        end = ev.get("end", {})

        # Date vs DateTime
        if "dateTime" in start:
            start_dt = datetime.datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).astimezone()
            end_dt = datetime.datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00")).astimezone()
            ev_date_str = start_dt.strftime("%Y-%m-%d")
            time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
        else:
            ev_date_str = start.get("date", "")
            time_str = "All Day"

        location = ev.get("location")
        loc_str = f" 📍 *{location}*" if location else ""
        item_line = f"- **{time_str}**: {summary}{loc_str}"

        if ev_date_str == today_str:
            today_events.append(item_line)
        else:
            try:
                ev_d = datetime.date.fromisoformat(ev_date_str)
                header_date = ev_d.strftime("%Y-%m-%d (%a)")
            except Exception:
                header_date = ev_date_str
            upcoming_events.append(f"- **{header_date}** [{time_str}]: {summary}{loc_str}")

    timestamp_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    weekday_str = today_local.strftime("%A")

    md = [
        "# 📅 Google Family Calendar\n",
        f"*Target: {calendar_name} | Last synchronized: {timestamp_now}*\n",
        f"## ☀️ Today: {weekday_str}, {today_str}\n"
    ]

    if not today_events:
        md.append("*No events scheduled for today.*\n")
    else:
        for t in today_events:
            md.append(t)
        md.append("")

    md.append(f"## 📆 Upcoming Family Schedule (Next {days} Days)\n")
    if not upcoming_events:
        md.append("*No upcoming events found on family calendar.*\n")
    else:
        for u in upcoming_events:
            md.append(u)
        md.append("")

    content = "\n".join(md)

    if dry_run:
        print(f"\n--- [DRY-RUN] _Sync/calendar-family.md ---\n{content}")
    else:
        sync_dir = os.path.join(vault_dir, "_Sync")
        os.makedirs(sync_dir, exist_ok=True)
        out_path = os.path.join(sync_dir, "calendar-family.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Synchronized {len(events)} events to {out_path}!")


def main():
    parser = argparse.ArgumentParser(description="Sync Google Family Calendar to Obsidian Vault.")
    parser.add_argument("--auth", action="store_true", help="Perform initial OAuth login.")
    parser.add_argument("--vault-dir", default=DEFAULT_VAULT_DIR, help=f"Path to Obsidian vault (default: {DEFAULT_VAULT_DIR})")
    parser.add_argument("--days", type=int, default=30, help="Days ahead to fetch (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Print output without saving to file.")
    args = parser.parse_args()

    if args.auth:
        authenticate(interactive=True)
    else:
        sync_calendar(vault_dir=args.vault_dir, days=args.days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
