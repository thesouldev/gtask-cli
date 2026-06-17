VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
GTASK := $(VENV)/bin/gtask

.PHONY: dev-install install build format lint test run-tests run clean

dev-install:
	@python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip
	@$(PIP) install -e ".[dev]"

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

clean:
	@rm -rf $(VENV) dist build *.egg-info src/*.egg-info .pytest_cache
	@find . -type d -name __pycache__ -prune -exec rm -rf {} +
