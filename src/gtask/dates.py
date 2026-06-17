"""
Terse date parser.

Forms (day first):
  22          -> 22nd of the current month and year
  22-06       -> 22 June of the current year
  22-06-2026  -> exact day, month, year

Separators -, /, and . are accepted. If a partial date has already passed it
rolls forward to the next period (next month for a day, next year for a
day-month) so a task is never created in the past.
"""

from __future__ import annotations

import datetime as _dt

_SEPS = ("-", "/", ".")


def parse_due(s: str, today: _dt.date | None = None) -> _dt.date:
    today = today or _dt.date.today()
    parts = _split(s)
    if len(parts) == 1:
        return _from_day(parts[0], today)
    if len(parts) == 2:
        return _from_day_month(parts[0], parts[1], today)
    if len(parts) == 3:
        return _from_full(parts[0], parts[1], parts[2])
    raise ValueError(f"unrecognised date: {s!r}")


def to_rfc3339(d: _dt.date) -> str:
    """Google Tasks 'due' is a day-level RFC3339 timestamp in UTC."""
    return d.strftime("%Y-%m-%dT00:00:00.000Z")


def from_rfc3339(s: str) -> _dt.date:
    return _dt.date.fromisoformat(s[:10])


def _split(s: str) -> list[str]:
    s = s.strip()
    for sep in _SEPS:
        if sep in s:
            return [p for p in s.split(sep) if p != ""]
    return [s]


def _to_int(p: str) -> int:
    try:
        return int(p)
    except ValueError as exc:
        raise ValueError(f"not a number: {p!r}") from exc


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    idx = (month - 1) + n
    return year + idx // 12, idx % 12 + 1


def _from_day(day: str, today: _dt.date) -> _dt.date:
    d = _to_int(day)
    for i in range(0, 13):
        y, m = _add_months(today.year, today.month, i)
        try:
            cand = _dt.date(y, m, d)
        except ValueError:
            continue  # e.g. day 31 in a 30-day month, try the next month
        if cand >= today:
            return cand
    raise ValueError(f"no valid date for day {d}")


def _from_day_month(day: str, month: str, today: _dt.date) -> _dt.date:
    d, mo = _to_int(day), _to_int(month)
    for yr in (today.year, today.year + 1):
        cand = _dt.date(
            yr, mo, d
        )  # raises ValueError if the day/month is invalid
        if cand >= today:
            return cand
    raise ValueError(f"no valid date for {day}-{month}")


def _from_full(day: str, month: str, year: str) -> _dt.date:
    d, mo, yr = _to_int(day), _to_int(month), _to_int(year)
    if yr < 100:
        yr += 2000
    return _dt.date(yr, mo, d)
