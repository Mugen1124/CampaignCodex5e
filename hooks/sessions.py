"""
The Sessions tab: one page per session in docs/sessions/ (see codex/sessions.py), listed newest
first - so adding a session never means editing the menus.

The tab's sidebar is This Session (index.md) on the DM site, then every session page, newest first,
as "Session 4: The Lighthouse" (the part of its # heading from "Session"; `nav_title:` in its front
matter shows something else). On the players' site This Session isn't there, so the tab - and the
site's home page - open on the latest session. In mkdocs.yml the tab is just:

    - Sessions: []

and this hook fills it in. It's listed first in mkdocs.yml and mkdocs-players.yml.

Session dates: a `date:` in a session page's front matter - when it was played, the time optional -
shows under its name in the menu and under the page's title:

    ---
    order: 4
    date: 2026-10-12 19:30
    ---
    # Greywater — Session 4: The Lighthouse

(A recording from Record & Transcribe is named "Session 2026-10-12 1930.webm": that's the date and time.)
`{{ session-log }}` on any page lists every session, newest first: its name, date, place, and the start
of its "Previously…" recap. Session dates and the log are based on Kosmos's (github.com/IIKosmosII).
"""

import html
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

from mkdocs.structure.pages import Page

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex import sessions as codex_sessions  # noqa: E402

INFO = {}   # src_uri -> {"short": "Session 4: The Lighthouse", "when": "Sat 12 Oct 2026 · 7:30 pm", "place", "recap"}
TITLE = re.compile(r"(Session\s+\d+\s*:.*)$")
RECAP = re.compile(r'^!!!\s+read-aloud\s+"Previously…"\s*\n((?:[ \t]+.*\n|[ \t]*\n)*)', re.M)
PLACEHOLDER = "A short recap to read at the start of next session."


def when(value) -> str:
    """'Sat 12 Oct 2026 · 7:30 pm' (or without the time) from a front-matter date."""
    if isinstance(value, datetime):
        d, t = value, value.time() if (value.hour or value.minute) else None
    elif isinstance(value, date):
        d, t = value, None
    elif value:
        text = str(value).strip()
        for fmt, has_time in (("%Y-%m-%d %H:%M", True), ("%Y-%m-%d %H%M", True), ("%Y-%m-%dT%H:%M", True),
                              ("%Y-%m-%d", False)):
            try:
                parsed = datetime.strptime(text, fmt)
                d, t = parsed, parsed.time() if has_time else None
                break
            except ValueError:
                continue
        else:
            return text          # written some other way: shown as written
    else:
        return ""
    out = f"{d:%a} {d.day} {d:%b %Y}"
    if t:
        hour = t.hour % 12 or 12
        out += f" · {hour}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"
    return out


def _recap(body: str) -> str:
    """The first words of a session's "Previously…" box, as plain text, for the session log."""
    m = RECAP.search(body)
    text = " ".join(m.group(1).split()) if m else ""
    if not text or text == PLACEHOLDER:
        return ""
    text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda x: x.group(2) or x.group(1), text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>|[*_`]", "", text)
    return text if len(text) <= 180 else text[:177].rsplit(" ", 1)[0] + "…"


def on_config(config, **kwargs):
    players = (config.get("extra") or {}).get("audience") == "players"
    docs = Path(config["docs_dir"])
    found = codex_sessions.sessions(docs, warn=True)
    INFO.clear()
    for _, path, title in found:
        front, body = codex_sessions.front_matter((docs / path).read_text(encoding="utf-8"))
        m = TITLE.search(title)
        INFO[path] = {"short": str(front.get("nav_title") or (m.group(1) if m else title)),
                      "when": when(front.get("date")),
                      "place": title.split(" — ")[0].strip() if " — " in title else "",
                      "recap": _recap(body)}
    nav = config.get("nav") or []
    for i, item in enumerate(nav):
        if isinstance(item, dict) and "Sessions" in item:
            children = [] if players else [{"This Session": "index.md"}]
            children += [{INFO[path]["short"]: path} for _, path, _ in found]
            if players and not children:
                children = [{"About this site": "players/about.md"}]
            nav[i] = {"Sessions": children}
            break
    return config


class _ListedPage(Page):
    is_index = False


def on_nav(nav, config, files, **kwargs):
    # This Session is index.md, which the theme would fold into the "Sessions" heading (its section
    # index) - so it's kept as a page of its own, the first line of the sidebar.
    for item in nav.items:
        if getattr(item, "title", None) == "Sessions" and item.children:
            for child in item.children:
                if isinstance(child, Page) and child.file.src_uri == "index.md":
                    child.__class__ = _ListedPage
    return nav


def _log(page) -> str:
    """{{ session-log }}: every session, newest first, as dated entries linking to their pages."""
    if not INFO:
        return '<p class="session-log-empty">No sessions yet.</p>'
    here = Path(page.file.src_uri).parent.as_posix()
    cards = []
    for path, info in INFO.items():
        href = os.path.relpath(path[:-3] + ".html", here if here != "." else ".").replace("\\", "/")
        meta = " · ".join(x for x in (info["when"], info["place"]) if x)
        cards.append(
            f'<a class="session-card" href="{html.escape(href)}">'
            f'<span class="session-card-title">{html.escape(info["short"])}</span>'
            + (f'<span class="session-card-meta">{html.escape(meta)}</span>' if meta else "")
            + (f'<span class="session-card-recap">{html.escape(info["recap"])}</span>' if info["recap"] else "")
            + "</a>")
    return '<div class="session-log">\n' + "\n".join(cards) + "\n</div>"


def on_page_markdown(markdown, page, config, files, **kwargs):
    if "{{ session-log }}" in markdown:
        markdown = markdown.replace("{{ session-log }}", _log(page))
    info = INFO.get(page.file.src_uri)
    if not info or not info["when"]:
        return markdown
    # The date, right under the page's # title.
    return re.sub(r"(?m)^(#\s+.+)$",
                  lambda m: f'{m.group(1)}\n\n<p class="session-date">{html.escape(info["when"])}</p>',
                  markdown, count=1)


def on_post_page(output, page, config, **kwargs):
    # In the side menu, the date under each session's name.
    for info in INFO.values():
        if not info["when"]:
            continue
        label = re.escape(html.escape(info["short"], quote=False))
        output = re.sub(rf'(<span class="md-ellipsis">\s*{label}\s*)(</span>)',
                        lambda m: m.group(1) + f'<span class="session-when">{html.escape(info["when"])}</span>'
                        + m.group(2), output)
    return output
