"""
Puts both sites online, each behind its own Cloudflare login (see "Going online" in the guide):

    your DM site        https://<dm_worker>.<subdomain>.workers.dev
    the players' site   https://<players_worker>.<subdomain>.workers.dev

It builds fresh copies (the offline mode off - that's for opening from disk) and uploads exactly
those folders. The players' site is only uploaded if the leak check finds no DM material in it.
After each upload it checks that a signed-out visitor is sent to the login, and warns loudly if not.

Needs Node.js (for Cloudflare's wrangler, run through npx) and a one-time `npx wrangler login`.
The online copies are read-only: make changes with CampaignCodex5e, then publish again.
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
CONFIRMED = ROOT / "publish" / ".signin-confirmed"   # written once the DM confirms step 4 of Going online
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
            {"name": "NOTES", "class_name": "Notes"},   # each player's private notes
            {"name": "PARTY", "class_name": "Party"},   # the live Party page
        ]},
        "migrations": [
            {"tag": "v1", "new_sqlite_classes": ["Tracker"]},
            {"tag": "v2", "new_sqlite_classes": ["Cards"]},
            {"tag": "v3", "new_sqlite_classes": ["Notes"]},
            {"tag": "v4", "new_sqlite_classes": ["Party"]},
        ],
    }
    note = "// Written by `publish` from campaign.yml each time - edit campaign.yml, not this file.\n"
    out = s.get("publish_dir", ROOT / "publish")
    (out / "players").mkdir(parents=True, exist_ok=True)
    (out / "wrangler.jsonc").write_text(note + json.dumps(dm, indent=2) + "\n", encoding="utf-8")
    (out / "players" / "wrangler.jsonc").write_text(note + json.dumps(players, indent=2) + "\n", encoding="utf-8")
    if out != ROOT / "publish":   # building outside this folder: the worker goes along with the players' site
        for module in (ROOT / "publish" / "players").glob("*.*js"):   # worker.js and the modules it imports
            shutil.copyfile(module, out / "players" / module.name)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def login_check(url: str) -> bool:
    """A signed-out visitor should be sent (302) to the Cloudflare login, never shown the site."""
    # Named plainly: Cloudflare's bot screening turns away Python's default name ("Python-urllib")
    # with a 403 before the sign-in is ever reached, which says nothing about whether the site is private.
    req = Request(url, method="GET", headers={"User-Agent": "CampaignCodex5e-publish-check/1.4"})
    location = ""
    try:
        build_opener(_NoRedirect).open(req, timeout=20)
        code = 200
    except HTTPError as err:
        code, location = err.code, err.headers.get("Location") or ""
    except URLError as err:
        print(f"  Couldn't check {url}: {err.reason}")
        return False
    if code in (301, 302, 303, 307) and ".cloudflareaccess.com/" in location:
        print(f"  OK - signed-out visitors to {url} get the login page.")
        return True
    if code in (401, 403):
        print(f"  Couldn't confirm the sign-in for {url}: Cloudflare turned the check away ({code}).")
        print("  Open it in a private browser window - it should ask you to sign in before showing anything.")
        return False
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


def confirm_signin() -> bool:
    """Before the very first upload: make sure the sign-in is on, so nothing is ever public."""
    if CONFIRMED.is_file():
        return True
    print("First upload. Before anything goes online, both sites must be behind a sign-in:")
    print("  Cloudflare dashboard -> Workers & Pages -> Cloudflare Access: on for workers.dev,")
    print("  scope All traffic, policy Cloudflare account. (Going online in the guide, step 4.)")
    try:
        answer = input('Type "yes" if that\'s done: ')
    except EOFError:
        answer = ""
    if answer.strip().lower() != "yes":
        print("Nothing was published.")
        return False
    CONFIRMED.write_text("Sign-in confirmed before the first upload.\n", encoding="utf-8")
    return True


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
    if not confirm_signin():
        return 1

    problems = False
    out = s["publish_dir"]
    if on.get("players_site", True):
        # Players' changes on the live Party page into data/party.yml first, so this build has them
        # and nothing you changed is held back for want of them (tools/site_helper.py pull_party).
        subprocess.call([PY, str(ROOT / "tools" / "site_helper.py"), "--pull-party"], cwd=ROOT)
    print("Building the DM site...")
    if build(["--site-dir", str(out / "site")]) != 0:
        print("\nThe build failed - nothing was published.")
        return 1
    leak_ok = True
    if on.get("players_site", True):
        print("\nBuilding the players' site...")
        if build(["-f", "mkdocs-players.yml", "--site-dir", str(out / "players" / "site")]) != 0:
            print("\nThe players' build failed - nothing was published.")
            return 1
        print()
        leak_ok = subprocess.call([PY, str(ROOT / "tools" / "leak_check.py"),
                                   str(out / "players" / "site")], cwd=ROOT) == 0

    write_configs(s)
    print("\nUploading the DM site...")
    problems |= not deploy(out, s["dm_url"], cmd)

    if on.get("players_site", True):
        if leak_ok:
            print("\nUploading the players' site...")
            subprocess.call([PY, str(ROOT / "tools" / "players_roster.py")], cwd=ROOT)
            problems |= not deploy(out / "players", s["players_url"], cmd)
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
