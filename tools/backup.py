r"""
A dated snapshot of the site's own files - run backup before a session, or before big changes.

Zips everything that's yours (data, pages, hooks, tools, templates, settings, scripts) into a
"<folder>-backups" folder next to this one, as <folder>-<date>-<time>.zip. Leaves out what can be
rebuilt or is kept elsewhere: site/, publish/site/, .map-cache/, sources/, .venv/, and caches. The
newest KEEP snapshots are kept; older ones (only this tool's own zips) are removed.
(If you use git, commits do the same job - this is for everyone else.)

To restore: open the zip and copy back the files you need - nothing is overwritten automatically.
"""

import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = ROOT.name
BACKUPS = ROOT.parent / f"{NAME}-backups"
KEEP = 20
FOLDERS = ["data", "docs", "maps", "hooks", "tools", "templates", "codex"]
SKIP_DIRS = {"__pycache__", ".wrangler", "node_modules", ".venv"}


def files():
    for name in FOLDERS:
        base = ROOT / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not SKIP_DIRS.intersection(path.relative_to(ROOT).parts):
                yield path
    for path in sorted(ROOT.iterdir()):   # settings and scripts at the top level
        if path.is_file() and path.suffix.lower() in (".yml", ".md", ".bat", ".sh", ".command", ".txt"):
            yield path
    jsonc = ROOT / "publish" / "wrangler.jsonc"
    if jsonc.is_file():
        yield jsonc


def main() -> int:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    out = BACKUPS / f"{NAME}-{datetime.now():%Y-%m-%d-%H%M%S}.zip"
    count = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in files():
            z.write(path, Path(NAME) / path.relative_to(ROOT))
            count += 1
    with zipfile.ZipFile(out) as z:   # read it back: a backup that can't be opened is no backup
        bad = z.testzip()
    if bad:
        print(f"WARNING: {out.name} is damaged ({bad}) - run backup again.")
        return 1
    size = out.stat().st_size / 1048576
    print(f"Backed up {count} files to {out} ({size:.1f} MB).")
    old = sorted(BACKUPS.glob(f"{NAME}-*.zip"))[:-KEEP]
    for path in old:
        path.unlink()
    if old:
        print(f"Removed {len(old)} older snapshot(s); the newest {KEEP} are kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
