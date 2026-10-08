#!/usr/bin/env bash
# CampaignCodex5e: starts your campaign site at http://127.0.0.1:8000, plus the save helper, and
# opens it in your browser once it's ready. Leave this window open while you use the site; close
# it (or press Ctrl+C) to stop.
# (On a Mac, double-click this file: it opens in Terminal.)
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ folders in the campaign
printf '\033]0;CampaignCodex5e\007'   # the window's title
VPY=.venv/bin/python
[ -f .venv-path ] && VPY="$(head -n 1 .venv-path)/bin/python"   # setup put it outside the folder (output: local)
if [ ! -x "$VPY" ]; then
  echo "CampaignCodex5e isn't set up yet - run ./setup.sh first."
  read -r -p "Press Enter to close." _
  exit 1
fi
exec "$VPY" -m codex serve
