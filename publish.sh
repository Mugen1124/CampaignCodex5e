#!/usr/bin/env bash
# Puts both sites online (see Going online in the guide). Builds, runs the leak check, uploads.
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ folders in the campaign
VPY=.venv/bin/python
[ -f .venv-path ] && VPY="$(head -n 1 .venv-path)/bin/python"   # setup put it outside the folder (output: local)
if [ ! -x "$VPY" ]; then
  echo "The site isn't set up yet - run ./setup.sh first."
  exit 1
fi
exec "$VPY" -m codex publish
