import datetime

import pytest

from gtask.client import Task
from gtask import view

TODAY = datetime.date(2026, 6, 17)


def make(
    id,
    title="task",
    due=None,
    status="needsAction",
    parent=None,
    position="0",
    deleted=False,
    completed=None,
    list_id="L1",
    list_title="Work",
):
    raw = {"id": id, "title": title, "status": status, "position": position}
    if due is not None:
        raw["due"] = due.strftime("%Y-%m-%dT00:00:00.000Z")
    if parent is not None:
        raw["parent"] = parent
    if deleted:
        raw["deleted"] = True
    if completed is not None:
        raw["completed"] = completed.strftime("%Y-%m-%dT12:00:00.000Z")
    return Task(raw, list_id, list_title)


@pytest.mark.parametrize(
    "due, expected",
    [
        (TODAY, "today"),
        (TODAY - datetime.timedelta(days=1), "overdue 1d"),
        (TODAY - datetime.timedelta(days=7), "overdue 7d"),
        (TODAY + datetime.timedelta(days=1), "tomorrow"),
        (datetime.date(2026, 6, 25), "25 Jun"),
        (None, ""),
    ],
)
def test_due_label(due, expected):
    assert view.due_label(due, TODAY) == expected


@pytest.mark.parametrize(
    "texts, expected",
    [
        (["see https://a.com now"], "https://a.com"),
        (["no link here"], None),
        ([None, ""], None),
        (["x https://b.org/p)."], "https://b.org/p"),
        (["", "ends https://c.io/x."], "https://c.io/x"),
        (["http://1.com", "http://2.com"], "http://1.com"),
    ],
)
def test_first_url(texts, expected):
    assert view.first_url(*texts) == expected


@pytest.mark.parametrize(
    "index, expected",
    [
        (0, view.LIST_COLORS[0]),
        (len(view.LIST_COLORS), view.LIST_COLORS[0]),
        (len(view.LIST_COLORS) + 1, view.LIST_COLORS[1]),
    ],
)
def test_list_color_cycles(index, expected):
    assert view.list_color(index) == expected


def test_order_tree_nests_children_under_parents():
    tasks = [
        make("p1", position="1"),
        make("c1", parent="p1", position="0"),
        make("p0", position="0"),
    ]
    ordered = view.order_tree(tasks)
    assert [(t.id, depth) for t, depth in ordered] == [
        ("p0", 0),
        ("p1", 0),
        ("c1", 1),
    ]


def test_order_tree_keeps_lists_apart():
    tasks = [
        make("a", list_id="L1"),
        make("b", list_id="L2"),
    ]
    ids = {t.id for t, _ in view.order_tree(tasks)}
    assert ids == {"a", "b"}


def test_due_today_includes_overdue_and_done_today():
    tasks = [
        make("overdue", due=TODAY - datetime.timedelta(days=2)),
        make("today", due=TODAY),
        make("done_today", due=TODAY, status="completed"),
        make(
            "done_overdue",
            due=TODAY - datetime.timedelta(days=1),
            status="completed",
        ),
        make("future", due=TODAY + datetime.timedelta(days=3)),
        make("no_due"),
    ]
    ids = [t.id for t in view.due_today(tasks, TODAY)]
    assert ids == ["overdue", "today", "done_today"]


def test_build_rows_nests_subtasks_and_sinks_done_parents():
    yesterday = TODAY - datetime.timedelta(days=1)
    p1 = make("p1", position="0")
    c_open = make("c_open", parent="p1", position="0")
    c_today = make(
        "c_today",
        parent="p1",
        status="completed",
        completed=TODAY,
        position="1",
    )
    c_old = make(
        "c_old",
        parent="p1",
        status="completed",
        completed=yesterday,
        position="2",
    )
    p2 = make("p2", status="completed", completed=TODAY, position="1")
    pool = [p1, c_open, c_today, c_old, p2]
    rows = view.build_rows([p1, p2], pool, TODAY)
    # open parent first with its open + today-done kids (old kid hidden),
    # then the completed parent sinks to the bottom.
    assert [t.id for t in rows] == ["p1", "c_open", "c_today", "p2"]


def test_mark_stamps_and_clears_completion():
    t = make("a")
    assert not t.done and t.completed_date is None
    t.mark(True)
    assert t.done and t.completed_date == datetime.date.today()
    t.mark(False)
    assert not t.done and t.completed_date is None


def test_due_on_matches_single_day_open_only():
    day = TODAY + datetime.timedelta(days=1)
    tasks = [
        make("tomorrow", due=day),
        make("done", due=day, status="completed"),
        make("today", due=TODAY),
    ]
    assert [t.id for t in view.due_on(tasks, day)] == ["tomorrow"]
