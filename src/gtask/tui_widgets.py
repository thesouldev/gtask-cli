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
        # up/down walk form fields rather than scrolling this row
        Binding("down", "focus_next", show=False),
        Binding("up", "focus_previous", show=False),
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

    def action_focus_next(self) -> None:
        self.screen.focus_next()

    def action_focus_previous(self) -> None:
        self.screen.focus_previous()

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
        ("← / →  ·  Tab", "switch pane"),
        ("j / k", "down / up"),
        ("g / G", "top / bottom"),
        ("Enter", "open detail / list"),
        ("Space", "toggle done"),
        ("o", "open URL in browser"),
        ("a", "add task / new list"),
        ("Shift+A", "add subtask"),
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
            ("←/→", "panes"),
            ("j/k", "move"),
            ("Enter", "open"),
            ("Space", "done"),
            ("o", "link"),
            ("a", "add"),
            ("A", "subtask"),
            ("e", "edit"),
            ("d", "delete"),
            ("/", "search"),
            ("r", "refresh"),
            ("?", "help"),
            ("q", "quit"),
        ],
        "lists": [
            ("←/→", "panes"),
            ("j/k", "move"),
            ("Enter", "open"),
            ("a", "new list"),
            ("e", "rename"),
            ("x", "delete"),
            ("/", "search"),
            ("r", "refresh"),
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


class TaskForm(ModalScreen):
    """
    Add a new task, or edit an existing one, in a docked panel.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("enter", "save", show=False),
        Binding("down", "focus_next", show=False),
        Binding("up", "focus_previous", show=False),
    ]

    def __init__(
        self, lists, default_list_id, today, task=None, parent=None
    ) -> None:
        super().__init__()
        self._lists = lists
        self._today = today
        self._task_obj = task
        self._parent_obj = parent  # set when adding a subtask
        self._fields = ["title", "notes", "due"]
        if parent is None:
            self._fields.append("list")
        self.due_field = DueField(today, self._due_default())
        start = (
            parent.list_id
            if parent
            else (task.list_id if task else default_list_id)
        )
        self.chooser = ListChooser(lists, start)

    def action_focus_next(self) -> None:
        self.focus_next()

    def action_focus_previous(self) -> None:
        self.focus_previous()

    def _due_default(self) -> str:
        if self._task_obj is None:
            return "today"
        due = self._task_obj.due
        if due is None:
            return "none"
        if due == self._today:
            return "today"
        if due == self._today + _dt.timedelta(days=1):
            return "tomorrow"
        return due.strftime("%d-%m-%Y")

    def compose(self) -> ComposeResult:
        editing = self._task_obj is not None
        with Vertical(id="form"):
            with Horizontal(classes="form-head"):
                yield Static(
                    self._header(editing),
                    id="form_title",
                    classes="head-title",
                )
                yield Static(
                    Text("Tab walks fields · ⇧Tab back", style=FAINT),
                    classes="head-hint",
                )
            yield self._row(
                "title",
                Input(
                    value=self._task_obj.title if editing else "",
                    placeholder="Task title…",
                    classes="inline",
                    id="f_title",
                ),
            )
            yield self._row(
                "notes",
                Input(
                    value=self._task_obj.notes if editing else "",
                    placeholder="notes — optional, paste any links here",
                    classes="inline",
                    id="f_notes",
                ),
            )
            yield self._row("due", self.due_field)
            if self._parent_obj is None:
                yield self._row("list", self.chooser)
            with Horizontal(classes="form-foot"):
                yield Static(id="foot_status")
                yield Static(
                    Text.assemble(
                        ("Enter", AQUA),
                        (" save · ", FAINT),
                        ("Esc", RED),
                        (" cancel", FAINT),
                    ),
                    classes="foot-hint",
                )

    def _header(self, editing: bool) -> Text:
        if editing:
            return Text.assemble(
                ("edit › ", f"bold {YELLOW}"),
                (self._task_obj.title, FG),
            )
        if self._parent_obj is not None:
            return Text.assemble(
                ("add › ", f"bold {YELLOW}"),
                ("subtask under ", FAINT),
                (self._parent_obj.title, AQUA),
            )
        return Text.assemble(
            ("add › ", f"bold {YELLOW}"),
            ("new task in ", FAINT),
            (self._list_name(self.chooser.value), AQUA),
        )

    def on_list_chooser_changed(self, _event: ListChooser.Changed) -> None:
        if self._task_obj is None:
            self.query_one("#form_title", Static).update(self._header(False))
        self._refresh_status()

    def _row(self, name: str, *content) -> Horizontal:
        label = Static(classes="field-label", id=f"lbl_{name}")
        return Horizontal(label, *content, classes="field")

    def _list_name(self, list_id: str) -> str:
        for item in self._lists:
            if item["id"] == list_id:
                return item["title"]
        return "?"

    def on_mount(self) -> None:
        self._mark("title")
        self._refresh_status()
        self.query_one("#f_title", Input).focus()

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        widget = event.widget
        if isinstance(widget, ListChooser):
            self._mark("list")
        elif isinstance(widget, DueField):
            self._mark("due")
        elif widget.id and widget.id.startswith("f_"):
            self._mark(widget.id[2:])

    def _mark(self, active: str) -> None:
        for name in self._fields:
            marker = "▸ " if name == active else "  "
            style = f"bold {YELLOW}" if name == active else FAINT
            self.query_one(f"#lbl_{name}", Static).update(
                Text(f"{marker}{name}", style=style)
            )

    def on_due_field_changed(self, _event: DueField.Changed) -> None:
        self._refresh_status()

    def _refresh_status(self) -> None:
        target = self._list_name(self.chooser.value)
        due = self.due_field.value()
        if self._task_obj is None:
            status = Text.assemble(
                ("type a title, hit ", FAINT),
                ("Enter", AQUA),
                (" → saved to ", FAINT),
                (target, AQUA),
                (" · ", FAINT),
                (due, YELLOW),
            )
        else:
            status = Text.assemble(
                ("Enter", AQUA),
                (" → ", FAINT),
                (target, AQUA),
                (" · ", FAINT),
                (due, YELLOW),
            )
        self.query_one("#foot_status", Static).update(status)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self.action_save()

    def action_save(self) -> None:
        title = self.query_one("#f_title", Input).value.strip()
        if not title:
            self.app.notify("Title is required", severity="warning")
            self.query_one("#f_title", Input).focus()
            return
        try:
            due = parse_due_input(self.due_field.value(), self._today)
        except ValueError as exc:
            self.app.notify(f"Bad date: {exc}", severity="warning")
            return
        self.dismiss(
            {
                "title": title,
                "notes": self.query_one("#f_notes", Input).value.strip(),
                "due": due,
                "list_id": self.chooser.value,
                "parent": self._parent_obj.id if self._parent_obj else None,
            }
        )
