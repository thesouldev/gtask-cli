import datetime

import pytest

from gtask.tui import parse_due_input

TODAY = datetime.date(2026, 6, 17)
TOMORROW = datetime.date(2026, 6, 18)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", TODAY),
        ("today", TODAY),
        ("  TODAY ", TODAY),
        ("tomorrow", TOMORROW),
        ("tmrw", TOMORROW),
        ("tom", TOMORROW),
        ("none", None),
        ("no", None),
        ("-", None),
        ("22", datetime.date(2026, 6, 22)),
        ("22-06", datetime.date(2026, 6, 22)),
        ("1-1-27", datetime.date(2027, 1, 1)),
    ],
)
def test_parse_due_input(value, expected):
    assert parse_due_input(value, TODAY) == expected


@pytest.mark.parametrize("value", ["5-13", "nonsense", "32-1"])
def test_parse_due_input_rejects_bad_dates(value):
    with pytest.raises(ValueError):
        parse_due_input(value, TODAY)
