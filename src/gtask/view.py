"""
Presentation helpers shared by the CLI and the TUI: human due labels,
task-tree ordering, link extraction, and the per-list colour palette.
"""

from __future__ import annotations

import datetime as _dt
import re

from .client import Task

# gruvbox accent hues, assigned to lists by position so each list keeps a
# stable colour across the sidebar and the task rows.
LIST_COLORS = (
    "#83a598",
    "#fabd2f",
    "#d3869b",
    "#b8bb26",
    "#fe8019",
    "#8ec07c",
    "#d65d0e",
)

_URL = re.compile(r"https?://[^\s<>)\]]+")


def list_color(index: int) -> str:
    return LIST_COLORS[index % len(LIST_COLORS)]


def first_url(*texts: str | None) -> str | None:
    """
    First http(s) URL found across the given texts, if any.
    """
    for text in texts:
        match = _URL.search(text or "")
        if match:
            return match.group(0).rstrip(".,;")
    return None


def due_label(due: _dt.date | None, today: _dt.date) -> str:
    if due is None:
        return ""
    if due == today:
        return "today"
    if due < today:
        return f"overdue {(today - due).days}d"
    if due == today + _dt.timedelta(days=1):
        return "tomorrow"
    return due.strftime("%d %b")


def order_tree(tasks: list[Task]) -> list[tuple[Task, int]]:
    """
    Order tasks per list as parents followed by their children (depth 1).
    """
    by_list: dict[str, list[Task]] = {}
    for task in tasks:
        by_list.setdefault(task.list_id, []).append(task)

    ordered: list[tuple[Task, int]] = []
    for items in by_list.values():
        ids = {t.id for t in items}
        children: dict[str, list[Task]] = {}
        tops: list[Task] = []
        for task in items:
            if task.parent and task.parent in ids:
                children.setdefault(task.parent, []).append(task)
            else:
                tops.append(task)
        for top in sorted(tops, key=lambda t: t.position):
            ordered.append((top, 0))
            kids = sorted(children.get(top.id, []), key=lambda t: t.position)
            ordered.extend((kid, 1) for kid in kids)
    return ordered


def due_today(tasks: list[Task], today: _dt.date) -> list[Task]:
    """
    Open overdue/today tasks, plus tasks completed today, across lists.
    """
    rows = [
        t
        for t in tasks
        if t.due is not None
        and not t.deleted
        and ((t.due <= today and not t.done) or t.due == today)
    ]
    rows.sort(key=lambda t: (t.due, t.list_title))
    return rows


def due_on(tasks: list[Task], day: _dt.date) -> list[Task]:
    """
    Open tasks due on a specific day, across lists.
    """
    rows = [t for t in tasks if t.due == day and not t.deleted and not t.done]
    rows.sort(key=lambda t: t.list_title)
    return rows
