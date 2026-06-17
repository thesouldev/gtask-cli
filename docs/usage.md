# Usage

Every gtask command, with examples. Run `gtask --help` or
`gtask <command> --help` for the same information at the terminal.

Back to the [README](../README.md).

## Date format

Dates are day first and you only type as much as you need.

| Input        | Means                                        |
| ------------ | -------------------------------------------- |
| `22`         | the 22nd of the current month and year       |
| `22-06`      | 22 June of the current year                  |
| `22-06-2026` | that exact day, month, and year              |

Separators `-`, `/`, and `.` all work. A two digit year is read as 20xx. If a
partial date has already passed, it rolls forward to the next period: a day
only value moves to next month, a day and month value moves to next year. This
keeps you from creating a task in the past. Google Tasks dates are day level,
so there is no clock time.

## Commands

### add

```bash
gtask add "TEXT" [DATE] [-l LIST]
```

Add a task. With no date the task has no due date. The `-l/--list` option sends
it to a named list; if that list does not exist gtask asks before creating it.
With no `-l`, the task goes to your first list.

```bash
gtask add "email the client" 22
gtask add "pay rent" 1-7 -l Personal
gtask add "draft proposal"
```

### ls

```bash
gtask ls [-l LIST] [--all]
```

List open tasks. By default it shows today and overdue tasks across all lists,
overdue marked in red, as a morning briefing. `-l/--list` limits it to one
list. `--all` shows every open task, including those with no due date and those
due later.

Each row has a number. That number is what you pass to `done` and `rm`, and it
is remembered until the next `ls`.

```bash
gtask ls
gtask ls --all
gtask ls -l Work
```

### done

```bash
gtask done N
```

Complete the task numbered `N` from the last `ls`.

### rm

```bash
gtask rm N
```

Delete the task numbered `N` from the last `ls`.

### lists

```bash
gtask lists
```

Show your task lists.

### login

```bash
gtask login
```

Run the one-time browser authorization. It also runs automatically the first
time you use any command without a cached token. See [setup](setup.md).
