"""
Reusable widgets and the gruvbox palette for the TUI's add/edit form.
"""

from __future__ import annotations

import datetime as _dt

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalScroll, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from . import dates, view
from .client import Task

# gruvbox palette, by role.
FG = "#ebdbb2"
DIM = "#928374"
FAINT = "#7c6f64"
RED = "#fb4934"
YELLOW = "#fabd2f"
AQUA = "#8ec07c"
BLUE = "#83a598"
GREEN = "#b8bb26"

EMPTY_ART = "╰( ◜◡◝ )╯"


def empty_state(is_today: bool) -> Text:
    """
    The calm placeholder shown when a view has no tasks at all.
    """
    message = "Nothing due today." if is_today else "Nothing here."
    text = Text(justify="center")
    text.append(EMPTY_ART + "\n\n", style=FAINT)
    text.append(message + "\n", style="#d5c4a1")
    text.append("Press a to add a task.", style=FAINT)
    return text


def celebration(count: int) -> Text:
    """
    The reward shown when every task due today has been completed.
    """
    text = Text(justify="center")
    text.append("＼(´▽`)／\n\n", style=GREEN)
    text.append("All done for today\n\n", style=f"bold {GREEN}")
    text.append(f"{count} of {count} tasks complete\n", style=GREEN)
    text.append(
        "You cleared everything on your plate. Go enjoy the quiet.\n\n",
        style=FAINT,
    )
    text.append("Press a to plan tomorrow.", style=FAINT)
    return text


def parse_due_input(value: str, today: _dt.date) -> _dt.date | None:
    """
    Parse the add/edit due field: words, a blank, or the CLI date syntax.
    """
    text = (value or "").strip().lower()
    if text in ("", "today"):
        return today
    if text in ("tomorrow", "tmrw", "tom"):
        return today + _dt.timedelta(days=1)
    if text in ("none", "no", "-"):
        return None
    return dates.parse_due(value, today)


class ConfirmDelete(ModalScreen):
    """
    A small red confirmation box; dismisses True to delete, False to cancel.
    """

    BINDINGS = [
        Binding("enter", "confirm", show=False),
        Binding("escape", "cancel", show=False),
        Binding("q", "cancel", show=False),
    ]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm"):
            yield Static(Text(self._title, style=f"bold {RED}"))
            yield Static(Text(self._body, style=FAINT), classes="confirm-body")
            yield Static(
                Text.assemble(
                    ("Enter", RED),
                    (" delete · ", FAINT),
                    ("Esc", FAINT),
                    (" cancel", FAINT),
                )
            )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class Chip(Static):
    """
    A clickable option in the task form: a due preset or a list name.
    """

    class Picked(Message):
        """
        Posted when a chip is clicked, carrying its group and value.
        """

        def __init__(self, group: str, value: str) -> None:
            self.group = group
            self.value = value
            super().__init__()

    def __init__(self, label: str, group: str, value: str) -> None:
        super().__init__(label, classes="chip")
        self.group = group
        self.option_value = value

    def on_click(self) -> None:
        self.post_message(self.Picked(self.group, self.option_value))


class ListChooser(HorizontalScroll):
    """
    Focusable row of list names; h/l cycles the target list and scrolls the
    selection into view when the lists overflow the row.
    """

    can_focus = True
    BINDINGS = [
        Binding("left", "prev", show=False),
        Binding("h", "prev", show=False),
        Binding("right", "next", show=False),
        Binding("l", "next", show=False),
    ]

    class Changed(Message):
        """
        Posted when the selected list changes, carrying its id.
        """

        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    def __init__(self, lists: list[dict], value: str) -> None:
        super().__init__(classes="chooser")
        self._lists = lists
        self.index = next(
            (i for i, it in enumerate(lists) if it["id"] == value), 0
        )

    def compose(self) -> ComposeResult:
        for item in self._lists:
            yield Chip(item["title"], "list", item["id"])

    def on_mount(self) -> None:
        self._sync()

    def on_chip_picked(self, event: Chip.Picked) -> None:
        self.select(event.value)
        event.stop()

    @property
    def value(self) -> str:
        return self._lists[self.index]["id"]

    def action_prev(self) -> None:
        self.index = (self.index - 1) % len(self._lists)
        self._sync()

    def action_next(self) -> None:
        self.index = (self.index + 1) % len(self._lists)
        self._sync()

    def select(self, list_id: str) -> None:
        self.index = next(
            (i for i, it in enumerate(self._lists) if it["id"] == list_id),
            self.index,
        )
        self._sync()

    def _sync(self) -> None:
        chips = list(self.query(Chip))
        for i, chip in enumerate(chips):
            chip.set_class(i == self.index, "list-active")
        chips[self.index].scroll_visible(animate=True)
        self.post_message(self.Changed(self.value))


class DueField(Horizontal):
    """
    Focusable due picker: h/l cycles today / tomorrow / custom. Typing a
    date switches to custom; an empty custom means no due date.
    """

    can_focus = True
    PRESETS = ("today", "tomorrow", "custom")
    BINDINGS = [
        Binding("left", "prev", show=False),
        Binding("h", "prev", show=False),
        Binding("right", "next", show=False),
        Binding("l", "next", show=False),
        Binding("backspace", "backspace", show=False),
    ]

    class Changed(Message):
        """
        Posted whenever the due selection or typed value changes.
        """

    def __init__(self, today: _dt.date, initial: str) -> None:
        super().__init__(classes="chooser duefield")
        self._today = today
        if initial in ("today", "tomorrow"):
            self.index = self.PRESETS.index(initial)
            self._buffer = ""
        else:
            self.index = 2
            self._buffer = (
                "" if initial in ("", "none", "no", "-") else initial
            )

    def compose(self) -> ComposeResult:
        for preset in self.PRESETS:
            yield Chip(preset, "due", preset)
        yield Static("·", classes="sep")
        yield Static("", id="due_value", classes="due-value")
        yield Static("", id="due_preview", classes="preview")

    def on_mount(self) -> None:
        self._sync()

    def on_chip_picked(self, event: Chip.Picked) -> None:
        self.index = self.PRESETS.index(event.value)
        self._sync()
        event.stop()

    def on_focus(self) -> None:
        self._sync()

    def on_blur(self) -> None:
        self._sync()

    def on_key(self, event: events.Key) -> None:
        char = event.character
        if char and (char.isdigit() or char in "-/."):
            self.index = 2
            self._buffer += char
            self._sync()
            event.stop()

    @property
    def preset(self) -> str:
        return self.PRESETS[self.index]

    def value(self) -> str:
        if self.preset == "custom":
            return self._buffer or "none"
        return self.preset

    def action_prev(self) -> None:
        self.index = (self.index - 1) % len(self.PRESETS)
        self._sync()

    def action_next(self) -> None:
        self.index = (self.index + 1) % len(self.PRESETS)
        self._sync()

    def action_backspace(self) -> None:
        if self.preset == "custom" and self._buffer:
            self._buffer = self._buffer[:-1]
            self._sync()

    def _sync(self) -> None:
        for i, chip in enumerate(self.query(Chip)):
            chip.set_class(i == self.index, "active")
        cursor = "█" if self.has_focus and self.preset == "custom" else ""
        shown = self._buffer + cursor if self.preset == "custom" else ""
        self.query_one("#due_value", Static).update(Text(shown, style=YELLOW))
        try:
            due = parse_due_input(self.value(), self._today)
            text = "→ no date" if due is None else f"→ {due:%d %b %Y}"
            style = FAINT
        except ValueError:
            text, style = "→ ?", RED
        self.query_one("#due_preview", Static).update(Text(text, style=style))
        self.post_message(self.Changed())


def _kv(label: str, value: Text) -> Text:
    line = Text()
    line.append(f"{label:<9}", style=FAINT)
    line.append_text(value)
    return line


class DetailScreen(ModalScreen):
    """
    Read a single task in full, with its notes and links.
    """

    BINDINGS = [
        Binding("q", "close", "Back"),
        Binding("escape", "close", show=False),
        Binding("e", "edit", "Edit"),
        Binding("space", "done", "Toggle done"),
        Binding("x", "done", show=False),
        Binding("o", "open", "Open link"),
    ]

    def __init__(self, task: Task, today) -> None:
        super().__init__()
        self._task_obj = task
        self._today = today

    def compose(self) -> ComposeResult:
        task = self._task_obj
        head = Text()
        head.append("[x] " if task.done else "[ ] ", style=AQUA)
        head.append(task.title, style=FG)

        rows = [
            _kv("list", Text(task.list_title, style=AQUA)),
            _kv("status", Text(task.status, style=BLUE)),
            _kv(
                "due",
                Text(view.due_label(task.due, self._today), style=YELLOW),
            ),
        ]
        notes = task.notes or "(no notes)"
        url = view.first_url(task.notes, task.web_view_link)
        hint = f"o  open {url}" if url else "no link in this task"

        with Vertical(id="detail"):
            yield Static(head, id="detail-title")
            for row in rows:
                yield Static(row)
            yield Static(Text("notes", style=FAINT), classes="section")
            yield Static(Text(notes, style="#d5c4a1"))
            yield Static(Text(hint, style=BLUE), classes="section")

    def action_close(self) -> None:
        self.dismiss(None)

    def action_edit(self) -> None:
        self.dismiss("edit")

    def action_done(self) -> None:
        self.dismiss("done")

    def action_open(self) -> None:
        self.app.open_current_link()


class HelpScreen(ModalScreen):
    """
    The keymap, mirrored from the footer hint bar.
    """

    BINDINGS = [
        Binding("question_mark", "close", show=False),
        Binding("q", "close", show=False),
        Binding("escape", "close", show=False),
    ]

    ROWS = [
        ("Tab / ⇧Tab", "switch pane"),
        ("j / k", "down / up"),
        ("g / G", "top / bottom"),
        ("Enter", "open detail / list"),
        ("Space", "toggle done"),
        ("o", "open URL in browser"),
        ("a", "add task / new list"),
        ("e", "edit task / rename list"),
        ("d / x", "delete task / list"),
        ("/", "search"),
        ("r", "refresh"),
        ("? / q", "help / quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help"):
            yield Static(Text("Keyboard", style=f"bold {YELLOW}"))
            for key, desc in self.ROWS:
                line = Text()
                line.append(f"{key:<13}", style=BLUE)
                line.append(desc, style=FG)
                yield Static(line)

    def action_close(self) -> None:
        self.dismiss(None)


class SearchInput(Input):
    """
    Filter box for the tasks pane; Escape clears and hides it.
    """

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def action_cancel(self) -> None:
        self.app.close_search(clear=True)


def hint_bar(mode: str = "tasks") -> Text:
    """
    The footer key hints; the set shown depends on the focused pane.
    """
    rows = {
        "tasks": [
            ("Tab", "panes"),
            ("j/k", "move"),
            ("Enter", "open"),
            ("Space", "done"),
            ("o", "link"),
            ("a", "add"),
            ("e", "edit"),
            ("d", "delete"),
            ("/", "search"),
            ("?", "help"),
            ("q", "quit"),
        ],
        "lists": [
            ("Tab", "panes"),
            ("j/k", "move"),
            ("Enter", "open"),
            ("a", "new list"),
            ("e", "rename"),
            ("x", "delete"),
            ("/", "search"),
            ("?", "help"),
            ("q", "quit"),
        ],
        "edit": [("Enter", "save"), ("Esc", "cancel")],
    }
    text = Text()
    for key, desc in rows[mode]:
        text.append(f" {key} ", style=YELLOW)
        text.append(f"{desc}  ", style=FAINT)
    return text
