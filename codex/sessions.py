"""
The session pages (docs/sessions/*.md), newest first. Used by hooks/sessions.py (the Sessions tab),
hooks/players.py (the players' home page is the latest session), and hooks/entities.py (what the
players have come across is whatever the session pages mention).

Each session page starts with its place in the order:

    ---
    order: 4
    ---
    # Greywater — Session 4: The Lighthouse
"""

import logging
import re
from pathlib import Path

import yaml

log = logging.getLogger("mkdocs.hooks.sessions")

FOLDER = "sessions"
FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
H1 = re.compile(r"(?m)^#\s+(.+?)\s*(\{[^}]*\})?\s*$")


def front_matter(text: str) -> tuple:
    """(front matter dict, the rest of the page)."""
    m = FRONT.match(text)
    return ((yaml.safe_load(m.group(1)) or {}) if m else {}), (text[m.end():] if m else text)


def sessions(docs: Path, warn: bool = False) -> list:
    """[(order, docs-relative path, title)], newest first."""
    out = []
    for p in sorted((Path(docs) / FOLDER).glob("*.md")):
        front, body = front_matter(p.read_text(encoding="utf-8"))
        h1 = H1.search(body)
        title = str(front.get("nav_title") or (h1.group(1) if h1 else p.stem))
        if warn and "order" not in front:
            log.warning("%s/%s has no order: in its front matter - it's listed last", FOLDER, p.name)
        out.append((float(front.get("order", -1)), f"{FOLDER}/{p.name}", title))
    return sorted(out, key=lambda s: (-s[0], s[1]))


def latest(docs: Path):
    found = sessions(docs)
    return found[0][1] if found else None


def pages(docs: Path) -> list:
    """Every session page as a Path, newest first."""
    return [Path(docs) / path for _, path, _ in sessions(docs)]
