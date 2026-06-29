"""
Command line interface for gtask, built with Typer and Rich.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Optional

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import dates, store, view

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="Manage Google Tasks from the terminal.",
)
lists_app = typer.Typer(help="Manage task lists.")
app.add_typer(lists_app, name="lists")

console = Console()
err = Console(stderr=True)


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context):
    """
    Open the interactive TUI when no subcommand is given.
    """
    if ctx.invoked_subcommand is not None:
        return
    from .tui import run

    run()


def _client():
    # Imported lazily so `gtask --help` works without network or credentials.
    from .client import GTasks

    return GTasks()


def _resolve_list(g, name: str, assume_yes: bool = False):
    tl = g.find_list(name)
    if tl:
        return tl
    if not assume_yes and not typer.confirm(
        f"List '{name}' does not exist. Create it?"
    ):
        raise typer.Abort()
    return g.create_list(name)


def _require_list(g, name: str):
    tl = g.find_list(name)
    if not tl:
        err.print(f"[red]No list named '{name}'[/red]")
        raise typer.Exit(1)
    return tl


def _parse_date(value: str) -> _dt.date:
    try:
        return dates.parse_due(value)
    except ValueError as e:
        err.print(f"[red]Bad date:[/red] {e}")
        raise typer.Exit(1) from e


def _lookup(n: int) -> dict:
    row = store.lookup(n)
    if not row:
        err.print(f"[red]No task #{n}.[/red] Run `gtask ls` first.")
        raise typer.Exit(1)
    return row


def _gather(g, list_name, show_done, show_deleted):
    """
    Collect tasks from one named list or all lists.
    """
    target = [_require_list(g, list_name)] if list_name else g.tasklists()
    tasks = []
    for tl in target:
        tasks.extend(
            g.list_tasks(
                tl["id"],
                tl["title"],
                include_completed=show_done,
                include_deleted=show_deleted,
            )
        )
    return tasks


def _ordered(tasks, full, today):
    """
    Default view is today and overdue, flat. Full view is the tree.
    """
    if full:
        return view.order_tree(tasks)
    due_open = [
        t for t in tasks if t.due is not None and t.due <= today and not t.done
    ]
    due_open.sort(key=lambda t: (t.due or today, t.list_title))
    return [(t, 0) for t in due_open]


def _cache(ordered):
    """
    Remember the numbering so done/rm/edit/move can resolve a number.
    """
    store.save(
        [
            {
                "n": n,
                "list_id": t.list_id,
                "list_title": t.list_title,
                "task_id": t.id,
                "title": t.title,
                "due": t.due.isoformat() if t.due else None,
            }
            for n, (t, _depth) in enumerate(ordered, start=1)
        ]
    )


def _as_json(ordered):
    return json.dumps(
        [
            {
                "id": t.id,
                "list": t.list_title,
                "title": t.title,
                "notes": t.notes,
                "due": t.due.isoformat() if t.due else None,
                "status": t.status,
                "parent": t.parent,
            }
            for t, _depth in ordered
        ]
    )


def _render(ordered, today):
    table = Table(
        show_header=True, header_style="bold", box=None, pad_edge=False
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Due")
    table.add_column("List", style="cyan")
    table.add_column("Task")
    for n, (t, depth) in enumerate(ordered, start=1):
        overdue = t.due is not None and t.due < today and not t.done
        due_text = view.due_label(t.due, today)
        due_cell = f"[red]{due_text}[/red]" if overdue else due_text
        title = ("  " * depth) + escape(t.title)
        if t.deleted or t.done:
            title = f"[dim strike]{title}[/dim strike]"
        table.add_row(str(n), due_cell, t.list_title, title)
    console.print(table)


@app.command()
def add(
    text: str = typer.Argument(..., help="task text"),
    date: Optional[str] = typer.Argument(
        None, help="due date: 22, 22-06, or 22-06-2026"
    ),
    list_name: Optional[str] = typer.Option(
        None, "-l", "--list", help="target list (created on demand)"
    ),
    notes: Optional[str] = typer.Option(
        None, "-n", "--notes", help="description / notes"
    ),
    under: Optional[int] = typer.Option(
        None, "-u", "--under", help="make it a subtask of this ls number"
    ),
    yes: bool = typer.Option(
        False, "-y", "--yes", help="create the list without prompting"
    ),
):
    """
    Add a task, optionally as a subtask of another.
    """
    g = _client()
    parent_id = None
    if under is not None:
        prow = _lookup(under)
        list_id, list_title = prow["list_id"], prow["list_title"]
        parent_id = prow["task_id"]
    elif list_name:
        tl = _resolve_list(g, list_name, yes)
        list_id, list_title = tl["id"], tl["title"]
    else:
        tl = g.tasklists()[0]
        list_id, list_title = tl["id"], tl["title"]

    due = _parse_date(date) if date else None
    g.add_task(list_id, text, due, notes, parent=parent_id)
    when = (
        f"  [dim]({view.due_label(due, _dt.date.today())})[/dim]"
        if due
        else ""
    )
    console.print(
        f"Added to [bold]{escape(list_title)}[/bold]: {escape(text)}{when}"
    )


@app.command()
def ls(
    list_name: Optional[str] = typer.Option(
        None, "-l", "--list", help="limit to one list"
    ),
    all: bool = typer.Option(False, "--all", help="show every open task"),
    show_done: bool = typer.Option(
        False, "--done", help="include completed tasks"
    ),
    show_deleted: bool = typer.Option(
        False, "--deleted", help="include deleted tasks"
    ),
    json_out: bool = typer.Option(
        False, "--json", help="output JSON (id, list, title, notes, due)"
    ),
):
    """
    List tasks. Default shows today and overdue across lists.
    """
    g = _client()
    today = _dt.date.today()
    full = all or show_done or show_deleted
    ordered = _ordered(
        _gather(g, list_name, show_done, show_deleted), full, today
    )
    _cache(ordered)

    if json_out:
        print(_as_json(ordered))
        return
    if not ordered:
        console.print("[dim]Nothing to show.[/dim]")
        return
    _render(ordered, today)


@app.command()
def show(n: int = typer.Argument(..., help="task number from the last ls")):
    """
    Show one task in full, with its subtasks.
    """
    row = _lookup(n)
    g = _client()
    t = g.get_task(row["list_id"], row["task_id"], row["list_title"])
    today = _dt.date.today()

    console.print(f"[bold]{escape(t.title)}[/bold]")
    console.print(f"[dim]List:[/dim] {escape(t.list_title)}")
    console.print(f"[dim]Status:[/dim] {t.status}")
    if t.due:
        console.print(f"[dim]Due:[/dim] {view.due_label(t.due, today)}")
    if t.notes:
        console.print(f"[dim]Notes:[/dim] {escape(t.notes)}")
    if t.web_view_link:
        console.print(f"[dim]Link:[/dim] {t.web_view_link}")

    subs = [
        s
        for s in g.list_tasks(
            row["list_id"], row["list_title"], include_completed=True
        )
        if s.parent == t.id
    ]
    if subs:
        console.print("[dim]Subtasks:[/dim]")
        for s in sorted(subs, key=lambda s: s.position):
            mark = "x" if s.done else " "
            console.print(f"  [{mark}] {escape(s.title)}")


@app.command()
def done(n: int = typer.Argument(..., help="task number from the last ls")):
    """
    Complete a task by its ls number.
    """
    row = _lookup(n)
    _client().complete_task(row["list_id"], row["task_id"])
    console.print(f"[green]Done:[/green] {escape(row['title'])}")


@app.command()
def reopen(n: int = typer.Argument(..., help="task number from the last ls")):
    """
    Reopen a completed task by its ls number.
    """
    row = _lookup(n)
    _client().reopen_task(row["list_id"], row["task_id"])
    console.print(f"Reopened: {escape(row['title'])}")


@app.command()
def edit(
    n: int = typer.Argument(..., help="task number from the last ls"),
    text: Optional[str] = typer.Option(None, "-t", "--text", help="new text"),
    notes: Optional[str] = typer.Option(
        None, "-n", "--notes", help="new description / notes"
    ),
    date: Optional[str] = typer.Option(
        None, "-d", "--date", help="new due date"
    ),
):
    """
    Update a task's text, notes, or due date by its ls number.
    """
    if text is None and notes is None and date is None:
        err.print(
            "[red]Nothing to update.[/red] Pass --text, --notes, or --date."
        )
        raise typer.Exit(1)
    row = _lookup(n)
    due = _parse_date(date) if date else None
    _client().update_task(
        row["list_id"], row["task_id"], title=text, notes=notes, due=due
    )
    console.print(f"Updated: {escape(text or row['title'])}")


@app.command()
def move(
    n: int = typer.Argument(..., help="task number from the last ls"),
    under: Optional[int] = typer.Option(
        None, "-u", "--under", help="make it a subtask of this ls number"
    ),
    top: bool = typer.Option(
        False, "--top", help="move to the top level (no parent)"
    ),
    after: Optional[int] = typer.Option(
        None, "-a", "--after", help="position after this ls number"
    ),
    to: Optional[str] = typer.Option(
        None, "--to", help="move to another list by name"
    ),
):
    """
    Reorder, reparent, or move a task to another list.
    """
    if under is not None and top:
        err.print("[red]Use either --under or --top, not both.[/red]")
        raise typer.Exit(1)
    row = _lookup(n)
    g = _client()

    destination = _require_list(g, to)["id"] if to else None
    parent = _lookup(under)["task_id"] if under is not None else None
    previous = _lookup(after)["task_id"] if after is not None else None

    g.move_task(
        row["list_id"],
        row["task_id"],
        parent=parent,
        previous=previous,
        destination=destination,
    )
    console.print(f"Moved: {escape(row['title'])}")


@app.command()
def rm(
    n: Optional[int] = typer.Argument(
        None, help="task number from the last ls"
    ),
    task_id: Optional[str] = typer.Option(
        None, "--id", help="delete by Google task id (needs --list)"
    ),
    list_name: Optional[str] = typer.Option(
        None, "-l", "--list", help="list to use with --id"
    ),
):
    """
    Delete a task by its ls number, or by --id with --list.
    """
    if task_id:
        if not list_name:
            err.print("[red]--id requires --list.[/red]")
            raise typer.Exit(1)
        g = _client()
        tl = _require_list(g, list_name)
        g.delete_task(tl["id"], task_id)
        console.print(f"Deleted task {task_id}")
        return
    if n is None:
        err.print("[red]Pass a task number, or --id with --list.[/red]")
        raise typer.Exit(1)
    row = _lookup(n)
    _client().delete_task(row["list_id"], row["task_id"])
    console.print(f"Deleted: {escape(row['title'])}")


@app.command()
def clear(
    list_name: Optional[str] = typer.Option(
        None, "-l", "--list", help="limit to one list (default: all lists)"
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="do not prompt"),
):
    """
    Remove completed tasks from a list, or from every list.
    """
    g = _client()
    targets = [_require_list(g, list_name)] if list_name else g.tasklists()
    where = list_name or "all lists"
    if not yes and not typer.confirm(f"Clear completed tasks from {where}?"):
        raise typer.Abort()
    for tl in targets:
        g.clear_completed(tl["id"])
    console.print(f"Cleared completed from {where}.")


@app.command()
def login():
    """
    Run the one-time browser authorization.
    """
    from .auth import get_credentials

    get_credentials()
    console.print("[green]Authorized.[/green] Token cached.")


@lists_app.callback(invoke_without_command=True)
def lists_main(ctx: typer.Context):
    """
    Show task lists, or manage them with a subcommand.
    """
    if ctx.invoked_subcommand is not None:
        return
    for tl in _client().tasklists():
        console.print(tl.get("title", "(untitled)"))


@lists_app.command("add")
def lists_add(name: str = typer.Argument(..., help="new list name")):
    """
    Create a task list.
    """
    _client().create_list(name)
    console.print(f"Created list: {escape(name)}")


@lists_app.command("rename")
def lists_rename(
    old: str = typer.Argument(..., help="current name"),
    new: str = typer.Argument(..., help="new name"),
):
    """
    Rename a task list.
    """
    g = _client()
    tl = _require_list(g, old)
    g.rename_list(tl["id"], new)
    console.print(f"Renamed {escape(old)} to {escape(new)}")


@lists_app.command("rm")
def lists_rm(
    name: str = typer.Argument(..., help="list name"),
    yes: bool = typer.Option(False, "-y", "--yes", help="do not prompt"),
):
    """
    Delete a task list and everything in it.
    """
    g = _client()
    tl = _require_list(g, name)
    if not yes and not typer.confirm(
        f"Delete list '{name}' and all its tasks?"
    ):
        raise typer.Abort()
    g.delete_list(tl["id"])
    console.print(f"Deleted list: {escape(name)}")


def main():
    app()


if __name__ == "__main__":
    main()
