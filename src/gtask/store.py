"""
Local cache mapping the numbers shown by `gtask ls` to real task ids,
so you never paste a raw Google task id.
"""

from __future__ import annotations

import json

from . import config


def save(rows: list[dict]) -> None:
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.CACHE_FILE.write_text(json.dumps(rows))


def load() -> list[dict]:
    if not config.CACHE_FILE.exists():
        return []
    try:
        return json.loads(config.CACHE_FILE.read_text())
    except (ValueError, OSError):
        return []


def lookup(n: int) -> dict | None:
    for row in load():
        if row.get("n") == n:
            return row
    return None
