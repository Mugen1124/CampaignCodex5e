#!/usr/bin/env bash
# CampaignCodex5e: starts your campaign site at http://127.0.0.1:8000, plus the save helper, and
# opens it in your browser once it's ready. Leave this window open while you use the site; close
# it (or press Ctrl+C) to stop.
# (On a Mac, double-click this file: it opens in Terminal.)
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ folders in the campaign
printf '\033]0;CampaignCodex5e\007'   # the window's title
VPY=.venv/bin/python
if [ -f .venv-path ]; then   # setup put it outside the folder (output: local)
  V="$(head -n 1 .venv-path)"
  if [ ! -x "$V/bin/python" ]; then   # written on another computer: the same place in this one's cache
    case "$(uname)" in Darwin) BASE="$HOME/Library/Caches" ;; *) BASE="${XDG_CACHE_HOME:-$HOME/.cache}" ;; esac
    T="${V#*CampaignCodex5e/}"
    [ "$T" = "$V" ] && T="${V#*CampaignCodex5e\\}"   # a Windows path
    [ "$T" != "$V" ] && V="$BASE/CampaignCodex5e/$(printf '%s' "$T" | tr '\\' '/')"
  fi
  VPY="$V/bin/python"
fi
if [ ! -x "$VPY" ]; then
  echo "CampaignCodex5e isn't set up yet - run ./setup.sh first."
  read -r -p "Press Enter to close." _
  exit 1
fi
exec "$VPY" -m codex serve
