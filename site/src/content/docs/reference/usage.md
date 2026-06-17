---
title: CLI reference
description: Every gtask command and option.
---


Manage Google Tasks from the terminal.

**Usage**:

```console
$ gtask [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `add`: Add a task, optionally as a subtask of...
* `ls`: List tasks.
* `show`: Show one task in full, with its subtasks.
* `done`: Complete a task by its ls number.
* `reopen`: Reopen a completed task by its ls number.
* `edit`: Update a task&#x27;s text, notes, or due date...
* `move`: Reorder, reparent, or move a task to...
* `rm`: Delete a task by its ls number, or by --id...
* `clear`: Remove completed tasks from a list, or...
* `login`: Run the one-time browser authorization.
* `lists`: Manage task lists.

## `gtask add`

Add a task, optionally as a subtask of another.

**Usage**:

```console
$ gtask add [OPTIONS] TEXT [DATE]
```

**Arguments**:

* `TEXT`: task text  [required]
* `[DATE]`: due date: 22, 22-06, or 22-06-2026

**Options**:

* `-l, --list TEXT`: target list (created on demand)
* `-n, --notes TEXT`: description / notes
* `-u, --under INTEGER`: make it a subtask of this ls number
* `-y, --yes`: create the list without prompting
* `--help`: Show this message and exit.

## `gtask ls`

List tasks. Default shows today and overdue across lists.

**Usage**:

```console
$ gtask ls [OPTIONS]
```

**Options**:

* `-l, --list TEXT`: limit to one list
* `--all`: show every open task
* `--done`: include completed tasks
* `--deleted`: include deleted tasks
* `--json`: output JSON (id, list, title, notes, due)
* `--help`: Show this message and exit.

## `gtask show`

Show one task in full, with its subtasks.

**Usage**:

```console
$ gtask show [OPTIONS] N
```

**Arguments**:

* `N`: task number from the last ls  [required]

**Options**:

* `--help`: Show this message and exit.

## `gtask done`

Complete a task by its ls number.

**Usage**:

```console
$ gtask done [OPTIONS] N
```

**Arguments**:

* `N`: task number from the last ls  [required]

**Options**:

* `--help`: Show this message and exit.

## `gtask reopen`

Reopen a completed task by its ls number.

**Usage**:

```console
$ gtask reopen [OPTIONS] N
```

**Arguments**:

* `N`: task number from the last ls  [required]

**Options**:

* `--help`: Show this message and exit.

## `gtask edit`

Update a task&#x27;s text, notes, or due date by its ls number.

**Usage**:

```console
$ gtask edit [OPTIONS] N
```

**Arguments**:

* `N`: task number from the last ls  [required]

**Options**:

* `-t, --text TEXT`: new text
* `-n, --notes TEXT`: new description / notes
* `-d, --date TEXT`: new due date
* `--help`: Show this message and exit.

## `gtask move`

Reorder, reparent, or move a task to another list.

**Usage**:

```console
$ gtask move [OPTIONS] N
```

**Arguments**:

* `N`: task number from the last ls  [required]

**Options**:

* `-u, --under INTEGER`: make it a subtask of this ls number
* `--top`: move to the top level (no parent)
* `-a, --after INTEGER`: position after this ls number
* `--to TEXT`: move to another list by name
* `--help`: Show this message and exit.

## `gtask rm`

Delete a task by its ls number, or by --id with --list.

**Usage**:

```console
$ gtask rm [OPTIONS] [N]
```

**Arguments**:

* `[N]`: task number from the last ls

**Options**:

* `--id TEXT`: delete by Google task id (needs --list)
* `-l, --list TEXT`: list to use with --id
* `--help`: Show this message and exit.

## `gtask clear`

Remove completed tasks from a list, or from every list.

**Usage**:

```console
$ gtask clear [OPTIONS]
```

**Options**:

* `-l, --list TEXT`: limit to one list (default: all lists)
* `-y, --yes`: do not prompt
* `--help`: Show this message and exit.

## `gtask login`

Run the one-time browser authorization.

**Usage**:

```console
$ gtask login [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `gtask lists`

Manage task lists.

**Usage**:

```console
$ gtask lists [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `add`: Create a task list.
* `rename`: Rename a task list.
* `rm`: Delete a task list and everything in it.

### `gtask lists add`

Create a task list.

**Usage**:

```console
$ gtask lists add [OPTIONS] NAME
```

**Arguments**:

* `NAME`: new list name  [required]

**Options**:

* `--help`: Show this message and exit.

### `gtask lists rename`

Rename a task list.

**Usage**:

```console
$ gtask lists rename [OPTIONS] OLD NEW
```

**Arguments**:

* `OLD`: current name  [required]
* `NEW`: new name  [required]

**Options**:

* `--help`: Show this message and exit.

### `gtask lists rm`

Delete a task list and everything in it.

**Usage**:

```console
$ gtask lists rm [OPTIONS] NAME
```

**Arguments**:

* `NAME`: list name  [required]

**Options**:

* `-y, --yes`: do not prompt
* `--help`: Show this message and exit.
