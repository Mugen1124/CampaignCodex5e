#!/usr/bin/env bash
# CampaignCodex5e - one-time setup for macOS and Linux.
# Installs what the site needs into a private folder (.venv here, or on this computer with
# output: local) - nothing else on this computer is changed. Run it again any time to update.
#   ./setup.sh                      the site
#   ./setup.sh --with-transcribe    the site, plus session transcription (a large download)
set -e
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ folders in the campaign

echo
echo "  =============================================="
echo "    CampaignCodex5e - one-time setup"
echo "  =============================================="
echo

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "  Python 3.10 or newer isn't installed."
  if [ "$(uname)" = "Darwin" ]; then
    echo "  Install it from https://www.python.org/downloads/ (or: brew install python), then run ./setup.sh again."
  else
    echo "  Install it with your package manager (e.g. sudo apt install python3 python3-venv), then run ./setup.sh again."
  fi
  exit 1
fi
echo "  Using: $("$PY" --version)"

# Normally .venv here; with output: local in campaign.yml, on this computer (its place goes in .venv-path).
VENV="$("$PY" codex/paths.py venv)"
if [ "$VENV" = ".venv" ]; then rm -f .venv-path; else printf '%s\n' "$VENV" > .venv-path; fi
if [ ! -x "$VENV/bin/python" ]; then
  echo "  Creating $VENV ..."
  "$PY" -m venv "$VENV" || { echo "  Couldn't create it (on Debian/Ubuntu: sudo apt install python3-venv)."; exit 1; }
fi
echo "  Installing the site's packages..."
"$VENV/bin/python" -m pip install --upgrade pip --quiet
"$VENV/bin/python" -m pip install -r requirements.txt
if [ "$1" = "--with-transcribe" ]; then
  echo
  echo "  Installing session transcription (a large download)..."
  "$VENV/bin/python" -m pip install -r requirements-transcribe.txt
fi
chmod +x CampaignCodex5e.sh CampaignCodex5e.command publish.sh codex.sh 2>/dev/null || true

echo
echo "  Setup complete."
echo
read -r -p "  Set up your own campaign now? (y = yes, n = keep exploring the demo first) [y/n]: " ANSWER
case "$ANSWER" in
  [Yy]*) "$VENV/bin/python" -m codex new ;;
esac

echo
echo "  Starting the site - leave this window open while you use it. From now on, open CampaignCodex5e.command (Mac) or run ./CampaignCodex5e.sh"
echo
exec "$VENV/bin/python" -m codex serve
