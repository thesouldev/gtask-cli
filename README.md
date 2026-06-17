<div align="center">

# gtask-cli

**Add and manage Google Tasks from the terminal.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/thesouldev/gtask-cli/pulls)

</div>

---

## Overview

gtask is a command line tool for adding and managing Google Tasks on one
account. A task you capture at the desk lands in the same account your phone
and iPad widgets read, and tasks with a due date appear in Google Calendar.
The OAuth scope is tasks only, so it cannot read or touch Gmail, Drive, or
Calendar.

It is built to stay small. The aim is a task driven day with the least
friction between a thought and it being captured.

## Features

- Add a task in one command with a terse, day first date format
- A default briefing of today and overdue tasks across all lists
- Complete or delete tasks by the number shown, never a raw id
- Target an existing list or create one on the fly
- Tasks only OAuth scope, with the token cached locally
- Built with Typer and Rich for a clean terminal experience

## Getting started

### Prerequisites

- Python 3.10 or newer
- A Google account that holds your tasks
- A one-time Google OAuth client, see [docs/setup.md](docs/setup.md)
- pipx, only if you use `make install`

### Installation

Install `gtask` as a system wide command. Clone the repo, then use one of:

```bash
git clone git@github.com:thesouldev/gtask-cli.git
cd gtask-cli

make install      # installs and updates via pipx (needs pipx)
# or
./install.sh      # sets up a virtualenv and links gtask onto your PATH
```

`make install` is also how you update to the latest version after a `git pull`.

Confirm it is on your PATH:

```bash
gtask --help
```

Then complete the [one-time setup](docs/setup.md) and authorize:

```bash
gtask login
```

### Development

For working on gtask itself, use the editable install with the dev tools
(black, pylint, pytest):

```bash
make dev-install
make test
```

### Usage

```bash
gtask add "email the client" 22        # due the 22nd of this month
gtask add "pay rent" 1-7 -l Personal   # 1 July, in the Personal list
gtask add "draft proposal"             # no due date
gtask ls                               # today and overdue across lists
gtask done 2                           # complete task #2 from the last ls
```

Full command reference is in [docs/usage.md](docs/usage.md).

## Documentation

- [Setup](docs/setup.md) one-time Google OAuth client and login
- [Usage](docs/usage.md) every command, with the date format
- [Configuration](docs/configuration.md) file locations and environment
- [Architecture](docs/architecture.md) design, modules, and roadmap

## Project structure

```
.
├── src/gtask/   config, auth, client, dates, store, cli
├── tests/       unit tests
├── docs/        setup, usage, configuration, architecture
├── Makefile     dev and install commands
└── install.sh   one-shot installer
```

## Contributing

Contributions are welcome. Open an issue to discuss substantial changes before
sending a pull request.

## License

This project is distributed under the GNU General Public License v3.0. See
[LICENSE](LICENSE) for the full text.
