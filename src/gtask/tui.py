"""
Textual TUI for browsing and managing Google Tasks.

A two-pane gruvbox layout: a Lists sidebar (Today, Tomorrow, then each task
list) on the left, and the selected view's tasks on the right. Everything is
keyboard-first and mouse-friendly; the keymap deliberately avoids modifier
plus arrow combos so it never collides with a terminal multiplexer.
"""

# The App naturally gathers state and user actions; a couple of the usual
# size limits do not fit a single-screen TUI.
# pylint: disable=too-many-instance-attributes,too-many-public-methods

from __future__ import annotations

import datetime as _dt
import webbrowser

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, OptionList, Static
from textual.widgets.option_list import Option

from . import view
from .client import GTasks, Task
from .tui_widgets import (
    AQUA,
    BLUE,
    DIM,
    FAINT,
    FG,
    RED,
    YELLOW,
    DueField,
    ListChooser,
    parse_due_input,
)

EMPTY_ART = "╰( ◜◡◝ )╯"


class Sidebar(OptionList):
    """
    Lists pane: vim keys on top of the built-in option list.
    """

    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g", "first", show=False),
        Binding("G", "last", show=False),
    ]


class TaskTable(DataTable):
    """
    Tasks pane: vim navigation and per-task actions on the cursor row.
    """

    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g", "top", show=False),
        Binding("G", "bottom", show=False),
        Binding("space", "toggle_done", show=False),
        Binding("x", "toggle_done", show=False),
        Binding("o", "open_link", show=False),
        Binding("e", "edit", show=False),
    ]

    def action_top(self) -> None:
        if self.row_count:
            self.move_cursor(row=0)

    def action_bottom(self) -> None:
        if self.row_count:
            self.move_cursor(row=self.row_count - 1)

    def action_toggle_done(self) -> None:
        self.app.toggle_current_done()

    def action_open_link(self) -> None:
        self.app.open_current_link()

    def action_edit(self) -> None:
        self.app.edit_current()


class SearchInput(Input):
    """
    Filter box for the tasks pane; Escape clears and hides it.
    """

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def action_cancel(self) -> None:
        self.app.close_search(clear=True)


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

    def __init__(self, task: Task, today: _dt.date) -> None:
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
        ("Enter", "open detail"),
        ("Space / x", "toggle done"),
        ("o", "open URL in browser"),
        ("a", "add task"),
        ("e", "edit task"),
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


class TaskForm(ModalScreen):
    """
    Add a new task, or edit an existing one, in a docked panel.
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("enter", "save", show=False),
    ]

    def __init__(self, lists, default_list_id, today, task=None) -> None:
        super().__init__()
        self._lists = lists
        self._today = today
        self._task_obj = task
        self._fields = ["title", "notes", "due"]
        self.due_field = DueField(today, self._due_default())
        self.chooser: ListChooser | None = None
        if task is None:
            self._fields.append("list")
            self.chooser = ListChooser(lists, default_list_id)

    def _due_default(self) -> str:
        if self._task_obj is None:
            return "today"
        due = self._task_obj.due
        return due.strftime("%d-%m-%Y") if due else "none"

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
            if self.chooser is not None:
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
        return Text.assemble(
            ("add › ", f"bold {YELLOW}"),
            ("new task in ", FAINT),
            (self._list_name(self.chooser.value), AQUA),
        )

    def on_list_chooser_changed(self, _event: ListChooser.Changed) -> None:
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
        if self.chooser is None:
            return
        status = Text.assemble(
            ("type a title, hit ", FAINT),
            ("Enter", AQUA),
            (" → saved to ", FAINT),
            (self._list_name(self.chooser.value), AQUA),
            (" · ", FAINT),
            (self.due_field.value(), YELLOW),
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
        list_id = (
            self._task_obj.list_id if self._task_obj else self.chooser.value
        )
        self.dismiss(
            {
                "title": title,
                "notes": self.query_one("#f_notes", Input).value.strip(),
                "due": due,
                "list_id": list_id,
            }
        )


class GTaskTUI(App):
    """
    Browse and manage Google Tasks in a two-pane terminal view.
    """

    CSS_PATH = "tui.tcss"
    TITLE = "gtask"

    BINDINGS = [
        Binding("a", "add", "Add"),
        Binding("slash", "search", "Search"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, loader=None) -> None:
        super().__init__()
        # loader() -> list[(list_dict, [Task])]; injected for tests.
        self._loader = loader
        self._svc: GTasks | None = None
        self._today = _dt.date.today()
        self.lists: list[dict] = []
        self.tasks_by_list: dict[str, list[Task]] = {}
        self.list_colors: dict[str, str] = {}
        self.current_view: tuple[str, str] | None = None
        self.view_rows: list[Task] = []
        self.rows: list[Task] = []
        self._option_ids: list[str] = []
        self._filter = ""

        self.sidebar = Sidebar(id="sidebar")
        self.sidebar.border_title = "Lists"
        self.summary = Static(id="summary")
        self.table = TaskTable(id="tasks", cursor_type="row")
        self.empty = Static(id="empty")
        self.empty.display = False
        self.right = Vertical(self.summary, self.table, self.empty, id="right")
        self.right.border_title = "Today"
        self.search = SearchInput(placeholder="filter…", id="search")
        self.search.display = False

    def compose(self) -> ComposeResult:
        yield Horizontal(self.sidebar, self.right, id="body")
        yield self.search
        yield Static(self._hint_bar(), id="hints")

    def on_mount(self) -> None:
        self.summary.update(Text("Loading…", style=DIM))
        self.action_refresh()

    def _service(self) -> GTasks:
        if self._svc is None:
            self._svc = GTasks()
        return self._svc

    def _load_all(self, svc: GTasks):
        return [
            (tl, svc.list_tasks(tl["id"], tl.get("title", ""), True))
            for tl in svc.tasklists()
        ]

    @work(thread=True, exclusive=True)
    def action_refresh(self) -> None:
        try:
            bundles = (
                self._loader()
                if self._loader
                else self._load_all(self._service())
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.call_from_thread(
                self.notify, f"Load failed: {exc}", severity="error"
            )
            return
        self.call_from_thread(self._apply, bundles)

    def _apply(self, bundles) -> None:
        self.lists = []
        self.tasks_by_list = {}
        self.list_colors = {}
        for index, (tl, tasks) in enumerate(bundles):
            list_id = tl["id"]
            self.lists.append(
                {"id": list_id, "title": tl.get("title", "(untitled)")}
            )
            self.tasks_by_list[list_id] = tasks
            self.list_colors[list_id] = view.list_color(index)
        if self.current_view is None:
            self.current_view = ("smart", "today")
        self._build_sidebar()
        self._refresh_view()
        if not self.table.has_focus:
            self.table.focus()

    @property
    def _all_tasks(self) -> list[Task]:
        return [t for tasks in self.tasks_by_list.values() for t in tasks]

    def _build_sidebar(self) -> None:
        today_open = [
            t
            for t in view.due_today(self._all_tasks, self._today)
            if not t.done
        ]
        tomorrow = self._today + _dt.timedelta(days=1)
        options = [
            self._smart_option("today", "★", YELLOW, "Today", len(today_open)),
            self._smart_option(
                "tomorrow",
                "☆",
                DIM,
                "Tomorrow",
                len(view.due_on(self._all_tasks, tomorrow)),
            ),
            None,
        ]
        options.extend(self._list_option(item) for item in self.lists)
        self._option_ids = [
            opt.id for opt in options if isinstance(opt, Option)
        ]
        self.sidebar.clear_options()
        self.sidebar.add_options(options)
        self._highlight_current()

    def _smart_option(self, key, mark, color, name, count) -> Option:
        return Option(
            self._row_text(mark, color, name, count), id=f"smart:{key}"
        )

    def _list_option(self, item) -> Option:
        open_count = sum(
            1
            for t in self.tasks_by_list[item["id"]]
            if not t.done and not t.deleted
        )
        color = self.list_colors[item["id"]]
        return Option(
            self._row_text("●", color, item["title"], open_count),
            id=f"list:{item['id']}",
        )

    @staticmethod
    def _row_text(mark, color, name, count) -> Text:
        text = Text()
        text.append(f"{mark} ", style=color)
        text.append(f"{name[:13]:<13}", style=FG)
        text.append(f"{count:>2}", style=DIM)
        return text

    def _highlight_current(self) -> None:
        kind, value = self.current_view
        target = f"{kind}:{value}"
        if target in self._option_ids:
            self.sidebar.highlighted = self._option_ids.index(target)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        self._select_view(event.option_id)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        self._select_view(event.option_id)
        self.table.focus()

    def _select_view(self, option_id: str | None) -> None:
        if not option_id:
            return
        kind, value = option_id.split(":", 1)
        new_view = (kind, value)
        if new_view == self.current_view:
            return
        self.current_view = new_view
        self._reset_filter()
        self._refresh_view()

    def _refresh_view(self) -> None:
        kind, value = self.current_view
        if kind == "smart" and value == "today":
            self.view_rows = view.due_today(self._all_tasks, self._today)
            title = "Today"
        elif kind == "smart":
            day = self._today + _dt.timedelta(days=1)
            self.view_rows = view.due_on(self._all_tasks, day)
            title = "Tomorrow"
        else:
            open_tasks = [
                t
                for t in self.tasks_by_list.get(value, [])
                if not t.done and not t.deleted
            ]
            self.view_rows = [t for t, _ in view.order_tree(open_tasks)]
            title = self._list_title(value)
        self.right.border_title = title
        self._refresh_table()

    def _list_title(self, list_id: str) -> str:
        for item in self.lists:
            if item["id"] == list_id:
                return item["title"]
        return "Tasks"

    def _refresh_table(self) -> None:
        self.rows = [t for t in self.view_rows if self._matches(t)]
        smart = self.current_view[0] == "smart"
        self.table.clear(columns=True)
        self.table.add_column("#", width=3)
        self.table.add_column(" ", width=3)
        self.table.add_column("due", width=11)
        if smart:
            self.table.add_column("list", width=10)
        self.table.add_column("task")
        for index, task in enumerate(self.rows, start=1):
            self.table.add_row(*self._cells(index, task, smart))
        self._update_summary()
        has_rows = bool(self.rows)
        self.table.display = has_rows
        self.empty.display = not has_rows
        if not has_rows:
            self.empty.update(self._empty_text())

    def _matches(self, task: Task) -> bool:
        if not self._filter:
            return True
        needle = self._filter
        return (
            needle in task.title.lower() or needle in task.list_title.lower()
        )

    def _cells(self, index: int, task: Task, smart: bool) -> list[Text]:
        num = Text(str(index), style=FAINT, justify="right")
        box = Text(
            "[x]" if task.done else "[ ]", style=DIM if task.done else FAINT
        )
        due = Text(
            view.due_label(task.due, self._today), style=self._due_style(task)
        )
        title = Text(task.title, style=DIM if task.done else FG)
        if task.done:
            title.stylize("strike")
        if view.first_url(task.notes, task.web_view_link):
            title.append("  ↗", style=BLUE)
        cells = [num, box, due]
        if smart:
            cells.append(
                Text(
                    task.list_title,
                    style=self.list_colors.get(task.list_id, AQUA),
                )
            )
        cells.append(title)
        return cells

    def _due_style(self, task: Task) -> str:
        if task.done:
            return DIM
        if task.due and task.due < self._today:
            return RED
        return YELLOW

    def _update_summary(self) -> None:
        kind, value = self.current_view
        text = Text()
        if kind == "smart" and value == "today":
            overdue = sum(
                1
                for t in self.rows
                if not t.done and t.due and t.due < self._today
            )
            due = sum(
                1 for t in self.rows if not t.done and t.due == self._today
            )
            done = sum(1 for t in self.rows if t.done)
            text.append(f"{overdue} overdue  ", style=RED)
            text.append(f"{due} due  ", style=YELLOW)
            text.append(f"· {done} done", style=DIM)
        else:
            text.append(f"{len(self.rows)} open", style=DIM)
        if self._filter:
            text.append(f"   /{self._filter}", style=BLUE)
        self.summary.update(text)

    def _empty_text(self) -> Text:
        message = (
            "Nothing due today."
            if self.current_view == ("smart", "today")
            else "Nothing here."
        )
        text = Text(justify="center")
        text.append(EMPTY_ART + "\n\n", style=FAINT)
        text.append(message + "\n", style="#d5c4a1")
        text.append("Press a to add a task.", style=FAINT)
        return text

    def _current_task(self) -> Task | None:
        index = self.table.cursor_row
        if 0 <= index < len(self.rows):
            return self.rows[index]
        return None

    def on_data_table_row_selected(
        self, _event: DataTable.RowSelected
    ) -> None:
        task = self._current_task()
        if task:
            self.push_screen(
                DetailScreen(task, self._today), self._after_detail
            )

    def _after_detail(self, result) -> None:
        if result == "edit":
            self.edit_current()
        elif result == "done":
            self.toggle_current_done()

    def toggle_current_done(self) -> None:
        task = self._current_task()
        if not task:
            return
        done = not task.done
        task.mark(done)
        self._refresh_table()
        self._build_sidebar()
        self._write_done(task.list_id, task.id, done)

    @work(thread=True)
    def _write_done(self, list_id: str, task_id: str, done: bool) -> None:
        svc = self._service()
        try:
            if done:
                svc.complete_task(list_id, task_id)
            else:
                svc.reopen_task(list_id, task_id)
        except Exception as exc:  # pylint: disable=broad-except
            self.call_from_thread(
                self.notify, f"Save failed: {exc}", severity="error"
            )

    def open_current_link(self) -> None:
        task = self._current_task()
        url = view.first_url(task.notes, task.web_view_link) if task else None
        if url:
            webbrowser.open(url)
            self.notify(f"Opening {url}")
        else:
            self.notify("No link in this task", severity="warning")

    def action_add(self) -> None:
        if not self.lists:
            return
        default = self._current_list_id() or self.lists[0]["id"]
        self.push_screen(
            TaskForm(self.lists, default, self._today), self._after_add
        )

    def _after_add(self, data) -> None:
        if data:
            self._create(data)

    def edit_current(self) -> None:
        task = self._current_task()
        if not task:
            return
        self.push_screen(
            TaskForm(self.lists, task.list_id, self._today, task),
            lambda data: self._after_edit(task, data),
        )

    def _after_edit(self, task: Task, data) -> None:
        if data:
            self._update(task, data)

    def _current_list_id(self) -> str | None:
        kind, value = self.current_view
        return value if kind == "list" else None

    @work(thread=True)
    def _create(self, data) -> None:
        svc = self._service()
        try:
            svc.add_task(
                data["list_id"], data["title"], data["due"], data["notes"]
            )
            self._reload_list(svc, data["list_id"])
        except Exception as exc:  # pylint: disable=broad-except
            self.call_from_thread(
                self.notify, f"Add failed: {exc}", severity="error"
            )

    @work(thread=True)
    def _update(self, task: Task, data) -> None:
        svc = self._service()
        try:
            svc.update_task(
                task.list_id,
                task.id,
                title=data["title"],
                notes=data["notes"],
                due=data["due"],
            )
            self._reload_list(svc, task.list_id)
        except Exception as exc:  # pylint: disable=broad-except
            self.call_from_thread(
                self.notify, f"Edit failed: {exc}", severity="error"
            )

    def _reload_list(self, svc: GTasks, list_id: str) -> None:
        tasks = svc.list_tasks(list_id, self._list_title(list_id), True)
        self.call_from_thread(self._replace_list, list_id, tasks)

    def _replace_list(self, list_id: str, tasks: list[Task]) -> None:
        self.tasks_by_list[list_id] = tasks
        self._build_sidebar()
        self._refresh_view()

    def action_search(self) -> None:
        self.search.display = True
        self.search.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._filter = event.value.strip().lower()
            self._refresh_table()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            self.table.focus()

    def _reset_filter(self) -> None:
        """
        Drop any active filter and hide the search box without moving focus.
        """
        self._filter = ""
        self.search.value = ""
        self.search.display = False

    def close_search(self, clear: bool) -> None:
        """
        Dismiss the search box in response to the user and return to the table.
        """
        if clear:
            self._reset_filter()
        else:
            self.search.display = False
        self._refresh_table()
        if self.table.display:
            self.table.focus()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    @staticmethod
    def _hint_bar() -> Text:
        pairs = [
            ("Tab", "panes"),
            ("j/k", "move"),
            ("Enter", "open"),
            ("Space", "done"),
            ("o", "link"),
            ("a", "add"),
            ("e", "edit"),
            ("/", "search"),
            ("?", "help"),
            ("q", "quit"),
        ]
        text = Text()
        for key, desc in pairs:
            text.append(f" {key} ", style=YELLOW)
            text.append(f"{desc}  ", style=FAINT)
        return text


def run() -> None:
    GTaskTUI().run()
