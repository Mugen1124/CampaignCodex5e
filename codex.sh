#!/usr/bin/env bash
# Any command:  ./codex.sh build | check | new | backup | add-mentions | import-monsters | transcribe | publish | serve
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "The site isn't set up yet - run ./setup.sh first."
  exit 1
fi
exec .venv/bin/python -m codex "$@"
