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
from textual.widgets import DataTable, Input, OptionList, Rule, Static
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
    HelpScreen,
    SearchInput,
    TaskForm,
    celebration,
    empty_state,
    hint_bar,
)


class NewListButton(Static):
    """
    Footer affordance docked at the bottom of the Lists pane.
    """

    def on_click(self) -> None:
        self.app.start_new_list()


class EmptyPane(Static):
    """
    The placeholder for an empty view; focusable so a still adds a task here.
    """

    can_focus = True
    BINDINGS = [Binding("left", "focus_lists", show=False)]

    def action_focus_lists(self) -> None:
        self.app.sidebar.focus()


class Sidebar(OptionList):
    """
    Lists pane: vim keys on top of the built-in option list.
    """

    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g", "first", show=False),
        Binding("G", "last", show=False),
        Binding("right", "focus_tasks", show=False),
    ]

    def action_focus_tasks(self) -> None:
        self.app.focus_tasks()

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
        Binding("A", "add_subtask", show=False),
        Binding("left", "focus_lists", show=False),
        Binding("right", "noop", show=False),
    ]

    def action_focus_lists(self) -> None:
        self.app.sidebar.focus()

    def action_noop(self) -> None:
        pass

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

    def action_add_subtask(self) -> None:
        self.app.add_subtask()


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
        self._list_cursor = 0
        self._suppress = False  # ignore highlight events during a rebuild

        self.sidebar = Sidebar(id="lists")
        self.new_list_btn = NewListButton(
            Text("  ＋ New list", style=FAINT), id="newlist"
        )
        self.left = Vertical(self.sidebar, self.new_list_btn, id="sidebar")
        self.left.border_title = "Lists"
        self.celebrate = Static(id="celebrate")
        self.celebrate.display = False
        self.summary = Static(id="summary")
        self.thead = Static(id="thead")
        self.rule_top = Rule(id="rule-top")
        self.rule_bot = Rule(id="rule-bot")
        self.table = TaskTable(
            id="tasks",
            cursor_type="row",
            cell_padding=1,
            show_header=False,
        )
        self.empty = EmptyPane(id="empty")
        self.empty.display = False
        self.right = Vertical(
            self.celebrate,
            self.summary,
            self.rule_top,
            self.thead,
            self.rule_bot,
            self.table,
            self.empty,
            id="right",
        )
        self.right.border_title = "Today"
        self.search = SearchInput(placeholder="filter…", id="search")
        self.search.display = False

    def compose(self) -> ComposeResult:
        yield Horizontal(self.left, self.right, id="body")
        yield self.search
        yield Static(hint_bar(), id="hints")

    def on_mount(self) -> None:
        self.summary.update(Text("Loading…", style=DIM))
        self._reload(announce=False)

    def _service(self) -> GTasks:
        if self._svc is None:
            self._svc = GTasks()
        return self._svc

    def _load_all(self, svc: GTasks):
        return [
            (tl, svc.list_tasks(tl["id"], tl.get("title", ""), True))
            for tl in svc.tasklists()
        ]

    def action_refresh(self) -> None:
        self.notify("Refreshing…", timeout=1)
        self._reload(announce=True)

    @work(thread=True, exclusive=True)
    def _reload(self, announce: bool) -> None:
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
        if announce:
            self.call_from_thread(self.notify, "Refreshed", timeout=1)

    def _apply(self, bundles, select=None) -> None:
        self.lists = []
        self.tasks_by_list = {}
        self.list_colors = {}
        bundles = sorted(bundles, key=lambda b: b[0].get("title", "").lower())
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
        self.new_list_btn.display = self._list_edit != "new"
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
        buf, cur = self._list_buffer, self._list_cursor
        box = "#fbf1c7 on #504945"
        text = Text()
        text.append("▎", style=YELLOW)
        text.append(" ● ", style=color)
        text.append(" ", style=box)
        text.append(buf[:cur], style=box)
        text.append(
            buf[cur] if cur < len(buf) else " ", style="#282828 on #fbf1c7"
        )
        text.append(buf[cur + 1 :], style=box)
        text.append(" ", style=box)
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
        text.append(f"{name[:31]:<32}", style=FG)
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
        today = self._today
        if kind == "smart" and value == "today":
            top = view.due_today(self._all_tasks, today)
            pool, title = self._all_tasks, "Today"
        elif kind == "smart":
            day = today + _dt.timedelta(days=1)
            top = view.due_on(self._all_tasks, day)
            pool, title = self._all_tasks, "Tomorrow"
        else:
            pool = [
                t for t in self.tasks_by_list.get(value, []) if not t.deleted
            ]
            top = sorted(
                (t for t in pool if not t.done or t.completed_date == today),
                key=lambda t: t.position,
            )
            title = self._list_title(value)
        top = [t for t in top if not t.parent]
        self.view_rows = view.build_rows(top, pool, today)
        self.right.border_title = title
        self._refresh_table()

    def _list_title(self, list_id: str) -> str:
        for item in self.lists:
            if item["id"] == list_id:
                return item["title"]
        return "Tasks"

    COLUMNS = (("", 3), ("due", 11), ("list", 10), ("task", 0))

    def _refresh_table(self) -> None:
        self.rows = [t for t in self.view_rows if self._matches(t)]
        smart = self.current_view[0] == "smart"
        columns = [c for c in self.COLUMNS if smart or c[0] != "list"]
        self.table.clear(columns=True)
        for name, width in columns:
            self.table.add_column(name, width=width or None)
        for i, task in enumerate(self.rows):
            nxt = self.rows[i + 1] if i + 1 < len(self.rows) else None
            last = bool(task.parent) and (
                nxt is None or nxt.parent != task.parent
            )
            self.table.add_row(*self._cells(task, smart, last))
        self.thead.update(self._header_text(columns))
        partying = self._celebrating()
        self.celebrate.display = partying
        if partying:
            self.celebrate.update(celebration(len(self.view_rows)))
        self._update_summary()
        has_rows = bool(self.rows)
        for widget in (self.thead, self.rule_top, self.rule_bot, self.table):
            widget.display = has_rows
        self.empty.display = not has_rows and not partying
        if not has_rows:
            self.empty.update(
                empty_state(self.current_view == ("smart", "today"))
            )

    @staticmethod
    def _header_text(columns) -> Text:
        parts = []
        for label, width in columns:
            parts.append(f" {label.ljust(width)} " if width else f" {label}")
        return Text("".join(parts), style=FAINT)

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

    def _cells(self, task: Task, smart: bool, last: bool) -> list[Text]:
        sub = bool(task.parent)
        box = Text(
            "[x]" if task.done else "[ ]", style=DIM if task.done else FAINT
        )
        due = Text(
            "" if sub else view.due_label(task.due, self._today),
            style=self._due_style(task),
        )
        title = Text()
        if sub:
            title.append(("└ " if last else "├ "), style=FAINT)
        name = Text(task.title, style=DIM if task.done else FG)
        if task.done:
            name.stylize("strike")
        title.append_text(name)
        title = self._with_badge(task, sub, title)
        if view.first_url(task.notes, task.web_view_link):
            title.append("  ↗", style=BLUE)
        cells = [box, due]
        if smart:
            color = self.list_colors.get(task.list_id, AQUA)
            cells.append(Text("" if sub else task.list_title, style=color))
        cells.append(title)
        return cells

    def _with_badge(self, task: Task, sub: bool, title: Text) -> Text:
        if sub:
            return title
        kids = [
            k
            for k in self.tasks_by_list.get(task.list_id, [])
            if k.parent == task.id and not k.deleted
        ]
        if kids:
            done = sum(1 for k in kids if k.done)
            title.append(f"  {done}/{len(kids)}", style=DIM)
        return title

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
            text.append(f"{overdue} overdue", style=RED)
            text.append("  ·  ", style=DIM)
            text.append(f"{due} due", style=YELLOW)
            text.append("  ·  ", style=DIM)
            text.append(f"{done} done", style=DIM)
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
        self._refresh_view()
        self._build_sidebar()
        if task in self.rows:
            self.table.move_cursor(row=self.rows.index(task))
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

    def focus_tasks(self) -> None:
        target = self.table if self.table.display else self.empty
        if target.display:
            target.focus()

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

    def add_subtask(self) -> None:
        task = self._current_task()
        if not task:
            return
        parent = task
        if task.parent:  # one level deep: attach to the top-level parent
            parent = next(
                (
                    t
                    for t in self.tasks_by_list.get(task.list_id, [])
                    if t.id == task.parent
                ),
                task,
            )
        self.push_screen(
            TaskForm(self.lists, parent.list_id, self._today, parent=parent),
            self._after_add,
        )

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
        self._list_cursor = 0
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
        self._list_cursor = len(self._list_buffer)
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
        key, cur, buf = event.key, self._list_cursor, self._list_buffer
        if key == "enter":
            self._commit_list_edit()
            return
        if key == "escape":
            self._end_list_edit()
            return
        if key == "left":
            self._list_cursor = max(0, cur - 1)
        elif key == "right":
            self._list_cursor = min(len(buf), cur + 1)
        elif key == "home":
            self._list_cursor = 0
        elif key == "end":
            self._list_cursor = len(buf)
        elif key == "backspace" and cur > 0:
            self._list_buffer = buf[: cur - 1] + buf[cur:]
            self._list_cursor = cur - 1
        elif key == "delete":
            self._list_buffer = buf[:cur] + buf[cur + 1 :]
        elif event.character and event.character.isprintable():
            self._list_buffer = buf[:cur] + event.character + buf[cur:]
            self._list_cursor = cur + 1
        else:
            return
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
                data["list_id"],
                data["title"],
                data["due"],
                data["notes"],
                parent=data.get("parent"),
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
