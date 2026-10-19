#!/usr/bin/env python3
"""
Google Family Calendar Management CLI
Allows viewing, searching, and adding events directly to the Google Family Calendar.
"""

import os
import sys
import json
import argparse
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly"
]

CONFIG_DIR = os.path.expanduser("~/.config/homelab-todo")
CALENDAR_CONFIG_FILE = os.path.join(CONFIG_DIR, "google_calendar.json")
TOKEN_FILE = os.path.join(CONFIG_DIR, "google_token.json")


def get_credentials():
    if not os.path.exists(TOKEN_FILE):
        print("❌ Error: Google token file not found. Run sync-google-calendar-to-vault.py --auth first.")
        sys.exit(1)
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        os.chmod(TOKEN_FILE, 0o600)
    return creds


def get_calendar_id():
    if os.path.exists(CALENDAR_CONFIG_FILE):
        try:
            with open(CALENDAR_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("calendar_id", "primary")
        except Exception:
            pass
    return "primary"


def list_events(days=7, search=None):
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    calendar_id = get_calendar_id()

    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now.isoformat()
    end_time = (now + datetime.timedelta(days=days)).isoformat()

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time,
        timeMax=end_time,
        singleEvents=True,
        orderBy="startTime",
        q=search
    ).execute()

    items = events_result.get("items", [])
    if not items:
        search_msg = f" matching '{search}'" if search else ""
        print(f"No upcoming events found{search_msg} in the next {days} days.")
        return []

    print(f"📅 Google Family Calendar Events (Next {days} Days):")
    for ev in items:
        summary = ev.get("summary", "Untitled")
        start = ev.get("start", {})
        start_time_str = start.get("dateTime", start.get("date"))
        loc = f" (📍 {ev.get('location')})" if ev.get("location") else ""
        print(f"  • {start_time_str}: {summary}{loc}")
    return items


def add_event(summary, start_iso, end_iso=None, location=None, description=None):
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    calendar_id = get_calendar_id()

    # Determine if all-day or datetime
    event_body = {
        "summary": summary,
        "description": description or "Created by Homelab Family Assistant"
    }
    if location:
        event_body["location"] = location

    # Parse date/time
    if "T" in start_iso:
        event_body["start"] = {"dateTime": start_iso}
        if not end_iso:
            # Default 1 hour duration
            dt = datetime.datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            end_iso = (dt + datetime.timedelta(hours=1)).isoformat()
        event_body["end"] = {"dateTime": end_iso}
    else:
        # All day event
        event_body["start"] = {"date": start_iso}
        if not end_iso:
            end_iso = start_iso
        event_body["end"] = {"date": end_iso}

    event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    print(f"✅ Added event '{summary}' to Family Calendar! Link: {event.get('htmlLink')}")
    return event


def main():
    parser = argparse.ArgumentParser(description="Manage Google Family Calendar events.")
    subparsers = parser.add_subparsers(dest="command")

    list_p = subparsers.add_parser("list", help="List upcoming events")
    list_p.add_argument("--days", type=int, default=14, help="Days ahead to look")
    list_p.add_argument("--search", "-s", help="Search keyword")

    add_p = subparsers.add_parser("add", help="Add an event to the Family Calendar")
    add_p.add_argument("summary", help="Event title / summary")
    add_p.add_argument("--start", "-s", required=True, help="Start time (YYYY-MM-DD or ISO 8601 YYYY-MM-DDTHH:MM:SS)")
    add_p.add_argument("--end", "-e", help="End time (YYYY-MM-DD or ISO 8601)")
    add_p.add_argument("--location", "-l", help="Event location")
    add_p.add_argument("--description", "-d", help="Event description/notes")

    args = parser.parse_args()
    if args.command == "list":
        list_events(days=args.days, search=args.search)
    elif args.command == "add":
        add_event(args.summary, args.start, end_iso=args.end, location=args.location, description=args.description)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
