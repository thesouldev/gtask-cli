"""
Reusable widgets and the gruvbox palette for the TUI's add/edit form.
"""

from __future__ import annotations

import datetime as _dt

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalScroll
from textual.message import Message
from textual.widgets import Static

from . import dates

# gruvbox palette, by role.
FG = "#ebdbb2"
DIM = "#928374"
FAINT = "#7c6f64"
RED = "#fb4934"
YELLOW = "#fabd2f"
AQUA = "#8ec07c"
BLUE = "#83a598"


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
