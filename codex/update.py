"""
`codex update`: bring the engine up to the latest CampaignCodex5e release, leaving your campaign alone.

    codex update                 the latest release from GitHub
    codex update --version v1.4  a particular release
    codex update --zip FILE      a release zip you've already downloaded
    codex update --yes           don't ask before changing anything

What's the engine is listed, file by file, in codex/engine-files.txt (with a fingerprint of each), which
every release carries. Update copies exactly those files in from the release, removes engine files the
release no longer has, and touches nothing else: your pages, data, maps, menus (mkdocs.yml,
mkdocs-players.yml), campaign.yml, campaign.css, README and CLAUDE.md stay as they are. It makes a backup
first, and tells you about any engine file you'd changed yourself (your version is in that backup).
Then it installs any new packages and runs `codex check`.
"""

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
REPO = "Mugen1124/CampaignCodex5e"
MANIFEST = "codex/engine-files.txt"
VERSION = "codex/version.txt"
PY = sys.executable


def fingerprint(data: bytes) -> str:
    """sha256 of a file's contents, with line endings evened out (a Windows checkout has CRLF)."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def read_manifest(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            digest, _, path = line.partition("  ")
            out[path] = digest
    return out


def version_here() -> str:
    p = ROOT / VERSION
    return p.read_text(encoding="utf-8").strip() if p.is_file() else "(before 1.4)"


# ---------------------------------------------------------------- getting the release

def fetch(version: str = None) -> bytes:
    api = f"https://api.github.com/repos/{REPO}/releases/" + (f"tags/{version}" if version else "latest")
    req = Request(api, headers={"Accept": "application/vnd.github+json", "User-Agent": "CampaignCodex5e-update"})
    with urlopen(req, timeout=30) as r:
        release = json.load(r)
    print(f"Downloading {release['tag_name']}...")
    with urlopen(Request(release["zipball_url"], headers={"User-Agent": "CampaignCodex5e-update"}), timeout=120) as r:
        return r.read()


def unpack(data: bytes, dest: Path) -> Path:
    """Extract the release zip; returns the folder that holds the release (GitHub adds one on top)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise SystemExit(f"Refusing a zip with an unsafe path: {name}")
        z.extractall(dest)
    for found in [dest] + [p for p in dest.iterdir() if p.is_dir()]:
        if (found / MANIFEST).is_file():
            return found
    raise SystemExit("That zip isn't a CampaignCodex5e release (it has no codex/engine-files.txt).")


# ---------------------------------------------------------------- settings files from before 1.4

def _top_block(text: str, key: str) -> str:
    """A top-level YAML key and everything indented under it, as written."""
    m = re.search(rf"(?m)^{key}:.*\n(?:(?:[ \t]+.*|[ \t]*)\n)*", text + "\n")
    return m.group(0).rstrip() + "\n" if m else ""


def convert_settings(name: str, inherit: str, header: str) -> str:
    """mkdocs.yml from before the engine/campaign split: keep its name, description and menus,
    take the rest from the engine. The old file is kept beside it. Returns a note, or ''."""
    path = ROOT / name
    if not path.is_file():
        return ""
    old = path.read_text(encoding="utf-8")
    if re.search(rf"(?m)^INHERIT:\s*{re.escape(inherit)}\s*$", old):
        return ""
    keep = [_top_block(old, k) for k in ("site_name", "site_description")]
    nav = _top_block(old, "nav")
    if not nav or not keep[0]:
        return f"{name}: not converted - couldn't find its site_name and nav. See codex/site.yml for the new layout."
    saved = path.with_name(name + ".before-update")
    shutil.copyfile(path, saved)
    path.write_text(header + f"INHERIT: {inherit}\n\n" + "".join(k for k in keep if k) + "\n" + nav, encoding="utf-8")
    note = f"{name}: now just your name and menus (the rest comes from {inherit}); the old one is {saved.name}."
    excl = _top_block(old, "exclude_docs")
    if name == "mkdocs-players.yml" and excl:
        engine = (ROOT / "codex" / "site-players.yml").read_text(encoding="utf-8")
        mine = [ln.strip() for ln in excl.splitlines()[1:] if ln.strip() and ln.strip() not in engine]
        if mine:
            note += ("\n    Your players' site also left out: " + ", ".join(mine) + " - put dm_only: true at the top of"
                     " each of those pages (or add an exclude_docs: to mkdocs-players.yml) so they stay off it.")
    return note


# ---------------------------------------------------------------- the update

def main(args=None) -> int:
    args = list(args or [])
    yes = "--yes" in args
    want = args[args.index("--version") + 1] if "--version" in args else None
    zpath = Path(args[args.index("--zip") + 1]) if "--zip" in args else None

    print(f"This campaign's engine: {version_here()}")
    try:
        data = zpath.read_bytes() if zpath else fetch(want)
    except OSError as err:
        print(f"Couldn't get the release: {err}")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        rel = unpack(data, Path(tmp))
        new_version = (rel / VERSION).read_text(encoding="utf-8").strip() if (rel / VERSION).is_file() else "?"
        new = read_manifest((rel / MANIFEST).read_text(encoding="utf-8"))
        old_text = (ROOT / MANIFEST).read_text(encoding="utf-8") if (ROOT / MANIFEST).is_file() else ""
        old = read_manifest(old_text)

        changed, added, mine = [], [], []
        for path, digest in new.items():
            here = ROOT / path
            if not here.is_file():
                added.append(path)
                continue
            current = fingerprint(here.read_bytes())
            if current != digest:
                changed.append(path)
                if path in old and current != old[path]:
                    mine.append(path)   # differs from the release it came with: changed by hand
        removed = [p for p in old if p not in new and (ROOT / p).is_file()]

        if not (changed or added or removed):
            print(f"Already up to date ({new_version}).")
            return 0
        print(f"\nUpdating to {new_version}: {len(changed)} engine file(s) changed, {len(added)} new, {len(removed)} removed.")
        print("Your pages, data, maps, menus, campaign.yml, campaign.css, README and CLAUDE.md aren't touched.")
        if mine:
            print("\nYou'd changed these engine files yourself - they'll be replaced (your versions go in the backup):")
            for p in mine:
                print("   ", p)
        if not old_text:
            print("\n(This campaign is from before 1.4, so update can't tell which engine files you changed - the backup has them all.)")
        if not yes:
            try:
                answer = input('\nType "yes" to update: ')
            except EOFError:
                answer = ""
            if answer.strip().lower() != "yes":
                print("Nothing was changed.")
                return 1

        print("\nBacking up first...")
        if subprocess.call([PY, str(ROOT / "tools" / "backup.py")], cwd=ROOT) != 0:
            print("The backup failed - nothing was changed.")
            return 1

        req_before = (ROOT / "requirements.txt").read_bytes() if (ROOT / "requirements.txt").is_file() else b""
        for path in changed + added:
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(rel / path, target)
        for path in removed:
            (ROOT / path).unlink()
        shutil.copyfile(rel / MANIFEST, ROOT / MANIFEST)
        if (rel / VERSION).is_file():
            shutil.copyfile(rel / VERSION, ROOT / VERSION)

    notes = [
        convert_settings("mkdocs.yml", "codex/site.yml",
                         "# Your DM site: its name and its menus. Everything else comes from the engine (codex/site.yml,\n"
                         "# replaced by `codex update`). A setting added here wins over the engine's.\n"),
        convert_settings("mkdocs-players.yml", "codex/site-players.yml",
                         "# Your players' site: its name and its menus. How DM material is kept out is the engine's job\n"
                         "# (codex/site-players.yml). Mark DM-only pages dm_only: true.\n"),
    ]
    css = ROOT / "docs" / "stylesheets" / "campaign.css"
    if not css.is_file():
        css.write_text("/* Your campaign's own styles, loaded after the engine's. `codex update` never touches this file. */\n",
                       encoding="utf-8")
    for n in notes:
        if n:
            print("\n" + n)

    if (ROOT / "requirements.txt").read_bytes() != req_before:
        print("\nInstalling updated packages...")
        subprocess.call([PY, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], cwd=ROOT)

    print(f"\nUpdated to {new_version}. Checking that both sites build...")
    code = subprocess.call([PY, "-m", "codex", "check"], cwd=ROOT)
    if code != 0:
        print("\nThe check found a problem (above). Your backup is in the <folder>-backups folder next to this one.")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
