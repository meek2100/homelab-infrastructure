"""
title: Second Brain Context Auto-Injector
author: homelab
author_url: https://github.com/meek2100/homelab-infrastructure
git_url: https://github.com/meek2100/homelab-infrastructure
description: Automatically intercepts user chat messages and injects live Microsoft To Do lists, Google Calendar schedules, and Paprika meal plans into the prompt so any model has instant, zero-effort access.
version: 1.0.0
requirements: requests, pydantic
"""

import json
import urllib.request
import urllib.parse
from typing import Optional
from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        MS_TODO_CLIENT_ID: str = Field(
            default="8edff306-100e-49e9-b523-883a026dc633",
            description="Microsoft Azure Client ID"
        )
        MS_TODO_REFRESH_TOKEN: str = Field(
            default="M.C528_SN1.0.U.MsaArtifacts.-CmnLfV43ZgCCDS!Ie1fkduicF*8RS*bnYVbSm4ae0xKtBwLzUpaSl7RDhcsGhpxWhZulMEC8s0KFfL0kfzrCcJwcAP98vh7ao2bdW6dpZPujIiviykyWJgmNhBzBXZkxo9E0S1DwdftxEWhc9XdnoH1oAQvoo4KNtyBtT0V9Nk8S4l3WiCTvtkOb66LcZCHfasmLSbNQy0nMG9pQdeWRQA1pQ1Q!qFT3waOUXLwUThMxE5GCMqJMOnOa5!lMyTEuKDock6D!9hnGRun73x*CGpXPUMQgIdgTvhAfqqRuWckWG6Bz2GcWwvjmz!DryLyl9VQDdK!t5WKhMkQWf!zT0tTxFQUNuGFuVDErNAn9sjEP",
            description="Microsoft To Do OAuth Refresh Token"
        )
        GOOGLE_CALENDAR_ID: str = Field(
            default="family17480042687465380396@group.calendar.google.com",
            description="Google Calendar ID"
        )
        GOOGLE_TOKEN_JSON: str = Field(
            default="",
            description="Google Calendar OAuth Token JSON contents"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_ms_todo_items(self, list_query: str = "groceries") -> str:
        if not self.valves.MS_TODO_REFRESH_TOKEN:
            return ""
        try:
            token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
            data = urllib.parse.urlencode({
                "client_id": self.valves.MS_TODO_CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": self.valves.MS_TODO_REFRESH_TOKEN,
                "scope": "Tasks.ReadWrite offline_access"
            }).encode("utf-8")
            req = urllib.request.Request(token_url, data=data)
            with urllib.request.urlopen(req, timeout=10) as res:
                access_token = json.loads(res.read().decode("utf-8"))["access_token"]

            # Get lists
            req = urllib.request.Request(
                "https://graph.microsoft.com/v1.0/me/todo/lists",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                lists = json.loads(res.read().decode("utf-8")).get("value", [])

            target = None
            q = list_query.lower()
            for l in lists:
                if q in l.get("displayName", "").lower():
                    target = l
                    break
            if not target and lists:
                target = lists[0]

            if not target:
                return ""

            encoded_filter = urllib.parse.quote("status ne 'completed'")
            req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/todo/lists/{target['id']}/tasks?$filter={encoded_filter}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                tasks = json.loads(res.read().decode("utf-8")).get("value", [])

            items = [f"• {t.get('title')}" for t in tasks]
            return f"Current {target['displayName']} in Microsoft To Do:\n" + ("\n".join(items) if items else "No open items.")
        except Exception as e:
            return f"[Error fetching To Do: {e}]"

    def _get_calendar_events(self) -> str:
        if not self.valves.GOOGLE_TOKEN_JSON:
            return ""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            import datetime

            info = json.loads(self.valves.GOOGLE_TOKEN_JSON)
            creds = Credentials.from_authorized_user_info(info, [
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/calendar.readonly"
            ])
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

            service = build("calendar", "v3", credentials=creds)
            now = datetime.datetime.now(datetime.timezone.utc)
            start_time = now.isoformat()
            end_time = (now + datetime.timedelta(days=7)).isoformat()

            events_result = service.events().list(
                calendarId=self.valves.GOOGLE_CALENDAR_ID,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            items = events_result.get("items", [])
            lines = []
            for ev in items:
                summary = ev.get("summary", "Untitled")
                start = ev.get("start", {})
                start_str = start.get("dateTime", start.get("date"))
                lines.append(f"• {start_str}: {summary}")
            return "Upcoming Google Family Calendar Events (Next 7 Days):\n" + ("\n".join(lines) if lines else "No events scheduled.")
        except Exception as e:
            return f"[Error fetching Calendar: {e}]"

    async def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        messages = body.get("messages", [])
        if not messages:
            return body

        last_user_msg = messages[-1].get("content", "").lower()
        context_blocks = []

        # Intercept grocery/shopping queries
        if any(w in last_user_msg for w in ["grocer", "shopping", "buy", "store"]):
            todo_ctx = self._get_ms_todo_items("groceries")
            if todo_ctx:
                context_blocks.append(todo_ctx)

        # Intercept task/todo queries
        elif any(w in last_user_msg for w in ["task", "todo", "chore", "to-do"]):
            todo_ctx = self._get_ms_todo_items("tasks")
            if todo_ctx:
                context_blocks.append(todo_ctx)

        # Intercept calendar/schedule queries
        if any(w in last_user_msg for w in ["calendar", "schedule", "appointment", "event", "week", "today", "tomorrow"]):
            cal_ctx = self._get_calendar_events()
            if cal_ctx:
                context_blocks.append(cal_ctx)

        if context_blocks:
            injected_context = "\n\n---\n[LIVE SECOND BRAIN CONTEXT]\n" + "\n\n".join(context_blocks) + "\n---\n"
            messages[-1]["content"] = f"{injected_context}\nUser Question: {messages[-1]['content']}"

        return body
