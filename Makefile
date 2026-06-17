VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
GTASK := $(VENV)/bin/gtask

.PHONY: dev-install install build format lint test run-tests run docs \
	site site-build clean

dev-install:
	@python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip
	@$(PIP) install -e ".[dev]"
	@git config core.hooksPath .githooks

install:
	@command -v pipx >/dev/null 2>&1 && pipx install --force . || ./install.sh

build:
	@$(PY) -m build

format:
	@$(PY) -m black src tests

lint:
	@$(PY) -m pylint src

test:
	@$(PY) -m pytest -q

run-tests: test

run:
	@$(GTASK) $(ARGS)

docs:
	@$(PY) -m typer gtask.cli utils docs --name gtask --output /tmp/gtask-usage.md
	@mkdir -p site/src/content/docs/reference
	@printf -- '---\ntitle: CLI reference\ndescription: Every gtask command and option.\n---\n\n' \
		> site/src/content/docs/reference/usage.md
	@tail -n +2 /tmp/gtask-usage.md >> site/src/content/docs/reference/usage.md
	@rm -f /tmp/gtask-usage.md

site:
	@npm --prefix site run dev

site-build:
	@npm --prefix site run build

clean:
	@rm -rf $(VENV) dist build *.egg-info src/*.egg-info .pytest_cache
	@find . -type d -name __pycache__ -prune -exec rm -rf {} +
