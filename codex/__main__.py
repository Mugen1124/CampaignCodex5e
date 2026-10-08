"""
The one command behind every script:  python -m codex <command>

    serve             the live site at http://127.0.0.1:8000, plus the save helper (stop with Ctrl+C)
    build             a copy you can open straight from disk, in site/
    players           the players' site, built into publish/players/site/ and opened, to see what they'll see
    check             build both sites into a temporary folder and run the leak check - changes nothing
    publish           put both sites online (needs online: in campaign.yml - see Going online)
    new               set up your own campaign (the wizard)
    transcribe [file] turn a session recording into a transcript
    import-monsters   add monsters from the SRD, Kobold Press's open books, or your own sheet
    import-rules      refresh the Rules tab's SRD text from Open5e (it comes with the site)
    add-mentions      wrap known names in [[mentions]] on your story pages
    backup            a dated zip of everything that's yours
    roster            (publish runs this) write the players' site's email -> character list

The setup script installs everything first; the other scripts (serve, build, publish...) just
run this with the project's own Python.
"""

import os
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codex import settings  # noqa: E402

PY = sys.executable


def run(*args, env=None, check=True) -> int:
    code = subprocess.call([PY, *map(str, args)], cwd=ROOT, env=env)
    if check and code != 0:
        raise SystemExit(code)
    return code


def mkdocs(*args, offline=True, check=True) -> int:
    env = dict(os.environ, OFFLINE="true" if offline else "false")
    return run("-m", "mkdocs", *args, env=env, check=check)


# ---------------------------------------------------------------- commands

def cmd_serve(args):
    helper = subprocess.Popen([PY, str(ROOT / "tools" / "site_helper.py")], cwd=ROOT)
    if "--no-browser" not in args:
        threading.Timer(4, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    print("The site is starting at http://127.0.0.1:8000 - leave this window open while you use it.")
    print("Press Ctrl+C here (or close the window) to stop.\n")
    try:
        mkdocs("serve", *[a for a in args if a != "--no-browser"], check=False)
    except KeyboardInterrupt:
        pass
    finally:
        helper.terminate()


def cmd_build(args):
    mkdocs("build", "--clean")
    index = ROOT / "site" / "index.html"
    print(f"\nBuilt. Open {index} in a browser - it works without a server or the internet.")
    if "--open" in args:
        webbrowser.open(index.as_uri())


def cmd_players(args):
    mkdocs("build", "--clean", "-f", "mkdocs-players.yml")
    index = ROOT / "publish" / "players" / "site" / "index.html"
    print(f"\nBuilt the players' site. Opening {index}")
    if "--no-open" not in args:
        webbrowser.open(index.as_uri())


def cmd_check(args):
    """Both builds into a temporary folder, then the leak check. Exit code 1 if anything's wrong."""
    with tempfile.TemporaryDirectory() as tmp:
        dm, players = Path(tmp) / "dm", Path(tmp) / "players"
        print("Building the DM site...")
        mkdocs("build", "--clean", "--site-dir", dm, offline=False)
        print("\nBuilding the players' site...")
        mkdocs("build", "--clean", "-f", "mkdocs-players.yml", "--site-dir", players, offline=False)
        print()
        code = run(ROOT / "tools" / "leak_check.py", players, check=False)
    print("\nAll good." if code == 0 else "\nThe leak check found DM material in the players' site (above).")
    raise SystemExit(code)


def cmd_new(args):
    run(ROOT / "tools" / "new_campaign.py", *args)


def cmd_transcribe(args):
    run(ROOT / "tools" / "transcribe.py", *args)


def cmd_import_monsters(args):
    if not args:
        args = ["srd"]
    elif len(args) == 1 and args[0].lower().endswith(".json") and Path(args[0]).is_file():
        args = ["file", args[0]]     # a sheet dropped onto the script
    run(ROOT / "tools" / "import_monsters.py", *args)


def cmd_import_rules(args):
    run(ROOT / "tools" / "import_rules.py", *args)


def cmd_add_mentions(args):
    run(ROOT / "tools" / "add_mentions.py", *args)


def cmd_backup(args):
    run(ROOT / "tools" / "backup.py", *args)


def cmd_roster(args):
    run(ROOT / "tools" / "players_roster.py", *args)


def cmd_publish(args):
    from codex import publish
    raise SystemExit(publish.main(args))


COMMANDS = {
    "serve": cmd_serve, "build": cmd_build, "players": cmd_players, "check": cmd_check, "publish": cmd_publish, "new": cmd_new,
    "transcribe": cmd_transcribe, "import-monsters": cmd_import_monsters, "import-rules": cmd_import_rules, "add-mentions": cmd_add_mentions,
    "backup": cmd_backup, "roster": cmd_roster,
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help") or argv[0] not in COMMANDS:
        print(__doc__)
        return 0 if not argv or argv[0] in ("-h", "--help", "help") else 2
    COMMANDS[argv[0]](argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
