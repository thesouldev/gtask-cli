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
    ConfirmDelete,
    DetailScreen,
    DueField,
    HelpScreen,
    ListChooser,
    SearchInput,
    celebration,
    empty_state,
    hint_bar,
    parse_due_input,
)


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

    def on_key(self, event: events.Key) -> None:
        # While focused, a/e/x manage lists; during an inline edit every key
        # feeds the buffer. Consume the event so navigation bindings and the
        # global add shortcut stay clear.
        app = self.app
        if app.list_editing:
            app.list_edit_key(event)
        elif event.key == "a":
            app.start_new_list()
        elif event.key == "e":
            app.start_rename_list()
        elif event.key == "x":
            app.start_delete_list()
        else:
            return
        event.stop()
        event.prevent_default()


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
        Binding("d", "delete", show=False),
    ]

    def action_cursor_up(self) -> None:
        if not self.row_count:
            return
        if self.cursor_row == 0:
            self.move_cursor(row=self.row_count - 1)
        else:
            super().action_cursor_up()

    def action_cursor_down(self) -> None:
        if not self.row_count:
            return
        if self.cursor_row >= self.row_count - 1:
            self.move_cursor(row=0)
        else:
            super().action_cursor_down()

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

    def action_delete(self) -> None:
        self.app.delete_current()


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
        self._fields = ["title", "notes", "due", "list"]
        self.due_field = DueField(today, self._due_default())
        start = task.list_id if task else default_list_id
        self.chooser = ListChooser(lists, start)

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
        self._list_edit: str | None = None  # None | "new" | "rename"
        self._list_target: str | None = None
        self._list_buffer = ""
        self._suppress = False  # ignore highlight events during a rebuild

        self.sidebar = Sidebar(id="sidebar")
        self.sidebar.border_title = "Lists"
        self.celebrate = Static(id="celebrate")
        self.celebrate.display = False
        self.summary = Static(id="summary")
        self.table = TaskTable(id="tasks", cursor_type="row")
        self.empty = Static(id="empty")
        self.empty.display = False
        self.right = Vertical(
            self.celebrate, self.summary, self.table, self.empty, id="right"
        )
        self.right.border_title = "Today"
        self.search = SearchInput(placeholder="filter…", id="search")
        self.search.display = False

    def compose(self) -> ComposeResult:
        yield Horizontal(self.sidebar, self.right, id="body")
        yield self.search
        yield Static(hint_bar(), id="hints")

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

    def _apply(self, bundles, select=None) -> None:
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
        if select and select[1] in self.tasks_by_list:
            self.current_view = select
        elif self.current_view is None or (
            self.current_view[0] == "list"
            and self.current_view[1] not in self.tasks_by_list
        ):
            self.current_view = ("smart", "today")
        self._build_sidebar()
        self._refresh_view()
        if not self.table.has_focus and not self.sidebar.has_focus:
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
        for item in self.lists:
            if self._list_edit == "rename" and self._list_target == item["id"]:
                options.append(self._edit_row(item["id"]))
            else:
                options.append(self._list_option(item))
        if self._list_edit == "new":
            options.append(self._edit_row(None))
        else:
            options.append(
                Option(Text("  ＋ New list", style=FAINT), id="action:new")
            )
        self._option_ids = [
            opt.id for opt in options if isinstance(opt, Option)
        ]
        self._suppress = True
        self.sidebar.clear_options()
        self.sidebar.add_options(options)
        self._highlight_sidebar()
        self.call_after_refresh(self._unsuppress)

    def _unsuppress(self) -> None:
        self._suppress = False

    def _edit_row(self, list_id: str | None) -> Option:
        color = self.list_colors.get(list_id, YELLOW) if list_id else YELLOW
        text = Text()
        text.append("▎", style=YELLOW)
        text.append(" ● ", style=color)
        text.append(f" {self._list_buffer}█ ", style="#fbf1c7 on #504945")
        oid = f"list:{list_id}" if list_id else "action:new"
        return Option(text, id=oid)

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
        text.append(f"{name[:30]:<31}", style=FG)
        text.append(f"{count:>2}", style=DIM)
        return text

    def _highlight_sidebar(self) -> None:
        if self._list_edit == "new":
            target = "action:new"
        elif self._list_edit == "rename":
            target = f"list:{self._list_target}"
        else:
            kind, value = self.current_view
            target = f"{kind}:{value}"
        if target in self._option_ids:
            self.sidebar.highlighted = self._option_ids.index(target)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if self._suppress:
            return
        self._select_view(event.option_id)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        if event.option_id == "action:new":
            self.start_new_list()
            return
        self._select_view(event.option_id)
        self.table.focus()

    def _select_view(self, option_id: str | None) -> None:
        if self._list_edit or not option_id:
            return
        kind, value = option_id.split(":", 1)
        if kind not in ("smart", "list"):
            return
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
            tasks = [
                t for t in self.tasks_by_list.get(value, []) if not t.deleted
            ]
            open_rows = [
                t for t, _ in view.order_tree([t for t in tasks if not t.done])
            ]
            done_rows = view.done_today(tasks, self._today)
            self.view_rows = open_rows + done_rows
            title = self._list_title(value)
        # Completed tasks always sink to the bottom (stable within groups).
        self.view_rows.sort(key=lambda t: t.done)
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
        partying = self._celebrating()
        self.celebrate.display = partying
        if partying:
            self.celebrate.update(celebration(len(self.view_rows)))
        self._update_summary()
        has_rows = bool(self.rows)
        self.table.display = has_rows
        self.empty.display = not has_rows and not partying
        if not has_rows:
            self.empty.update(
                empty_state(self.current_view == ("smart", "today"))
            )

    def _celebrating(self) -> bool:
        return (
            self.current_view == ("smart", "today")
            and not self._filter
            and bool(self.view_rows)
            and all(t.done for t in self.view_rows)
        )

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
        if self._celebrating():
            self.summary.update(Text("✓ completed today", style=FAINT))
            return
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
        if task in self.view_rows:
            self.view_rows.remove(task)
            if done:
                self.view_rows.append(task)
            else:
                first_done = next(
                    (i for i, t in enumerate(self.view_rows) if t.done),
                    len(self.view_rows),
                )
                self.view_rows.insert(first_done, task)
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

    def delete_current(self) -> None:
        task = self._current_task()
        if not task:
            return
        self.push_screen(
            ConfirmDelete(
                f'Delete "{task.title}"?',
                "This removes the task from Google Tasks.",
            ),
            lambda ok: self._delete_task(task) if ok else None,
        )

    @work(thread=True)
    def _delete_task(self, task: Task) -> None:
        svc = self._service()
        try:
            svc.delete_task(task.list_id, task.id)
            self._reload_list(svc, task.list_id)
        except Exception as exc:  # pylint: disable=broad-except
            self.call_from_thread(
                self.notify, f"Delete failed: {exc}", severity="error"
            )

    @property
    def list_editing(self) -> bool:
        return self._list_edit is not None

    def _selected_list(self) -> dict | None:
        index = self.sidebar.highlighted
        if index is None or index >= len(self._option_ids):
            return None
        oid = self._option_ids[index]
        if oid.startswith("list:"):
            list_id = oid.split(":", 1)[1]
            return next((x for x in self.lists if x["id"] == list_id), None)
        return None

    def start_new_list(self) -> None:
        self._list_edit = "new"
        self._list_target = None
        self._list_buffer = ""
        self.sidebar.focus()
        self._build_sidebar()
        self._update_hints()

    def start_rename_list(self) -> None:
        item = self._selected_list()
        if not item:
            self.notify("Pick a list to rename", severity="warning")
            return
        self._list_edit = "rename"
        self._list_target = item["id"]
        self._list_buffer = item["title"]
        self._build_sidebar()
        self._update_hints()

    def start_delete_list(self) -> None:
        item = self._selected_list()
        if not item:
            self.notify("Pick a list to delete", severity="warning")
            return
        count = sum(
            1 for t in self.tasks_by_list.get(item["id"], []) if not t.deleted
        )
        self.push_screen(
            ConfirmDelete(
                f'Delete "{item["title"]}"?',
                f"The list and its {count} tasks will be removed.",
            ),
            lambda ok: self._list_op("delete", item["id"], "") if ok else None,
        )

    def list_edit_key(self, event: events.Key) -> None:
        if event.key == "enter":
            self._commit_list_edit()
        elif event.key == "escape":
            self._end_list_edit()
        elif event.key == "backspace":
            self._list_buffer = self._list_buffer[:-1]
            self._build_sidebar()
        elif event.character and event.character.isprintable():
            self._list_buffer += event.character
            self._build_sidebar()

    def _commit_list_edit(self) -> None:
        name = self._list_buffer.strip()
        kind, target = self._list_edit, self._list_target
        self._end_list_edit()
        if not name:
            self.notify("Name can't be empty", severity="warning")
            return
        self._list_op(kind, target, name)

    def _end_list_edit(self) -> None:
        self._list_edit = None
        self._list_target = None
        self._list_buffer = ""
        self._build_sidebar()
        self._update_hints()

    @work(thread=True)
    def _list_op(self, kind: str, list_id: str | None, name: str) -> None:
        svc = self._service()
        select = None
        try:
            if kind == "new":
                select = ("list", svc.create_list(name)["id"])
            elif kind == "rename":
                svc.rename_list(list_id, name)
            elif kind == "delete":
                svc.delete_list(list_id)
            bundles = self._load_all(svc)
        except Exception as exc:  # pylint: disable=broad-except
            self.call_from_thread(
                self.notify, f"List {kind} failed: {exc}", severity="error"
            )
            return
        self.call_from_thread(self._apply, bundles, select)

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
            if data["list_id"] != task.list_id:
                svc.move_task(
                    task.list_id, task.id, destination=data["list_id"]
                )
                self._reload_list(svc, data["list_id"])
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

    def on_descendant_focus(self, _event: events.DescendantFocus) -> None:
        self._update_hints()

    def _update_hints(self) -> None:
        if self.list_editing:
            mode = "edit"
        elif self.sidebar.has_focus:
            mode = "lists"
        else:
            mode = "tasks"
        self.query_one("#hints", Static).update(hint_bar(mode))


def run() -> None:
    GTaskTUI().run()
