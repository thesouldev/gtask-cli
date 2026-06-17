"""
Filesystem locations and OAuth scope, shared with gtask-mcp by path.
"""

import os
import pathlib

CONFIG_DIR = pathlib.Path(
    os.environ.get(
        "GTASK_CONFIG_DIR", pathlib.Path.home() / ".config" / "gtask"
    )
)
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"  # created once
TOKEN_FILE = CONFIG_DIR / "token.json"  # cached after login
CACHE_FILE = CONFIG_DIR / "ls_cache.json"  # ls number to task id

# Tasks only. Cannot touch Gmail, Drive, or Calendar.
SCOPES = ["https://www.googleapis.com/auth/tasks"]
