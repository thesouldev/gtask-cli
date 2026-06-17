# Architecture

gtask is a thin command line layer over a small, UI agnostic core. The core
holds all the data logic so a future TUI can reuse it without a rewrite.

Back to the [README](../README.md).

## Modules

All under `src/gtask/`.

| Module       | Responsibility                                             |
| ------------ | --------------------------------------------------------- |
| `config.py`  | file locations and the OAuth scope                        |
| `auth.py`    | OAuth login, token caching, and refresh                   |
| `client.py`  | the Tasks API wrapper, plus list resolve and create       |
| `dates.py`   | the terse date parser                                      |
| `store.py`   | the `ls` number to task id cache                           |
| `cli.py`     | the Typer commands, the only module that prints           |

The rule is that `cli.py` is the only place that formats output. Everything
below it returns data. A TUI would sit beside `cli.py` on the same core.

## Data flow

1. A command in `cli.py` calls the core.
2. `client.py` builds a Tasks API service using credentials from `auth.py`.
3. For `add`, `dates.py` turns the typed date into a real date.
4. For `ls`, tasks are gathered, filtered, numbered, and the numbering is saved
   by `store.py` so `done` and `rm` can resolve a number to a task id.

## Design decisions

- One Google account, the user's main account.
- OAuth scope is tasks only, which also makes tasks appear in Google Calendar
  for free, so no Calendar API is needed.
- Dates are day level only, matching what the Tasks API supports.
- Lists are addressed by name and created on demand.
- Credentials live on disk at a fixed path so the separate `gtask-mcp` repo can
  share a single login.

## Roadmap

| Phase | Scope                                                          |
| ----- | ------------------------------------------------------------- |
| v1    | the CLI described here                                         |
| v2    | a Textual TUI launched by `gtask` with no arguments           |
| later | recurring tasks via a local scheduler, and the gtask-mcp server |

The v2 TUI plans a left pane of lists with a virtual Today entry, a right pane
of tasks, vim style keys, overdue in red, and completed struck through. It adds
no data logic, only a new view onto the existing core.
