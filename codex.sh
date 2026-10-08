#!/usr/bin/env bash
# Any command:  ./codex.sh build | check | new | backup | add-mentions | import-monsters | transcribe | publish | serve
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ folders in the campaign
VPY=.venv/bin/python
[ -f .venv-path ] && VPY="$(head -n 1 .venv-path)/bin/python"   # setup put it outside the folder (output: local)
if [ ! -x "$VPY" ]; then
  echo "The site isn't set up yet - run ./setup.sh first."
  exit 1
fi
exec "$VPY" -m codex "$@"
