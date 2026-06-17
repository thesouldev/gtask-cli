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
    A read-only view over a raw Google task plus its list context.

    The raw API dict is the single source of truth; fields are exposed as
    properties so there is no duplicated parsing or stale state.
    """

    def __init__(self, raw: dict, list_id: str, list_title: str):
        self._raw = raw
        self.list_id = list_id
        self.list_title = list_title

    @property
    def id(self) -> str:
        return self._raw["id"]

    @property
    def title(self) -> str:
        return self._raw.get("title", "") or "(untitled)"

    @property
    def notes(self) -> str:
        return self._raw.get("notes", "")

    @property
    def status(self) -> str:
        return self._raw.get("status", "needsAction")

    @property
    def parent(self) -> str | None:
        return self._raw.get("parent")

    @property
    def position(self) -> str:
        return self._raw.get("position", "")

    @property
    def deleted(self) -> bool:
        return bool(self._raw.get("deleted", False))

    @property
    def web_view_link(self) -> str:
        return self._raw.get("webViewLink", "")

    @property
    def due(self) -> _dt.date | None:
        raw_due = self._raw.get("due")
        return dates.from_rfc3339(raw_due) if raw_due else None

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

    def rename_list(self, list_id: str, name: str) -> dict:
        return (
            self._svc.tasklists()
            .patch(tasklist=list_id, body={"title": name})
            .execute()
        )

    def delete_list(self, list_id: str) -> None:
        self._svc.tasklists().delete(tasklist=list_id).execute()

    # --- tasks ---
    def list_tasks(
        self,
        list_id: str,
        list_title: str,
        include_completed: bool = False,
        include_deleted: bool = False,
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
                    showDeleted=include_deleted,
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

    def get_task(
        self, list_id: str, task_id: str, list_title: str = ""
    ) -> Task:
        raw = self._svc.tasks().get(tasklist=list_id, task=task_id).execute()
        return Task(raw, list_id, list_title)

    def add_task(
        self,
        list_id: str,
        title: str,
        due: _dt.date | None = None,
        notes: str | None = None,
        parent: str | None = None,
    ) -> dict:
        body: dict = {"title": title}
        if due:
            body["due"] = dates.to_rfc3339(due)
        if notes:
            body["notes"] = notes
        return (
            self._svc.tasks()
            .insert(tasklist=list_id, body=body, parent=parent)
            .execute()
        )

    def complete_task(self, list_id: str, task_id: str) -> dict:
        return (
            self._svc.tasks()
            .patch(
                tasklist=list_id, task=task_id, body={"status": "completed"}
            )
            .execute()
        )

    def reopen_task(self, list_id: str, task_id: str) -> dict:
        return (
            self._svc.tasks()
            .patch(
                tasklist=list_id,
                task=task_id,
                body={"status": "needsAction"},
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

    def move_task(
        self,
        list_id: str,
        task_id: str,
        parent: str | None = None,
        previous: str | None = None,
        destination: str | None = None,
    ) -> dict:
        return (
            self._svc.tasks()
            .move(
                tasklist=list_id,
                task=task_id,
                parent=parent,
                previous=previous,
                destinationTasklist=destination,
            )
            .execute()
        )

    def clear_completed(self, list_id: str) -> None:
        self._svc.tasks().clear(tasklist=list_id).execute()
