"""
Where things live on this computer - with no packages needed, so setup can ask before anything is
installed:

    python codex/paths.py venv     the folder for this campaign's Python packages

Normally that's .venv in the campaign folder. With `output: local` in campaign.yml (a campaign kept in
Google Drive, Dropbox, OneDrive or iCloud) it's on this computer instead, next to the built sites, and
setup leaves its location in .venv-path for the launchers to read.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", str(text).lower().replace("’", "").replace("'", ""))
    return re.sub(r"[\s_]+", "-", s).strip("-")


def local_dir() -> Path:
    """This computer's own cache folder for CampaignCodex5e (never a synced folder)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "CampaignCodex5e"


def _setting(text: str, key: str) -> str:
    m = re.search(rf"(?m)^{key}:[ \t]*(.*?)[ \t]*(?:#.*)?$", text)
    return m.group(1).strip().strip("'\"") if m else ""


def venv_dir(root: Path = ROOT) -> str:
    conf = Path(root) / "campaign.yml"
    text = conf.read_text(encoding="utf-8") if conf.is_file() else ""
    if _setting(text, "output").lower() != "local":
        return ".venv"
    return str(local_dir() / (slug(_setting(text, "name")) or "campaign") / "venv")


if __name__ == "__main__":
    if sys.argv[1:] == ["venv"]:
        print(venv_dir())
    else:
        print(__doc__)
