"""
Writes codex/engine-files.txt: every file that belongs to the engine, with a fingerprint of each.
`codex update` copies exactly these from a new release and never touches anything else. Run it
before each release (the smoke tests fail if it's out of date):

    python tools/engine_manifest.py            write it
    python tools/engine_manifest.py --check    exit 1 if it's out of date

The engine is the code, the guide, the rules, the scripts, and the SRD data. Everything else -
your pages, data, maps, menus (mkdocs.yml, mkdocs-players.yml), campaign.yml, campaign.css,
README.md, CLAUDE.md - is the campaign's.
"""

import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codex.update import MANIFEST, fingerprint  # noqa: E402

ENGINE = [
    "codex/*", "hooks/*", "tools/*", "templates/*",
    "docs/guide/*", "docs/rules/*", "docs/javascripts/*", "docs/stylesheets/extra.css",
    "docs/players/*.js", "docs/players/tracker.md", "docs/players/notes.md", "docs/recording.md",
    "data/rules/srd.json", "data/monsters/srd.json",
    "publish/players/worker.js",
    "*.bat", "*.sh", "*.command", "requirements.txt", "requirements-transcribe.txt",
    "LICENSE", "CREDITS.md",
]
NEVER = [MANIFEST, "tools/tracker-token.txt"]


def tracked() -> list:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(p for p in out.splitlines() if p)


def engine_files() -> list:
    return [p for p in tracked() if p not in NEVER and any(fnmatch.fnmatch(p, g) for g in ENGINE)]


def render() -> str:
    lines = ["# The engine's files and their fingerprints - written by tools/engine_manifest.py for each release.",
             "# `codex update` replaces exactly these, and nothing else in your campaign."]
    lines += [f"{fingerprint((ROOT / p).read_bytes())}  {p}" for p in engine_files()]
    return "\n".join(lines) + "\n"


def main() -> int:
    text = render()
    path = ROOT / MANIFEST
    if "--check" in sys.argv:
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        if current.replace("\r\n", "\n") != text:
            print(f"{MANIFEST} is out of date - run: python tools/engine_manifest.py")
            return 1
        print(f"{MANIFEST} is up to date ({len(text.splitlines()) - 2} files).")
        return 0
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {MANIFEST}: {len(text.splitlines()) - 2} engine files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
