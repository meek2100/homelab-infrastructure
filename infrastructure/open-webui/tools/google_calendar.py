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
            default="family17480042687465380396@group.calendar.google.com",
            description="Google Calendar ID"
        )
        TOKEN_JSON: str = Field(
            default="",
            description="OAuth Token JSON contents (from ~/.config/homelab-todo/google_token.json)"
        )
        TOKEN_PATH: str = Field(
            default="~/.config/homelab-todo/google_token.json",
            description="Fallback path to authorized Google token file if running locally"
        )

    def __init__(self):
        self.valves = self.Valves()
        cfg_file = os.path.expanduser("~/.config/homelab-todo/google_calendar.json")
        if os.path.exists(cfg_file) and not self.valves.CALENDAR_ID:
            try:
                with open(cfg_file) as f:
                    self.valves.CALENDAR_ID = json.load(f).get("calendar_id", self.valves.CALENDAR_ID)
            except Exception:
                pass

    def _get_service(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        if self.valves.TOKEN_JSON:
            try:
                info = json.loads(self.valves.TOKEN_JSON)
                creds = Credentials.from_authorized_user_info(info, [
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/calendar.readonly"
                ])
            except Exception as e:
                raise ValueError(f"Failed to parse TOKEN_JSON in valves: {e}")
        else:
            token_path = os.path.expanduser(self.valves.TOKEN_PATH)
            if not os.path.exists(token_path):
                raise ValueError(f"Google token file not found at {token_path}. Run sync-google-calendar-to-vault.py --auth first.")
            creds = Credentials.from_authorized_user_file(token_path, [
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ])

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return build("calendar", "v3", credentials=creds)

    def search_calendar_events(
        self,
        days: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        count: Optional[int] = None,
        query: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> str:
        """
        Search or list calendar events.
        :param days: Number of days to look ahead.
        :param start: Optional start date/time.
        :param end: Optional end date/time.
        :param count: Optional count limit.
        :param query: Optional keyword search query.
        :param search_query: Optional keyword search query.
        :return: Formatted scheduled events.
        """
        try:
            service = self._get_service()
            now = datetime.datetime.now(datetime.timezone.utc)
            start_iso = None
            end_iso = None

            if start:
                try:
                    s_clean = start.replace("Z", "+00:00")
                    dt_start = datetime.datetime.fromisoformat(s_clean)
                    if dt_start.year >= 2026:
                        start_iso = dt_start.isoformat()
                except Exception:
                    pass

            if end:
                try:
                    e_clean = end.replace("Z", "+00:00")
                    dt_end = datetime.datetime.fromisoformat(e_clean)
                    if dt_end.year >= 2026:
                        end_iso = dt_end.isoformat()
                except Exception:
                    pass

            if not start_iso:
                start_iso = now.isoformat()
            if not end_iso:
                d = count or days or 7
                end_iso = (now + datetime.timedelta(days=d)).isoformat()

            q_term = query or search_query
            events_result = service.events().list(
                calendarId=self.valves.CALENDAR_ID,
                timeMin=start_iso,
                timeMax=end_iso,
                singleEvents=True,
                orderBy="startTime",
                q=q_term
            ).execute()

            items = events_result.get("items", [])
            if not items:
                search_msg = f" matching '{q_term}'" if q_term else ""
                return f"No events scheduled{search_msg} between {start_iso[:10]} and {end_iso[:10]}."

            lines = [f"📅 Scheduled Family Events ({len(items)} found):"]
            for ev in items:
                summary = ev.get("summary", "Untitled")
                ev_start = ev.get("start", {})
                start_str = ev_start.get("dateTime", ev_start.get("date"))
                loc = f" at {ev.get('location')}" if ev.get('location') else ""
                lines.append(f"• {start_str}: {summary}{loc}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error querying calendar: {str(e)}"

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
