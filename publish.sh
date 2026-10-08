#!/usr/bin/env bash
# Puts both sites online (see Going online in the guide). Builds, runs the leak check, uploads.
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ folders in the campaign
if [ ! -x .venv/bin/python ]; then
  echo "The site isn't set up yet - run ./setup.sh first."
  exit 1
fi
exec .venv/bin/python -m codex publish
