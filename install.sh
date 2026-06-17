#!/usr/bin/env bash
#
# Install gtask: create a virtualenv, install the package, and link the
# command onto your PATH. Re-running it is safe.
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"
BIN_DIR="${GTASK_BIN_DIR:-$HOME/.local/bin}"
CONFIG_DIR="${GTASK_CONFIG_DIR:-$HOME/.config/gtask}"

echo "Creating virtualenv at $VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install -e "$HERE" >/dev/null

mkdir -p "$BIN_DIR"
ln -sf "$VENV/bin/gtask" "$BIN_DIR/gtask"
mkdir -p "$CONFIG_DIR"

echo
echo "Installed: $BIN_DIR/gtask"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Add $BIN_DIR to your PATH to use 'gtask' directly." ;;
esac
echo "Next:"
echo "  1. Put your OAuth client at $CONFIG_DIR/credentials.json (see docs/setup.md)"
echo "  2. Run: gtask login"
