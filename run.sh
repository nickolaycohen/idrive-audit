#!/usr/bin/env bash
# ==============================================================================
# run.sh — iDrive Device Backup Wizard Launcher
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Activate virtual environment if present
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    source "venv/bin/activate"
elif [ -d "../.venv" ] && [ -f "../.venv/bin/activate" ]; then
    source "../.venv/bin/activate"
fi

python3 device_backup_wizard.py "$@"
