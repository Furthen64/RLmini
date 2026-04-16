#!/usr/bin/env bash
set -euo pipefail

PYTHON=python3.12

if ! command -v "$PYTHON" &>/dev/null; then
    echo "ERROR: $PYTHON not found. Please install Python 3.12."
    exit 1
fi

VENV_DIR=".venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Creating virtual environment..."
    rm -rf "$VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

python -m app.editor_main "$@"