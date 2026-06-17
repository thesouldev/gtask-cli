"""
Command line interface for gtask, built with Typer and Rich.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import dates, store

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manage Google Tasks from the terminal.",
)
console = Console()
err = Console(stderr=True)


def _client():
    # Imported lazily so `gtask --help` works without network or credentials.
    from .client import GTasks

    return GTasks()


def _due_label(due: Optional[_dt.date], today: _dt.date) -> str:
    if due is None:
        return ""
    if due == today:
        return "today"
    if due < today:
        return f"overdue {(today - due).days}d"
    return due.strftime("%d %b")


def _resolve_list(g, name: str):
    tl = g.find_list(name)
    if tl:
        return tl
    if not typer.confirm(f"List '{name}' does not exist. Create it?"):
        raise typer.Abort()
    return g.create_list(name)


@app.command()
def add(
    text: str = typer.Argument(..., help="task text"),
    date: Optional[str] = typer.Argument(
        None, help="due date: 22, 22-06, or 22-06-2026"
    ),
    list_name: Optional[str] = typer.Option(
        None, "-l", "--list", help="target list (created on demand)"
    ),
):
    """
    Add a task.
    """
    g = _client()
    tl = _resolve_list(g, list_name) if list_name else g.tasklists()[0]

    due = None
    if date:
        try:
            due = dates.parse_due(date)
        except ValueError as e:
            err.print(f"[red]Bad date:[/red] {e}")
            raise typer.Exit(1) from e

    g.add_task(tl["id"], text, due)
    when = f"  [dim]({_due_label(due, _dt.date.today())})[/dim]" if due else ""
    console.print(f"Added to [bold]{tl['title']}[/bold]: {text}{when}")


@app.command()
def ls(
    list_name: Optional[str] = typer.Option(
        None, "-l", "--list", help="limit to one list"
    ),
    all: bool = typer.Option(False, "--all", help="show every open task"),
):
    """
    List open tasks. Default shows today and overdue across lists.
    """
    g = _client()
    today = _dt.date.today()

    target_lists = g.tasklists()
    if list_name:
        target_lists = [
            tl
            for tl in target_lists
            if tl.get("title", "").lower() == list_name.lower()
        ]
        if not target_lists:
            err.print(f"[red]No list named '{list_name}'[/red]")
            raise typer.Exit(1)

    tasks = []
    for tl in target_lists:
        tasks.extend(
            g.list_tasks(tl["id"], tl["title"], include_completed=False)
        )

    if not all:
        tasks = [t for t in tasks if t.due is not None and t.due <= today]

    tasks.sort(key=lambda t: (t.due is None, t.due or today, t.list_title))

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
            for n, t in enumerate(tasks, start=1)
        ]
    )

    if not tasks:
        console.print(
            "[dim]Nothing due.[/dim]"
            if not all
            else "[dim]No open tasks.[/dim]"
        )
        return

    table = Table(
        show_header=True, header_style="bold", box=None, pad_edge=False
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Due")
    table.add_column("List", style="cyan")
    table.add_column("Task")
    for n, t in enumerate(tasks, start=1):
        overdue = t.due is not None and t.due < today
        due_text = _due_label(t.due, today)
        due_cell = f"[red]{due_text}[/red]" if overdue else due_text
        table.add_row(str(n), due_cell, t.list_title, t.title)
    console.print(table)


@app.command()
def done(n: int = typer.Argument(..., help="task number from the last ls")):
    """
    Complete a task by its ls number.
    """
    row = store.lookup(n)
    if not row:
        err.print(f"[red]No task #{n}.[/red] Run `gtask ls` first.")
        raise typer.Exit(1)
    _client().complete_task(row["list_id"], row["task_id"])
    console.print(f"[green]Done:[/green] {row['title']}")


@app.command()
def rm(n: int = typer.Argument(..., help="task number from the last ls")):
    """
    Delete a task by its ls number.
    """
    row = store.lookup(n)
    if not row:
        err.print(f"[red]No task #{n}.[/red] Run `gtask ls` first.")
        raise typer.Exit(1)
    _client().delete_task(row["list_id"], row["task_id"])
    console.print(f"Deleted: {row['title']}")


@app.command()
def lists():
    """
    Show task lists.
    """
    for tl in _client().tasklists():
        console.print(tl.get("title", "(untitled)"))


@app.command()
def login():
    """
    Run the one-time browser authorization.
    """
    from .auth import get_credentials

    get_credentials()
    console.print("[green]Authorized.[/green] Token cached.")


def main():
    app()


if __name__ == "__main__":
    main()
