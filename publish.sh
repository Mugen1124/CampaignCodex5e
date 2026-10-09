#!/usr/bin/env bash
# Puts both sites online (see Going online in the guide). Builds, runs the leak check, uploads.
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ folders in the campaign
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
  echo "The site isn't set up yet - run ./setup.sh first."
  exit 1
fi
exec "$VPY" -m codex publish
