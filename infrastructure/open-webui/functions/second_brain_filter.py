"""
title: Second Brain Context Auto-Injector
author: homelab
author_url: https://github.com/meek2100/homelab-infrastructure
git_url: https://github.com/meek2100/homelab-infrastructure
description: Automatically intercepts user chat messages and injects live Microsoft To Do lists, Google Calendar schedules, and Paprika meal plans into the prompt so any model has instant, zero-effort access.
version: 1.0.0
requirements: requests, pydantic
"""

import os
import glob
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
        VAULT_DIR: str = Field(
            default="/mnt/c/Users/dtheurer/Obsidian/Vault/Personal",
            description="Path to personal Obsidian vault root"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_access_token(self) -> str:
        token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        data = urllib.parse.urlencode({
            "client_id": self.valves.MS_TODO_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.valves.MS_TODO_REFRESH_TOKEN,
            "scope": "Tasks.ReadWrite offline_access"
        }).encode("utf-8")
        req = urllib.request.Request(token_url, data=data)
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode("utf-8"))["access_token"]

    def _get_ms_todo_items(self, list_query: str = "groceries") -> str:
        if not self.valves.MS_TODO_REFRESH_TOKEN:
            return ""
        try:
            access_token = self._get_access_token()
            req = urllib.request.Request(
                "https://graph.microsoft.com/v1.0/me/todo/lists",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
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
            with urllib.request.urlopen(req, timeout=30) as res:
                tasks = json.loads(res.read().decode("utf-8")).get("value", [])

            items = [f"- {t.get('title')}" for t in tasks]
            return f"Current {target['displayName']} in Microsoft To Do:\n" + ("\n".join(items) if items else "No open items.")
        except Exception as e:
            return f"[Error fetching To Do: {e}]"

    def _add_ms_todo_item(self, title: str, list_query: str = "groceries") -> str:
        try:
            access_token = self._get_access_token()
            req = urllib.request.Request(
                "https://graph.microsoft.com/v1.0/me/todo/lists",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
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
                return "Failed: list not found"

            payload = json.dumps({"title": title}).encode("utf-8")
            post_req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/todo/lists/{target['id']}/tasks",
                data=payload,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(post_req, timeout=30) as res:
                return f"Successfully added '{title}' to {target['displayName']} in Microsoft To Do."
        except Exception as e:
            return f"[Error adding item: {e}]"

    def _get_calendar_events(self, search_query: Optional[str] = None) -> str:
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
            end_time = (now + datetime.timedelta(days=14)).isoformat()

            events_result = service.events().list(
                calendarId=self.valves.CALENDAR_ID,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime",
                q=search_query
            ).execute()

            items = events_result.get("items", [])
            lines = []
            for ev in items:
                summary = ev.get("summary", "Untitled")
                start = ev.get("start", {})
                start_str = start.get("dateTime", start.get("date"))
                loc = f" at {ev.get('location')}" if ev.get("location") else ""
                lines.append(f"- {start_str}: {summary}{loc}")
            return f"Upcoming Google Family Calendar Events (Next 14 Days):\n" + ("\n".join(lines) if lines else "No events scheduled.")
        except Exception as e:
            return f"[Error fetching Calendar: {e}]"

    def _search_recipes(self, query: str) -> str:
        vault_path = os.path.join(self.valves.VAULT_DIR, "Recipes")
        if not os.path.exists(vault_path):
            vault_path = os.path.join(self.valves.VAULT_DIR, "Paprika")
        if not os.path.exists(vault_path):
            return ""
        q_words = [w for w in query.lower().split() if len(w) > 3 and w not in ["recipe", "make", "cook", "soup", "how"]]
        matched = []
        for fpath in glob.glob(os.path.join(vault_path, "*.md")):
            fname = os.path.basename(fpath).lower()
            if any(w in fname for w in q_words) or (q_words and any(w in fpath.lower() for w in q_words)):
                with open(fpath, encoding="utf-8") as f:
                    matched.append(f"### {os.path.basename(fpath)}\n" + f.read()[:2500])
                if len(matched) >= 2:
                    break
        if matched:
            return "Found Matching Recipes in Obsidian Vault:\n" + "\n---\n".join(matched)
        return ""

    def _get_maintenance_due(self, query: str = "") -> str:
        vault_path = os.path.join(self.valves.VAULT_DIR, "Maintenance")
        if not os.path.exists(vault_path):
            return ""
        entries = []
        q_lower = query.lower()
        for fpath in glob.glob(os.path.join(vault_path, "*.md")):
            fname = os.path.basename(fpath).lower()
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            # If specific query matches (e.g. car, tire, oil), prioritize it
            if any(w in fname or w in content.lower() for w in ["car", "tire", "vehicle", "oil", "service", "maintenance", "flush", "filter"]):
                entries.append(f"### {os.path.basename(fpath)}\n" + content[:1000])
        return "Upcoming Home & Vehicle Maintenance in Obsidian Vault:\n" + "\n\n".join(entries) if entries else ""

    async def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        messages = body.get("messages", [])
        if not messages:
            return body

        last_user_msg = messages[-1].get("content", "").lower()
        context_blocks = []

        # 1. Identity context
        context_blocks.append("Household Identity:\n- User/Owner: Darin Theurer ([[dtheurer]])\n- Household: Theurer Family\n- You are: Theurer Family Assistant, a private zero-cloud household intelligence co-pilot.")

        # 2. Add item to To Do list if requested (e.g. "add sugar-free tortonis syrup to grocery list")
        if any(w in last_user_msg for w in ["add ", "put "]) and any(w in last_user_msg for w in ["grocery", "groceries", "shopping", "list", "todo"]):
            # extract title
            clean = last_user_msg
            for phrase in ["add ", "put ", "to the grocery list", "to my grocery list", "to grocery list", "to our grocery list", "to the shopping list", "to shopping list", "to the list", "to my list", "on the list", "on the grocery list"]:
                clean = clean.replace(phrase, "")
            item_title = clean.strip(" \t\n.,\"'")
            if item_title:
                add_res = self._add_ms_todo_item(item_title, "groceries")
                context_blocks.append(f"Action Taken: {add_res}")

        # 3. Grocery / Shopping query
        if any(w in last_user_msg for w in ["grocer", "shopping", "buy", "store"]):
            todo_ctx = self._get_ms_todo_items("groceries")
            if todo_ctx:
                context_blocks.append(todo_ctx)

        # 4. Task / Todo query
        elif any(w in last_user_msg for w in ["task", "todo", "chore", "to-do"]):
            todo_ctx = self._get_ms_todo_items("tasks")
            if todo_ctx:
                context_blocks.append(todo_ctx)

        # 5. Calendar / Schedule query
        if any(w in last_user_msg for w in ["calendar", "schedule", "appointment", "event", "week", "today", "tomorrow", "dentist", "doctor", "flight", "going on"]):
            cal_ctx = self._get_calendar_events()
            if cal_ctx:
                context_blocks.append(cal_ctx)

        # 6. Recipe / Cooking query
        if any(w in last_user_msg for w in ["recipe", "soup", "cook", "dinner", "ingredient"]):
            recipe_ctx = self._search_recipes(last_user_msg)
            if recipe_ctx:
                context_blocks.append(recipe_ctx)

        # 7. Maintenance / Car / Vehicle query
        if any(w in last_user_msg for w in ["maintenance", "car", "vehicle", "tire", "oil", "service", "rotation"]):
            maint_ctx = self._get_maintenance_due(last_user_msg)
            if maint_ctx:
                context_blocks.append(maint_ctx)

        if context_blocks:
            injected_context = "\n\n---\n[LIVE SECOND BRAIN CONTEXT]\n" + "\n\n".join(context_blocks) + "\n---\n"
            messages[-1]["content"] = f"{injected_context}\nUser Question: {messages[-1]['content']}"

        return body
