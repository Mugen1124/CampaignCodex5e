"""
Puts both sites online, each behind its own Cloudflare login (see "Going online" in the guide):

    your DM site        https://<dm_worker>.<subdomain>.workers.dev
    the players' site   https://<players_worker>.<subdomain>.workers.dev

It builds fresh copies (the offline mode off - that's for opening from disk) and uploads exactly
those folders. The players' site is only uploaded if the leak check finds no DM material in it.
After each upload it checks that a signed-out visitor is sent to the login, and warns loudly if not.

Needs Node.js (for Cloudflare's wrangler, run through npx) and a one-time `npx wrangler login`.
The online copies are read-only: make changes with serve, then publish again.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from codex import settings

ROOT = settings.ROOT
PY = sys.executable
COMPAT = "2026-09-23"


def wrangler() -> list:
    if shutil.which("wrangler"):
        return [shutil.which("wrangler")]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "wrangler"]
    return []


def write_configs(s: dict):
    on = s["online"]
    dm = {
        "name": on["dm_worker"],
        "compatibility_date": COMPAT,
        "workers_dev": True,
        "preview_urls": False,
        "assets": {"directory": "./site"},
    }
    players = {
        "name": on["players_worker"],
        "compatibility_date": COMPAT,
        "workers_dev": True,
        "preview_urls": False,
        "main": "worker.js",
        "assets": {"directory": "./site", "binding": "ASSETS"},
        "vars": {"ACCESS_TEAM": s["access_url"]},
        "durable_objects": {"bindings": [
            {"name": "TRACKER", "class_name": "Tracker"},
            {"name": "CARDS", "class_name": "Cards"},
        ]},
        "migrations": [
            {"tag": "v1", "new_sqlite_classes": ["Tracker"]},
            {"tag": "v2", "new_sqlite_classes": ["Cards"]},
        ],
    }
    note = "// Written by `publish` from campaign.yml each time - edit campaign.yml, not this file.\n"
    (ROOT / "publish" / "wrangler.jsonc").write_text(note + json.dumps(dm, indent=2) + "\n", encoding="utf-8")
    (ROOT / "publish" / "players" / "wrangler.jsonc").write_text(note + json.dumps(players, indent=2) + "\n",
                                                                  encoding="utf-8")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def login_check(url: str) -> bool:
    """A signed-out visitor should be sent (302) to the Cloudflare login, never shown the site."""
    try:
        build_opener(_NoRedirect).open(Request(url, method="GET"), timeout=20)
        code = 200
    except HTTPError as err:
        code = err.code
    except URLError as err:
        print(f"  Couldn't check {url}: {err.reason}")
        return False
    if code in (301, 302, 303, 307):
        print(f"  OK - signed-out visitors to {url} get the login page.")
        return True
    print("*" * 76)
    print(f"  WARNING: {url} answered {code} instead of sending visitors to the login.")
    print("  It may be PUBLIC. In the Cloudflare dashboard (Zero Trust -> Access -> Applications),")
    print("  check the application for that address and its policy. See Going online in the guide.")
    print("*" * 76)
    return False


def deploy(folder: Path, url: str, cmd: list) -> bool:
    if subprocess.call(cmd + ["deploy"], cwd=folder) != 0:
        print(f"  The upload failed - {url} is unchanged.")
        return False
    return login_check(url)


def build(args: list, offline=False) -> int:
    env = dict(os.environ, OFFLINE="true" if offline else "false")
    return subprocess.call([PY, "-m", "mkdocs", "build", "--clean", *args], cwd=ROOT, env=env)


def main(args=None) -> int:
    s = settings.load()
    on = s["online"]
    missing = [k for k in ("dm_worker", "subdomain") if not on.get(k)]
    if on.get("players_site", True):
        missing += [k for k in ("players_worker", "access_team") if not on.get(k)]
    if not on.get("enabled") or missing:
        print("Going online isn't set up yet." if not on.get("enabled") else
              "campaign.yml is missing: " + ", ".join(f"online: {k}" for k in missing))
        print("Follow 'Going online' in the site's guide, then fill in online: in campaign.yml.")
        return 1
    cmd = wrangler()
    if not cmd:
        print("Node.js isn't installed (publish uses Cloudflare's wrangler through npx).")
        print("Install Node.js from https://nodejs.org, then run:  npx wrangler login")
        return 1

    problems = False
    print("Building the DM site...")
    if build(["--site-dir", str(ROOT / "publish" / "site")]) != 0:
        print("\nThe build failed - nothing was published.")
        return 1
    leak_ok = True
    if on.get("players_site", True):
        print("\nBuilding the players' site...")
        if build(["-f", "mkdocs-players.yml", "--site-dir", str(ROOT / "publish" / "players" / "site")]) != 0:
            print("\nThe players' build failed - nothing was published.")
            return 1
        print()
        leak_ok = subprocess.call([PY, str(ROOT / "tools" / "leak_check.py"),
                                   str(ROOT / "publish" / "players" / "site")], cwd=ROOT) == 0

    write_configs(s)
    print("\nUploading the DM site...")
    problems |= not deploy(ROOT / "publish", s["dm_url"], cmd)

    if on.get("players_site", True):
        if leak_ok:
            print("\nUploading the players' site...")
            subprocess.call([PY, str(ROOT / "tools" / "players_roster.py")], cwd=ROOT)
            problems |= not deploy(ROOT / "publish" / "players", s["players_url"], cmd)
        else:
            problems = True
            print("\n" + "*" * 76)
            print("  The players' site was NOT uploaded - the leak check found DM material in it")
            print("  (listed above). Fix those, then publish again.")
            print("*" * 76)

    print("\nFinished, with problems - see above." if problems else "\nDone - everything is up to date.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
