#!/usr/bin/env bash
# CampaignCodex5e: starts your campaign site at http://127.0.0.1:8000, plus the save helper, and
# opens it in your browser once it's ready. Leave this window open while you use the site; close
# it (or press Ctrl+C) to stop.
cd "$(dirname "$0")"
printf '\033]0;CampaignCodex5e\007'   # the window's title
if [ ! -x .venv/bin/python ]; then
  echo "CampaignCodex5e isn't set up yet - run ./setup.sh first."
  exit 1
fi
exec .venv/bin/python -m codex serve
