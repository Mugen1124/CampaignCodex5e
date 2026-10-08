#!/usr/bin/env bash
# The live site at http://127.0.0.1:8000, plus the save helper. Leave the window open; close it to stop.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "The site isn't set up yet - run ./setup.sh first."
  exit 1
fi
exec .venv/bin/python -m codex serve
