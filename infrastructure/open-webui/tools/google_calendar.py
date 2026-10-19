"""
title: Google Family Calendar
author: homelab
author_url: https://github.com/meek2100/homelab-infrastructure
git_url: https://github.com/meek2100/homelab-infrastructure
description: Query appointments, doctor visits, and schedule new events on the Google Family Calendar
version: 1.0.0
requirements: google-api-python-client, google-auth-oauthlib, pydantic
"""

import os
import json
import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        CALENDAR_ID: str = Field(
            default="primary",
            description="Google Calendar ID (from ~/.config/homelab-todo/google_calendar.json)"
        )
        TOKEN_PATH: str = Field(
            default="~/.config/homelab-todo/google_token.json",
            description="Path to authorized Google token file"
        )

    def __init__(self):
        self.valves = self.Valves()
        cfg_file = os.path.expanduser("~/.config/homelab-todo/google_calendar.json")
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file) as f:
                    self.valves.CALENDAR_ID = json.load(f).get("calendar_id", self.valves.CALENDAR_ID)
            except Exception:
                pass

    def _get_service(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        token_path = os.path.expanduser(self.valves.TOKEN_PATH)
        if not os.path.exists(token_path):
            raise ValueError(f"Google token file not found at {token_path}. Run sync-google-calendar-to-vault.py --auth first.")

        creds = Credentials.from_authorized_user_file(token_path, [
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.readonly"
        ])
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    def get_upcoming_events(
        self,
        days: int = 7,
        search_query: Optional[str] = None
    ) -> str:
        """
        Check upcoming events, doctor appointments, school schedules, and family activities.
        :param days: Number of days ahead to look (default: 7).
        :param search_query: Optional search keyword to filter events (e.g. 'doctor', 'swim', 'vet', 'gymnastics').
        :return: Formatted list of scheduled family events.
        """
        try:
            service = self._get_service()
            now = datetime.datetime.now(datetime.timezone.utc)
            start_time = now.isoformat()
            end_time = (now + datetime.timedelta(days=days)).isoformat()

            events_result = service.events().list(
                calendarId=self.valves.CALENDAR_ID,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime",
                q=search_query
            ).execute()

            items = events_result.get("items", [])
            if not items:
                search_msg = f" matching '{search_query}'" if search_query else ""
                return f"No events scheduled{search_msg} in the next {days} days."

            lines = [f"📅 Upcoming Family Events (Next {days} Days):"]
            for ev in items:
                summary = ev.get("summary", "Untitled")
                start = ev.get("start", {})
                start_str = start.get("dateTime", start.get("date"))
                loc = f" at {ev.get('location')}" if ev.get("location") else ""
                lines.append(f"• {start_str}: {summary}{loc}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error querying family calendar: {str(e)}"

    def add_calendar_event(
        self,
        summary: str,
        start_time: str,
        end_time: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """
        Add a new event or appointment to the Google Family Calendar.
        :param summary: Title/summary of the event (e.g. 'Dentist appointment', 'Family dinner').
        :param start_time: Start date/time in YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS format.
        :param end_time: Optional end date/time (defaults to 1 hour after start).
        :param location: Optional physical address or venue name.
        :param description: Optional notes or description.
        :return: Success confirmation.
        """
        try:
            service = self._get_service()
            body = {
                "summary": summary,
                "description": description or "Created by Homelab Assistant"
            }
            if location:
                body["location"] = location

            if "T" in start_time:
                body["start"] = {"dateTime": start_time}
                if not end_time:
                    dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    end_time = (dt + datetime.timedelta(hours=1)).isoformat()
                body["end"] = {"dateTime": end_time}
            else:
                body["start"] = {"date": start_time}
                body["end"] = {"date": end_time or start_time}

            event = service.events().insert(calendarId=self.valves.CALENDAR_ID, body=body).execute()
            return f"✅ Successfully added '{summary}' on {start_time} to Google Family Calendar!"
        except Exception as e:
            return f"Error adding event to calendar: {str(e)}"
