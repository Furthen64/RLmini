#!/usr/bin/env bash
set -euo pipefail

PYTHON=python3.12

# Check Python 3.12 is available
if ! command -v "$PYTHON" &>/dev/null; then
    echo "ERROR: $PYTHON not found. Please install Python 3.12."
    exit 1
fi

VENV_DIR=".venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# Recreate venv if missing or broken
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Creating virtual environment..."
    rm -rf "$VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
fi

# Activate
source "$VENV_DIR/bin/activate"

# Upgrade pip
python -m pip install --upgrade pip -q

# Install requirements
python -m pip install -r requirements.txt -q

# Launch
python -m app.main
