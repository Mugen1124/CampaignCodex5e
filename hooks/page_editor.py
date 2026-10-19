"""Page editor: a pencil beside each page's title opens that page in an editor and saves it back
to docs/. Session pages, This Session and the World/town pages open in a word-processor style
editor (Toast UI Editor, loaded only when opened, usage statistics off); the rest open as Markdown
(EasyMDE), and either can switch to the other. Campaign-owned (not an engine file - `codex update` leaves it alone),
listed in the hooks: of mkdocs.yml only, so the players' site never has it.

The pencil only works while the site is served on this computer (CampaignCodex5e); the editor
saves through this hook's own endpoint on the site's server:
    GET  /__page/get?src=cities/greywater/index.md  the page's Markdown, as written
    POST /__page/save                                saves it (JSON: src, text, hash)
Only Markdown files inside docs/ can be read or written. Every save keeps a copy of the file as
it was in sources/backups/pages/ first, and refuses if the file changed since it was opened.
Pages built by hooks rather than from a file (the SRD rules, for example) get no pencil.

It also runs the New session button on This Session:
    GET  /__page/new-session-info   the next session number, and the town the party is in
    POST /__page/new-session        makes docs/sessions/<town>-<n>.md (order, date: now)
    POST /__page/delete-session     moves a session page to sources/backups/deleted/ (Delete session)
    POST /__page/upload?src=&name=  a picture (PNG/JPEG/GIF/WebP) into docs/uploads/, for the editor
Changes to this file need CampaignCodex5e restarted.
"""
import hashlib
import json
import posixpath
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

import yaml

ROOT = [None]          # the campaign folder
DOCS = [None]          # docs/
LOCK = threading.Lock()
MAX_TEXT = 2 * 1024 * 1024
MAX_IMAGE = 15 * 1024 * 1024
# Picture types the editor accepts, with how each file starts (SVG is left out: it can hold scripts).
IMAGE_TYPES = {"image/png": (".png", (b"\x89PNG",)), "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
               "image/gif": (".gif", (b"GIF87a", b"GIF89a")), "image/webp": (".webp", (b"RIFF",))}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _page_file(src: str):
    """docs/<src> if src names a Markdown file inside docs/, else None."""
    if not src or not src.endswith(".md") or "\\" in src or src.startswith("/"):
        return None
    docs = DOCS[0].resolve()
    path = (docs / src).resolve()
    if docs not in path.parents or not path.is_file():
        return None
    return path


# ---------------------------------------------------------------- MkDocs events

def on_config(config, **kwargs):
    ROOT[0] = Path(config.config_file_path).parent
    DOCS[0] = Path(config["docs_dir"])


def on_post_page(output, page, config, **kwargs):
    src = page.file.src_uri
    if not _page_file(src):
        return output
    here = posixpath.dirname(page.file.dest_uri) or "."
    rel = lambda p: posixpath.relpath(p, here)
    head = (f'<link rel="stylesheet" href="{rel("javascripts/vendor/easymde.min.css")}">\n')
    tail = (f'<script>window.PAGE_EDITOR_SRC = {json.dumps(src)}; '
            f'window.PAGE_EDITOR_VENDOR = {json.dumps(rel("javascripts/vendor") + "/")};</script>\n'
            f'<script src="{rel("javascripts/vendor/easymde.min.js")}"></script>\n'
            f'<script src="{rel("javascripts/page-editor.js")}"></script>\n')
    return output.replace("</head>", head + "</head>", 1).replace("</body>", tail + "</body>", 1)


def on_serve(server, config, builder, **kwargs):
    if getattr(server, "_page_editor", False):
        return server
    app = server.get_app()

    def wrapped(environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path.startswith("/__page/"):
            return _api(environ, start_response, path)
        if path.startswith("/uploads/") and environ.get("REQUEST_METHOD") in ("GET", "HEAD"):
            # A picture just added shows in the editor at once, before the site has rebuilt.
            served = _serve_upload(path, start_response)
            if served is not None:
                return served
        return app(environ, start_response)

    server.set_app(wrapped)
    server._page_editor = True
    return server


# ---------------------------------------------------------------- reading and saving

def _reply(start_response, status: int, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    start_response(f"{status} {'OK' if status == 200 else 'Error'}",
                   [("Content-Type", "application/json"), ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store")])
    return [body]


def _api(environ, start_response, path):
    method = environ.get("REQUEST_METHOD", "GET")
    try:
        if method == "GET" and path == "/__page/get":
            src = (parse_qs(environ.get("QUERY_STRING", "")).get("src") or [""])[0]
            file = _page_file(src)
            if not file:
                return _reply(start_response, 404, {"error": "This page has no file of its own to edit."})
            text = file.read_text(encoding="utf-8")
            return _reply(start_response, 200, {"src": src, "text": text, "hash": _hash(text)})
        if method == "GET" and path == "/__page/new-session-info":
            return _reply(start_response, 200, _new_session_info())
        if method == "POST" and path in ("/__page/new-session", "/__page/delete-session"):
            if not environ.get("CONTENT_TYPE", "").startswith("application/json"):
                return _reply(start_response, 415, {"error": "Expected JSON."})
            length = int(environ.get("CONTENT_LENGTH") or 0)
            data = json.loads(environ["wsgi.input"].read(min(length, 65536)) or b"{}")
            with LOCK:
                status, payload = _new_session(data) if path.endswith("new-session") else _delete_session(data)
            return _reply(start_response, status, payload)
        if method == "POST" and path == "/__page/upload":
            # An image type only: a page from another site can't send one without the server agreeing.
            ctype = environ.get("CONTENT_TYPE", "").split(";")[0].strip().lower()
            if ctype not in IMAGE_TYPES:
                return _reply(start_response, 415, {"error": "Pictures can be PNG, JPEG, GIF or WebP."})
            length = int(environ.get("CONTENT_LENGTH") or 0)
            if not 0 < length <= MAX_IMAGE:
                return _reply(start_response, 413, {"error": "That picture is too large (15 MB at most)."})
            query = parse_qs(environ.get("QUERY_STRING", ""))
            with LOCK:
                status, payload = _upload((query.get("src") or [""])[0], (query.get("name") or [""])[0],
                                          ctype, environ["wsgi.input"].read(length))
            return _reply(start_response, status, payload)
        if method == "POST" and path == "/__page/save":
            # JSON only: a page from another site can't send that without the server agreeing (it won't).
            if not environ.get("CONTENT_TYPE", "").startswith("application/json"):
                return _reply(start_response, 415, {"error": "Expected JSON."})
            length = int(environ.get("CONTENT_LENGTH") or 0)
            if length > MAX_TEXT * 2:
                return _reply(start_response, 413, {"error": "That page is too large to save here."})
            data = json.loads(environ["wsgi.input"].read(length) or b"{}")
            with LOCK:
                status, payload = _save(data)
            return _reply(start_response, status, payload)
        return _reply(start_response, 404, {"error": "not found"})
    except (ValueError, OSError) as err:
        return _reply(start_response, 500, {"error": f"Couldn't save: {err}"})


# ---------------------------------------------------------------- New session / live session

def _sessions():
    sys.path.insert(0, str(ROOT[0]))
    from codex import sessions as codex_sessions
    return codex_sessions


def _focus_place() -> str:
    """The town the party is in (campaign.yml focus:), by its name in data/locations/."""
    try:
        settings = yaml.safe_load((ROOT[0] / "campaign.yml").read_text(encoding="utf-8")) or {}
        focus = str(settings.get("focus") or "")
        loc = ROOT[0] / "data" / "locations" / f"{focus}.yml"
        city = (yaml.safe_load(loc.read_text(encoding="utf-8")) or {}) if loc.is_file() else {}
        return str(city.get("name") or focus.replace("-", " ").title())
    except (OSError, yaml.YAMLError):
        return ""


def _new_session_info() -> dict:
    found = _sessions().sessions(DOCS[0])
    last = max((int(o) for o, _, _ in found if o >= 0), default=0)
    return {"number": last + 1, "place": _focus_place()}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "session"


def _new_session(data: dict):
    title = " ".join(str(data.get("title") or "").split())
    place = " ".join(str(data.get("place") or "").split())
    if not title or not place:
        return 400, {"error": "Give the session a name and a place."}
    if any(c in title + place for c in "\n#[]{}<>"):
        return 400, {"error": "Leave out # [ ] { } < > in the name and place."}
    number = _new_session_info()["number"]
    folder = DOCS[0] / "sessions"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_slug(place)}-{number}.md"
    if path.exists():
        return 409, {"error": f"docs/sessions/{path.name} already exists."}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    keep = _carried_over()
    sections = "".join(f"## {name}\n\n{keep.get(name) or start}\n\n" for name, start in SECTIONS)
    path.write_text(
        f"---\norder: {number}\ndate: {now}\n---\n\n"
        f"# {place} — Session {number}: {title}\n\n"
        f'!!! read-aloud "Previously…"\n    A short recap to read at the start of next session.\n\n'
        f"## Table notes\n\n- \n\n"
        f'??? dm "Private theories"\n    - \n\n'
        f"{sections}".rstrip("\n") + "\n",
        encoding="utf-8", newline="\n")
    return 200, {"src": f"sessions/{path.name}", "url": f"sessions/{path.stem}.html"}


# A new session page: Table notes and Private theories first, then (below a line) these sections -
# what the old Next Session page held - each with how it starts.
SECTIONS = (("Where we left off", "- "), ("Open questions", "- "), ("Things to ask or do", "- "),
            ("My character's goals", "- "))
CARRY = ("Open questions", "Things to ask or do", "My character's goals")   # ongoing: copied from last time


def _carried_over() -> dict:
    """The ongoing sections of the latest session page, as written there."""
    found = _sessions().sessions(DOCS[0])
    if not found:
        return {}
    text = (DOCS[0] / found[0][1]).read_text(encoding="utf-8").replace("\r\n", "\n")
    out = {}
    for name in CARRY:
        m = re.search(rf"^##\s+{re.escape(name)}\s*\n(.*?)(?=^##\s|^!!!|^\?\?\?|^<!--|\Z)", text, re.M | re.S)
        body = m.group(1).strip() if m else ""
        if body and body not in ("-", "*"):
            out[name] = body
    return out


def _upload(src: str, name: str, ctype: str, data: bytes):
    """A picture for the page being edited: saved as docs/uploads/<name>-<time>.<ext>; returns the
    link to it from that page."""
    if not _page_file(src):
        return 404, {"error": "This page has no file of its own to add pictures to."}
    ext, starts = IMAGE_TYPES[ctype]
    if not data.startswith(starts) or (ctype == "image/webp" and data[8:12] != b"WEBP"):
        return 400, {"error": "That file isn't the picture it says it is."}
    stem = posixpath.splitext(posixpath.basename(name.replace("\\", "/")))[0]
    alt = " ".join(re.sub(r"[-_]+", " ", stem).split())[:60] or "picture"
    folder = DOCS[0] / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    base = _slug(stem)[:40] if re.search(r"[A-Za-z0-9]", stem) else "picture"
    stamp, n = f"{datetime.now():%Y%m%d-%H%M%S}", 1
    file = folder / f"{base}-{stamp}{ext}"
    while file.exists():
        n += 1
        file = folder / f"{base}-{stamp}-{n}{ext}"
    file.write_bytes(data)
    url = posixpath.relpath(f"uploads/{file.name}", posixpath.dirname(src) or ".")
    return 200, {"url": url, "alt": alt}


def _serve_upload(path: str, start_response):
    folder = (DOCS[0] / "uploads").resolve()
    file = (DOCS[0] / path.lstrip("/")).resolve()
    types = {ext: ctype for ctype, (ext, _) in IMAGE_TYPES.items()}
    if folder not in file.parents or not file.is_file() or file.suffix.lower() not in types:
        return None
    body = file.read_bytes()
    start_response("200 OK", [("Content-Type", types[file.suffix.lower()]), ("Content-Length", str(len(body))),
                              ("Cache-Control", "no-store")])
    return [body]


def _delete_session(data: dict):
    """Delete session: the page moves to sources/backups/deleted/ (not erased), off the site."""
    src = str(data.get("src") or "")
    file = _page_file(src)
    if not file or not src.startswith("sessions/") or src.count("/") != 1:
        return 404, {"error": "Only session pages can be deleted here."}
    bin_ = ROOT[0] / "sources" / "backups" / "deleted"
    bin_.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    file.replace(bin_ / f"{file.stem}-{stamp}.md")
    return 200, {"deleted": src}


def _save(data: dict):
    src = str(data.get("src") or "")
    text = data.get("text")
    file = _page_file(src)
    if not file:
        return 404, {"error": "This page has no file of its own to edit."}
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        return 400, {"error": "Nothing to save."}
    current = file.read_text(encoding="utf-8")
    if data.get("hash") and data["hash"] != _hash(current):
        return 409, {"error": "This page was changed somewhere else since you opened it. "
                              "Copy your text, reload the page, and edit again."}
    backups = ROOT[0] / "sources" / "backups" / "pages"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (backups / f"{src[:-3].replace('/', '--')}-{stamp}.md").write_text(current, encoding="utf-8")
    text = text.replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    file.write_text(text, encoding="utf-8", newline="\n")
    return 200, {"saved": f"docs/{src}", "hash": _hash(text)}
