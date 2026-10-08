"""
The Sessions tab: one page per session in docs/sessions/ (see codex/sessions.py), listed newest
first - so adding a session never means editing the menus.

The tab's sidebar is This Session (index.md) on the DM site, then every session page, newest first,
titled by its # heading (or `nav_title:` in its front matter, to show something shorter). On the
players' site This Session isn't there, so the tab - and the site's home page - open on the latest
session. In mkdocs.yml the tab is just:

    - Sessions: []

and this hook fills it in. It's listed first in mkdocs.yml and mkdocs-players.yml.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex import sessions as codex_sessions  # noqa: E402


def on_config(config, **kwargs):
    players = (config.get("extra") or {}).get("audience") == "players"
    found = codex_sessions.sessions(Path(config["docs_dir"]), warn=True)
    nav = config.get("nav") or []
    for i, item in enumerate(nav):
        if isinstance(item, dict) and "Sessions" in item:
            children = [] if players else [{"This Session": "index.md"}]
            children += [{title: path} for _, path, title in found]
            if players and not children:
                children = [{"About this site": "players/about.md"}]
            nav[i] = {"Sessions": children}
            break
    return config
