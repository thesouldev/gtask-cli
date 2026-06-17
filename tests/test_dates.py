import datetime

import pytest

from gtask.dates import parse_due, to_rfc3339, from_rfc3339

TODAY = datetime.date(2026, 6, 17)


def test_day_only_future():
    assert parse_due("22", TODAY) == datetime.date(2026, 6, 22)


def test_day_only_today_stays_today():
    assert parse_due("17", TODAY) == datetime.date(2026, 6, 17)


def test_day_only_past_rolls_to_next_month():
    assert parse_due("5", TODAY) == datetime.date(2026, 7, 5)


def test_day_only_skips_month_without_that_day():
    # June has 30 days, so day 31 lands in July
    assert parse_due("31", TODAY) == datetime.date(2026, 7, 31)


def test_day_month_future():
    assert parse_due("22-06", TODAY) == datetime.date(2026, 6, 22)


def test_day_month_past_rolls_to_next_year():
    assert parse_due("5-3", TODAY) == datetime.date(2027, 3, 5)


def test_full_date():
    assert parse_due("22-06-2026", TODAY) == datetime.date(2026, 6, 22)


def test_full_date_two_digit_year():
    assert parse_due("1-1-27", TODAY) == datetime.date(2027, 1, 1)


def test_slash_separator():
    assert parse_due("22/06", TODAY) == datetime.date(2026, 6, 22)


def test_invalid_month_raises():
    with pytest.raises(ValueError):
        parse_due("5-13", TODAY)


def test_rfc3339_roundtrip():
    d = datetime.date(2026, 6, 22)
    assert to_rfc3339(d) == "2026-06-22T00:00:00.000Z"
    assert from_rfc3339("2026-06-22T00:00:00.000Z") == d
