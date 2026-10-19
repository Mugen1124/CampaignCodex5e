"""Session dates: each session in the Sessions tab's menu shows as "Session 4: The Lighthouse" with
its date and time underneath, newest first under This Session, and the session page itself shows the
date under its title, like a blog post. Campaign-owned (not an engine file - `codex update` leaves it
alone); listed in the hooks: of mkdocs.yml and mkdocs-players.yml, after hooks/sessions.py.

The date comes from the session page's front matter:

    ---
    order: 4
    date: 2026-10-12 19:30     # when the session was played (the time is optional)
    ---
    # Greywater — Session 4: The Lighthouse

The home page (the Sessions tab's "All sessions") lists them all with `{{ session-log }}`: each
session's name, date, place and the start of its "Previously…" recap, newest first.

A recording made with Record & Transcribe is named "Session 2026-10-12 1930.webm" - that's the date
and time to copy in. A page with no date: still gets its "Session 4: ..." menu entry, just undated.
Changes to this file need CampaignCodex5e restarted.
"""
import html
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex import sessions as codex_sessions  # noqa: E402

DOCS = [None]
INFO = {}          # src_uri -> {"short": "Session 4: The Lighthouse", "when": "Sat 12 Oct 2026 · 7:30 pm"}
TITLE = re.compile(r"(Session\s+\d+\s*:.*)$")


def _when(value) -> str:
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


RECAP = re.compile(r'^!!!\s+read-aloud\s+"Previously…"\s*\n((?:[ \t]+.*\n|[ \t]*\n)*)', re.M)
PLACEHOLDER = "A short recap to read at the start of next session."


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
    DOCS[0] = Path(config["docs_dir"])
    INFO.clear()
    for order, path, title in codex_sessions.sessions(DOCS[0]):
        front, body = codex_sessions.front_matter((DOCS[0] / path).read_text(encoding="utf-8"))
        m = TITLE.search(title)
        short = str(front.get("nav_title") or (m.group(1) if m else title))
        place = title.split(" — ")[0].strip() if " — " in title else ""
        INFO[path] = {"short": short, "when": _when(front.get("date")), "place": place, "recap": _recap(body)}
    # The Sessions tab: "All sessions" (the home page) first, then each session as "Session N: Title".
    for item in config.get("nav") or []:
        if isinstance(item, dict) and "Sessions" in item:
            item["Sessions"] = [{INFO[p]["short"]: p} if p in INFO else {("All sessions" if p == "index.md" else t): p}
                                for entry in item["Sessions"] for t, p in entry.items()]
    return config


def _log(page) -> str:
    """{{ session-log }}: every session, newest first, as dated entries linking to their pages."""
    if not INFO:
        return '<p class="session-log-empty">No sessions yet. <strong>New session</strong> starts one.</p>'
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
    # In the side menu, the date and time under each session's entry.
    for info in INFO.values():
        if not info["when"]:
            continue
        label = re.escape(html.escape(info["short"], quote=False))
        output = re.sub(rf'(<span class="md-ellipsis">\s*{label}\s*)(</span>)',
                        lambda m: m.group(1) + f'<span class="session-when">{html.escape(info["when"])}</span>'
                        + m.group(2), output)
    return output
