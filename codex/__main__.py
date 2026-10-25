"""
The one command behind every script:  python -m codex <command>

    serve             the live site at http://127.0.0.1:8000 (or the next free port), plus the save helper (stop with Ctrl+C)
    build             a copy you can open straight from disk, in site/ (or the output: folder)
    players           the players' site, built and opened, to see what they'll see
    check             build both sites into a temporary folder and run the leak check - changes nothing
    publish           put both sites online (needs online: in campaign.yml - see Going online)
    new               set up your own campaign (the wizard)
    transcribe [file] turn a session recording into a transcript
    import-monsters   add monsters from the SRD, Kobold Press's open books, or your own sheet
    import-rules      refresh the Rules tab's SRD text from Open5e (it comes with the site)
    import-character FILE.ccc5e [--player NAME]   add or update a character from CCC5e on the Party page
    add-mentions      wrap known names in [[mentions]] on your story pages
    backup            a dated zip of everything that's yours
    update            bring the engine up to the latest release - your campaign isn't touched
    version           which release this campaign's engine is
    roster            (publish runs this) write the players' site's email -> character list

The setup script installs everything first; the other scripts (CampaignCodex5e, publish, codex...) just
run this with the project's own Python.
"""

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# No compiled-file caches (__pycache__) in the campaign folder - it may be a synced cloud folder.
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
# Material prints a notice about MkDocs 2 on every build; the engine stays on MkDocs 1 (requirements.txt).
os.environ.setdefault("NO_MKDOCS_2_WARNING", "1")

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

def open_when_ready(url: str, give_up: float = 300):
    """Open url in the browser as soon as it answers (checked every half second, for up to 5 minutes)."""
    from urllib.error import HTTPError, URLError
    from urllib.request import urlopen
    start = time.time()
    while time.time() - start < give_up:
        try:
            with urlopen(url, timeout=2):
                webbrowser.open(url)
                return
        except HTTPError as err:
            if err.code < 500:
                webbrowser.open(url)
                return
        except (URLError, OSError):
            pass
        time.sleep(0.5)


def port_free(port: int) -> bool:
    """Nothing else has this port on 127.0.0.1. Windows lets a second server share a port (and the
    first one gets every visit - a stuck copy of the site would leave the page blank), so the check
    asks for the port all to itself."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def cmd_serve(args):
    browser = "--no-browser" not in args
    args = [a for a in args if a != "--no-browser"]
    # The site's address: 127.0.0.1:8000, or the next free port if something else has it (another
    # campaign's site, or a copy that didn't close). -a / --dev-addr chooses one yourself.
    addr = next((args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-a", "--dev-addr")), None)
    if not addr:
        port = next((p for p in range(8000, 8020) if port_free(p)), 8000)
        if port != 8000:
            print(f"Port 8000 is in use (another site, or one that didn't close) - using {port} instead.", flush=True)
        addr = f"127.0.0.1:{port}"
        args += ["-a", addr]
    url = f"http://{addr}/"
    helper = subprocess.Popen([PY, str(ROOT / "tools" / "site_helper.py")], cwd=ROOT)
    if browser:
        # Open the browser once the site actually answers - the first build takes a few seconds,
        # more for a big campaign, and a fixed wait opened it too early ("site can't be reached").
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    print(f"The site is starting at {url} - leave this window open while you use it.", flush=True)
    print("Press Ctrl+C here (or close the window) to stop.\n", flush=True)
    try:
        code = mkdocs("serve", *args, check=False)
    except KeyboardInterrupt:
        code = 0
    finally:
        helper.terminate()
    # A crash (a broken page hook, a bad mkdocs.yml) has to exit nonzero, or the .bat closes its
    # window before the error can be read. Ctrl+C reaching mkdocs first is a normal stop, not a crash.
    if code not in (0, 130, -2, 0xC000013A):
        raise SystemExit(code)


def cmd_build(args):
    site = settings.load()["site_dir"]
    mkdocs("build", "--clean", "--site-dir", site)
    index = site / "index.html"
    print(f"\nBuilt. Open {index} in a browser - it works without a server or the internet.")
    if "--open" in args:
        webbrowser.open(index.as_uri())


def cmd_players(args):
    site = settings.load()["publish_dir"] / "players" / "site"
    mkdocs("build", "--clean", "-f", "mkdocs-players.yml", "--site-dir", site)
    index = site / "index.html"
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


def cmd_import_character(args):
    run(ROOT / "tools" / "import_ccc5e.py", *args)


def cmd_import_rules(args):
    run(ROOT / "tools" / "import_rules.py", *args)


def cmd_add_mentions(args):
    run(ROOT / "tools" / "add_mentions.py", *args)


def cmd_backup(args):
    run(ROOT / "tools" / "backup.py", *args)


def cmd_roster(args):
    run(ROOT / "tools" / "players_roster.py", *args)


def cmd_update(args):
    from codex import update
    raise SystemExit(update.main(args))


def cmd_version(args):
    from codex import update
    print(f"CampaignCodex5e {update.version_here()}")


def cmd_publish(args):
    from codex import publish
    raise SystemExit(publish.main(args))


COMMANDS = {
    "serve": cmd_serve, "build": cmd_build, "players": cmd_players, "check": cmd_check, "publish": cmd_publish, "new": cmd_new,
    "transcribe": cmd_transcribe, "import-monsters": cmd_import_monsters, "import-rules": cmd_import_rules, "import-character": cmd_import_character, "add-mentions": cmd_add_mentions,
    "backup": cmd_backup, "roster": cmd_roster, "update": cmd_update, "version": cmd_version,
    "--version": cmd_version,
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
