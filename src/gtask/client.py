"""
Thin wrapper over the Google Tasks API.
"""

from __future__ import annotations

import datetime as _dt

from googleapiclient.discovery import build

from . import dates
from .auth import get_credentials


class Task:
    """
    A single Google task, with its due date parsed to a date.
    """

    def __init__(self, raw: dict, list_id: str, list_title: str):
        self.id = raw["id"]
        self.title = raw.get("title", "") or "(untitled)"
        self.notes = raw.get("notes", "")
        self.status = raw.get("status", "needsAction")
        self.list_id = list_id
        self.list_title = list_title
        due = raw.get("due")
        self.due: _dt.date | None = dates.from_rfc3339(due) if due else None

    @property
    def done(self) -> bool:
        return self.status == "completed"


class GTasks:
    """
    Tasks API operations for lists and tasks.
    """

    def __init__(self, creds=None):
        creds = creds or get_credentials()
        self._svc = build(
            "tasks", "v1", credentials=creds, cache_discovery=False
        )

    # --- lists ---
    def tasklists(self) -> list[dict]:
        items: list[dict] = []
        page = None
        while True:
            resp = (
                self._svc.tasklists()
                .list(maxResults=100, pageToken=page)
                .execute()
            )
            items.extend(resp.get("items", []))
            page = resp.get("nextPageToken")
            if not page:
                break
        return items

    def find_list(self, name: str) -> dict | None:
        low = name.lower()
        for tl in self.tasklists():
            if tl.get("title", "").lower() == low:
                return tl
        return None

    def create_list(self, name: str) -> dict:
        return self._svc.tasklists().insert(body={"title": name}).execute()

    # --- tasks ---
    def list_tasks(
        self, list_id: str, list_title: str, include_completed: bool = False
    ) -> list[Task]:
        items: list[Task] = []
        page = None
        while True:
            resp = (
                self._svc.tasks()
                .list(
                    tasklist=list_id,
                    showCompleted=include_completed,
                    showHidden=include_completed,
                    maxResults=100,
                    pageToken=page,
                )
                .execute()
            )
            for raw in resp.get("items", []):
                items.append(Task(raw, list_id, list_title))
            page = resp.get("nextPageToken")
            if not page:
                break
        return items

    def add_task(
        self,
        list_id: str,
        title: str,
        due: _dt.date | None = None,
        notes: str | None = None,
    ) -> dict:
        body: dict = {"title": title}
        if due:
            body["due"] = dates.to_rfc3339(due)
        if notes:
            body["notes"] = notes
        return self._svc.tasks().insert(tasklist=list_id, body=body).execute()

    def complete_task(self, list_id: str, task_id: str) -> dict:
        return (
            self._svc.tasks()
            .patch(
                tasklist=list_id, task=task_id, body={"status": "completed"}
            )
            .execute()
        )

    def delete_task(self, list_id: str, task_id: str) -> None:
        self._svc.tasks().delete(tasklist=list_id, task=task_id).execute()

    def update_task(
        self,
        list_id: str,
        task_id: str,
        title: str | None = None,
        notes: str | None = None,
        due: _dt.date | None = None,
    ) -> dict:
        body: dict = {}
        if title is not None:
            body["title"] = title
        if notes is not None:
            body["notes"] = notes
        if due is not None:
            body["due"] = dates.to_rfc3339(due)
        return (
            self._svc.tasks()
            .patch(tasklist=list_id, task=task_id, body=body)
            .execute()
        )
