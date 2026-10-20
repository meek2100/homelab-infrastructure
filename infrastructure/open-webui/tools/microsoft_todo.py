"""
title: Microsoft To Do & Groceries Manager
author: homelab
author_url: https://github.com/meek2100/homelab-infrastructure
git_url: https://github.com/meek2100/homelab-infrastructure
description: Add, complete, and view tasks and grocery items in Microsoft To Do lists directly from chat
version: 1.0.0
requirements: requests, pydantic
"""

import json
import urllib.request
import urllib.parse
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        CLIENT_ID: str = Field(
            default="8edff306-100e-49e9-b523-883a026dc633",
            description="Azure App Registration Application (client) ID"
        )
        REFRESH_TOKEN: str = Field(
            default="",
            description="OAuth Refresh Token for Microsoft To Do account (from ~/.config/homelab-todo/token_cache.json)"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_access_token(self) -> str:
        if not self.valves.CLIENT_ID or not self.valves.REFRESH_TOKEN:
            raise ValueError("Microsoft To Do CLIENT_ID or REFRESH_TOKEN is missing in Tool Valves.")

        token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        data = urllib.parse.urlencode({
            "client_id": self.valves.CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.valves.REFRESH_TOKEN,
            "scope": "Tasks.ReadWrite offline_access"
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=data)
        with urllib.request.urlopen(req, timeout=15) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            return res_data["access_token"]

    def _get_lists(self, access_token: str):
        req = urllib.request.Request(
            "https://graph.microsoft.com/v1.0/me/todo/lists",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("value", [])

    def _match_list(self, lists, query: Optional[str]):
        if not query:
            for l in lists:
                if "grocer" in l.get("displayName", "").lower():
                    return l
            return lists[0] if lists else None

        q = query.lower().strip()
        for l in lists:
            if l.get("displayName", "").lower() == q:
                return l
        for l in lists:
            if q in l.get("displayName", "").lower():
                return l
        return None

    def add_todo_item(
        self,
        title: str,
        list_name: str = "Home - Groceries",
        due_date: Optional[str] = None
    ) -> str:
        """
        Add a task, grocery item, or chore to a Microsoft To Do list.
        :param title: The item or task description (e.g. "Milk", "Tomatoes", "Change engine oil").
        :param list_name: Target list name or keyword (e.g. "Home - Groceries", "Home - Todo List", "Groceries", "Tasks"). Defaults to "Home - Groceries".
        :param due_date: Optional due date in YYYY-MM-DD format (e.g. "2026-10-27").
        :return: Confirmation of the created task.
        """
        try:
            token = self._get_access_token()
            lists = self._get_lists(token)
            target = self._match_list(lists, list_name)

            if not target:
                return f"Error: Could not find any list matching '{list_name}'. Available: {', '.join(l['displayName'] for l in lists)}"

            payload = {"title": title}
            if due_date:
                payload["dueDateTime"] = {
                    "dateTime": f"{due_date}T00:00:00Z",
                    "timeZone": "UTC"
                }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/todo/lists/{target['id']}/tasks",
                data=data,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as res:
                created = json.loads(res.read().decode("utf-8"))
                due_info = f" with due date {due_date}" if due_date else ""
                return f"Successfully added '{title}'{due_info} to '{target['displayName']}' in Microsoft To Do!"
        except Exception as e:
            return f"Failed to add task to Microsoft To Do: {str(e)}"

    def complete_todo_item(
        self,
        title: str,
        list_name: Optional[str] = None
    ) -> str:
        """
        Mark an existing task or grocery item as completed.
        :param title: Name or keyword of the task to complete (e.g. "Milk").
        :param list_name: Optional list to search in. If omitted, searches "Home - Groceries" first.
        :return: Confirmation of completion.
        """
        try:
            token = self._get_access_token()
            lists = self._get_lists(token)
            target = self._match_list(lists, list_name)

            if not target:
                return f"Error: Could not find list matching '{list_name}'."

            encoded_filter = urllib.parse.quote("status ne 'completed'")
            req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/todo/lists/{target['id']}/tasks?$filter={encoded_filter}",
                headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req, timeout=15) as res:
                tasks = json.loads(res.read().decode("utf-8")).get("value", [])

            q = title.lower()
            matched = None
            for t in tasks:
                if q in t.get("title", "").lower():
                    matched = t
                    break

            if not matched:
                return f"No open task matching '{title}' was found in '{target['displayName']}'."

            patch_data = json.dumps({"status": "completed"}).encode("utf-8")
            patch_req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/todo/lists/{target['id']}/tasks/{matched['id']}",
                data=patch_data,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="PATCH"
            )
            with urllib.request.urlopen(patch_req, timeout=15) as res:
                return f"Marked '{matched['title']}' as completed in '{target['displayName']}'!"
        except Exception as e:
            return f"Failed to complete task: {str(e)}"

    def get_grocery_list(self) -> str:
        """
        View current open items on the family grocery list.
        :return: Formatted list of open grocery items.
        """
        return self.get_todo_items(list_name="Home - Groceries")

    def get_groceries(self) -> str:
        """
        View current items on the grocery list.
        :return: Formatted list of open grocery items.
        """
        return self.get_todo_items(list_name="Home - Groceries")

    def search_todo_items(
        self,
        query: Optional[str] = None,
        list_name: Optional[str] = "Home - Groceries"
    ) -> str:
        """
        Search or view items on a task or grocery list.
        :param query: Optional search term.
        :param list_name: Target list name (defaults to 'Home - Groceries').
        :return: Formatted list of items.
        """
        return self.get_todo_items(list_name=list_name or "Home - Groceries")

    def get_todo_items(
        self,
        list_name: str = "Home - Groceries",
        show_completed: bool = False
    ) -> str:
        """
        View current items on a task or grocery list in Microsoft To Do.
        :param list_name: Target list name or keyword (e.g. "Home - Groceries", "Groceries", "Tasks", "Family"). Defaults to "Home - Groceries".
        :param show_completed: Whether to include already completed items (default False).
        :return: Formatted list of open tasks/groceries.
        """
        try:
            token = self._get_access_token()
            lists = self._get_lists(token)
            target = self._match_list(lists, list_name)

            if not target:
                return f"Error: Could not find list matching '{list_name}'. Available: {', '.join(l['displayName'] for l in lists)}"

            filter_clause = "" if show_completed else "?$filter=" + urllib.parse.quote("status ne 'completed'")
            req = urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/me/todo/lists/{target['id']}/tasks{filter_clause}",
                headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req, timeout=15) as res:
                tasks = json.loads(res.read().decode("utf-8")).get("value", [])

            if not tasks:
                return f"No open items found on '{target['displayName']}'."

            lines = [f"📋 Items on '{target['displayName']}':"]
            for t in tasks:
                due = f" (Due: {t['dueDateTime']['dateTime'][:10]})" if t.get("dueDateTime") else ""
                lines.append(f"• {t.get('title')}{due}")

            return "\n".join(lines)
        except Exception as e:
            return f"Failed to get tasks: {str(e)}"

    def list_todo_lists(self) -> str:
        """
        Get all available Microsoft To Do list names.
        :return: Formatted list of task list names.
        """
        try:
            token = self._get_access_token()
            lists = self._get_lists(token)
            names = [l['displayName'] for l in lists]
            return f"Your Microsoft To Do lists: {', '.join(names)}"
        except Exception as e:
            return f"Failed to fetch lists: {str(e)}"
