"""NPC cards: the NPC Index as cards, like the Party page's character cards. Campaign-owned (not an
engine file - `codex update` leaves it alone), listed in the hooks: of mkdocs.yml and
mkdocs-players.yml, before hooks/entities.py so the [[mentions]] it writes become links.

    {{ npc-cards }}     every NPC as a card, grouped by region (on the players' site: the engine's
                        {{ npc-index }} instead, so notes and secrets never reach it)
    {{ npc-cards greywater }}  only the NPCs of one town: region: Greywater, or a location: in
                        data/locations/greywater.yml (players' site: {{ npc-list greywater }})

Each card shows the NPC's portrait (portrait: in data/npcs/, a path under docs/), who they are,
the hook or description, appearance, personality, notes, and private theories (secret:).

While the site is served (CampaignCodex5e), javascripts/npc-cards.js puts Edit on each card and
Add NPC above them, and saves through this hook's own endpoint on the site's server:
    GET  /__npc/get?id=...   the NPC's entry as written, plus the known locations
    POST /__npc/save         saves an entry (and an uploaded portrait) to data/npcs/
Every save keeps a copy of the file it changed in sources/backups/npcs/ first.
Changes to this file need CampaignCodex5e restarted.
"""
import base64
import hashlib
import html
import json
import posixpath
import re
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

import yaml

MARKER = re.compile(r"^([ \t]*)\{\{\s*npc-cards\s*([a-z0-9_-]*)\s*\}\}[ \t]*$", re.MULTILINE)
ROOT = [None]          # the campaign folder
DOCS = [None]          # docs/
PLAYERS = [False]
LOCK = threading.Lock()

PORTRAITS = "npc-portraits"      # under docs/
STATUSES = ["alive", "dead", "missing", "captive", "unknown"]
# The fields the card editor changes; anything else in an entry (aliases, faction, statblock,
# player_hook...) is kept as written.
TEXT_FIELDS = ["name", "race", "role", "region", "group", "location", "status",
               "hook", "description", "appearance", "personality", "notes", "secret"]
REQUIRED = ["name", "region", "role", "hook"]
ORDER = ["id", "name", "region", "group", "race", "role", "location", "faction", "portrait", "status",
         "hook", "description", "appearance", "personality", "notes", "secret"]
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
MAX_IMAGE = 10 * 1024 * 1024


# ---------------------------------------------------------------- data

def slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", str(text).lower().replace("’", "").replace("'", ""))
    return re.sub(r"[\s_]+", "-", s).strip("-")


def _load(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def _npc_files():
    return sorted((ROOT[0] / "data" / "npcs").glob("*.yml"))


def _all_npcs():
    """[(path, entry)] in data-file order, each entry with its id filled in."""
    out = []
    for path in _npc_files():
        for n in _load(path) or []:
            if isinstance(n, dict):
                n.setdefault("id", slug(n.get("name", "")))
                out.append((path, n))
    return out


def _locations():
    """{id: name} of every location in data/locations/."""
    out = {}
    for path in sorted((ROOT[0] / "data" / "locations").glob("*.yml")):
        city = _load(path) or {}
        for district in city.get("districts") or []:
            for loc in district.get("locations") or []:
                if isinstance(loc, dict) and loc.get("name"):
                    out[loc.get("id") or slug(loc["name"])] = loc["name"]
    return out


def _factions():
    path = ROOT[0] / "data" / "factions.yml"
    data = _load(path) if path.is_file() else None
    return {(f.get("id") or slug(f.get("name", ""))): f.get("name")
            for f in data or [] if isinstance(f, dict) and f.get("name")}


# ---------------------------------------------------------------- rendering

def _flat(text) -> str:
    return " ".join(str(text).split())


def _empty(text: str) -> str:
    return f'<span class="npc-empty">{text}</span>'


def _card(n: dict, page_src: str, locations: dict, factions: dict) -> str:
    nid = n["id"]
    lines = [f'<div class="statblock pc-card npc-card" data-npc="{html.escape(nid)}" markdown>', ""]
    portrait = n.get("portrait")
    if portrait and (DOCS[0] / str(portrait)).is_file():
        src = posixpath.relpath(str(portrait), posixpath.dirname(page_src) or ".")
        lines += [f'![{_flat(n.get("name", ""))}]({src}){{ .npc-portrait }}', ""]
    else:   # no portrait yet: the name's first letter in the same frame, so every card lines up
        initial = next((c for c in str(n.get("name", "")).removeprefix("The ") if c.isalnum()), "?")
        lines += [f'<div class="npc-portrait npc-portrait--empty" aria-hidden="true">{html.escape(initial.upper())}</div>', ""]
    lines += [f"### {n.get('name', nid)} {{ #npc-{nid} }}", ""]
    meta = [n.get("race"), n.get("role")]
    if n.get("location") in locations:
        meta.append(f"[[{locations[n['location']]}]]")
    for fid in n.get("faction") if isinstance(n.get("faction"), list) else [n.get("faction")]:
        if fid in factions:
            meta.append(f"[[{factions[fid]}]]")
    if n.get("group"):
        meta.append(n["group"])
    sub = "*" + " · ".join(_flat(x) for x in meta if x) + "*" if any(meta) else ""
    lines += [sub or "&nbsp;", ""]
    # The status line is always there (empty for the living), so dividers line up across a row.
    status = str(n.get("status") or "alive")
    pill = f'<span class="npc-status">{html.escape(status.capitalize())}</span>' if status != "alive" else ""
    lines += [f'<p class="npc-status-row">{pill}</p>', "", "---", ""]
    # Every card shows every section in the same order; empty ones say so, quietly.
    about = n.get("description") or n.get("hook")
    lines += [str(about).strip() if about else _empty("No description yet"), ""]
    lines += ["<br>\n".join(f'<span class="npc-label">{label}</span> {_flat(n[f]) if n.get(f) else _empty("Not yet known")}'
                            for label, f in (("Appearance", "appearance"), ("Personality", "personality"))), ""]
    lines += ['<p class="sb-section">Notes</p>', "",
              str(n["notes"]).strip() if n.get("notes") else _empty("Nothing yet"), ""]
    lines += ['<div class="npc-private" markdown>', "", '<p class="sb-section">Private theories</p>', "",
              str(n["secret"]).strip() if n.get("secret") else _empty("No theories yet"), "", "</div>", ""]
    lines += ["</div>", ""]
    return "\n".join(lines)


def _city_locations(place: str) -> set:
    """The location ids in data/locations/<place>.yml."""
    path = ROOT[0] / "data" / "locations" / f"{place}.yml"
    city = (_load(path) or {}) if path.is_file() else {}
    return {loc.get("id") or slug(loc.get("name", "")) for d in city.get("districts") or []
            for loc in d.get("locations") or [] if isinstance(loc, dict)}


def _in_place(n: dict, place: str, places: set) -> bool:
    """An NPC belongs to a town if their region is that town, or they're at one of its locations."""
    return slug(n.get("region", "")) == place or n.get("location") in places


def render_cards(page_src: str, place: str = "") -> str:
    npcs = [n for _, n in _all_npcs()]
    if place:
        places = _city_locations(place)
        npcs = [n for n in npcs if _in_place(n, place, places)]
    locations, factions = _locations(), _factions()
    out = ['<div class="npc-bar"></div>', "", '<div class="npc-form" style="display:none"></div>', "",
           '<div class="npc-page" markdown>', ""]
    if not npcs:
        out += ["*Nobody here yet - use Add NPC.*", ""]
    regions = {}
    for n in npcs:
        regions.setdefault(str(n.get("region") or "Other"), []).append(n)
    for region, people in regions.items():
        out += [f"## {region}", "", '<div class="npc-cards" markdown>', ""]
        out += [_card(n, page_src, locations, factions) for n in people]
        out += ["</div>", ""]
    out += ["</div>", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- MkDocs events

def on_config(config, **kwargs):
    ROOT[0] = Path(config.config_file_path).parent
    DOCS[0] = Path(config["docs_dir"])
    PLAYERS[0] = (config.get("extra") or {}).get("audience") == "players"


def on_page_markdown(markdown, page, config, files, **kwargs):
    if PLAYERS[0]:   # the players' site gets the engine's own list: no notes, no secrets
        return MARKER.sub(lambda m: m.group(1) + ("{{ npc-list " + m.group(2) + " }}" if m.group(2)
                                                   else "{{ npc-index }}"), markdown)
    return MARKER.sub(lambda m: "\n".join(m.group(1) + l if l else l
                                          for l in render_cards(page.file.src_uri, m.group(2)).split("\n")), markdown)


def _stamp(rel_path: str) -> str:
    f = DOCS[0] / rel_path
    return hashlib.md5(f.read_bytes()).hexdigest()[:8] if f.is_file() else "0"


ACTIVE_LINK = re.compile(r'(<a href="[^"]*" class="md-nav__link md-nav__link--active">.*?</a>)', re.S)


def _side_list(output: str) -> str:
    """The names of the NPCs whose cards are on this page, by region, under the page's entry in the
    side menu (links to the cards)."""
    shown = set(re.findall(r'data-npc="([^"]+)"', output))
    regions = {}
    for _, n in _all_npcs():
        if html.escape(n["id"]) not in shown:
            continue
        regions.setdefault(str(n.get("region") or "Other"), []).append(n)
    items = []
    for region, people in regions.items():
        items.append(f'<li class="md-nav__item npc-side__region">{html.escape(region)}</li>')
        items += [f'<li class="md-nav__item"><a href="#npc-{html.escape(n["id"])}" class="md-nav__link">'
                  f'<span class="md-ellipsis">{html.escape(_flat(n.get("name", n["id"])))}</span></a></li>'
                  for n in people]
    if not items:
        return output
    side = '<ul class="md-nav__list npc-side">' + "".join(items) + "</ul>"
    return ACTIVE_LINK.sub(lambda m: m.group(1) + side, output, count=1)


def on_post_page(output, page, config, **kwargs):
    # Fetch campaign.css afresh whenever it changes, instead of a cached copy.
    output = re.sub(r'(stylesheets/campaign\.css)(["\'])', rf"\1?v={_stamp('stylesheets/campaign.css')}\2", output)
    if not PLAYERS[0] and 'class="npc-bar"' in output:
        output = _side_list(output)
        js = posixpath.relpath("javascripts/npc-cards.js", posixpath.dirname(page.file.dest_uri) or ".")
        output = output.replace("</body>", f'<script src="{js}?v={_stamp("javascripts/npc-cards.js")}"></script>\n</body>', 1)
    return output


def on_serve(server, config, builder, **kwargs):
    if getattr(server, "_npc_cards", False):
        return server
    app = server.get_app()

    def wrapped(environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path.startswith("/__npc/"):
            return _api(environ, start_response, path)
        return app(environ, start_response)

    server.set_app(wrapped)
    server._npc_cards = True
    return server


# ---------------------------------------------------------------- saving

def _reply(start_response, status: int, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    start_response(f"{status} {'OK' if status == 200 else 'Error'}",
                   [("Content-Type", "application/json"), ("Content-Length", str(len(body))),
                    ("Cache-Control", "no-store")])
    return [body]


def _api(environ, start_response, path):
    method = environ.get("REQUEST_METHOD", "GET")
    try:
        if method == "GET" and path == "/__npc/get":
            nid = (parse_qs(environ.get("QUERY_STRING", "")).get("id") or [""])[0]
            entry = next((n for _, n in _all_npcs() if n["id"] == nid), None) if nid else None
            if nid and not entry:
                return _reply(start_response, 404, {"error": f"No NPC with the id {nid} - reload the page."})
            return _reply(start_response, 200, {"npc": entry or {}, "statuses": STATUSES,
                                                "locations": [{"id": k, "name": v} for k, v in _locations().items()]})
        if method == "POST" and path == "/__npc/save":
            # JSON only: a page from another site can't send that without the server agreeing (it won't).
            if not environ.get("CONTENT_TYPE", "").startswith("application/json"):
                return _reply(start_response, 415, {"error": "Expected JSON."})
            length = int(environ.get("CONTENT_LENGTH") or 0)
            data = json.loads(environ["wsgi.input"].read(length) or b"{}")
            with LOCK:
                status, payload = _save(data)
            return _reply(start_response, status, payload)
        return _reply(start_response, 404, {"error": "not found"})
    except (ValueError, OSError, yaml.YAMLError) as err:
        return _reply(start_response, 500, {"error": f"Couldn't save: {err}"})


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper, value):
    style = "|" if "\n" in value.strip() else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value.strip() + ("\n" if style else ""), style=style)


_Dumper.add_representer(str, _str)


def _header(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or (lines and not line.strip()):
            lines.append(line)
        else:
            break
    return "\n".join(lines).rstrip() + "\n\n" if lines else ""


def _write(path: Path, entries: list, header: str):
    if path.is_file():
        backups = ROOT[0] / "sources" / "backups" / "npcs"
        backups.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (backups / f"{path.stem}-{stamp}.yml").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    body = "\n".join(yaml.dump([e], Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100,
                               default_flow_style=False) for e in entries)
    path.write_text(header + (body if entries else "[]\n"), encoding="utf-8", newline="\n")


def _save(data: dict):
    raw = data.get("npc") or {}
    fields = {f: str(raw.get(f) or "").strip() for f in TEXT_FIELDS}
    for f in ("name", "race", "role", "region", "group", "location", "status"):
        fields[f] = _flat(fields[f])
    missing = [f for f in REQUIRED if not fields[f]]
    if missing:
        return 400, {"error": "Fill in: " + ", ".join(missing) + "."}
    if fields["status"] and fields["status"] not in STATUSES:
        return 400, {"error": "Unknown status."}
    if fields["status"] == "alive":
        fields["status"] = ""
    if fields["location"] and fields["location"] not in _locations():
        return 400, {"error": f"No location with the id {fields['location']}."}

    everyone = _all_npcs()
    nid = str(data.get("id") or "")
    if nid:
        path = next((p for p, n in everyone if n["id"] == nid), None)
        if not path:
            return 404, {"error": f"No NPC with the id {nid} - reload the page."}
    else:
        nid = slug(fields["name"])
        if not nid:
            return 400, {"error": "The name needs at least one letter or number."}
        path = None
    if not path and any(n["id"] == nid for _, n in everyone):
        return 409, {"error": f"There's already an NPC with the id {nid}."}
    names = {_flat(n.get("name", "")).lower() for _, n in everyone if n["id"] != nid}
    if fields["name"].lower() in names:
        return 409, {"error": f"There's already an NPC called {fields['name']}."}

    portrait = None
    upload = data.get("portrait")
    if upload:
        m = re.match(r"^data:([\w/+.-]+);base64,(.*)$", str(upload), re.S)
        if not m or m.group(1) not in IMAGE_TYPES:
            return 400, {"error": "The portrait must be a PNG, JPEG, WebP or GIF image."}
        blob = base64.b64decode(m.group(2))
        if len(blob) > MAX_IMAGE:
            return 400, {"error": "The portrait is over 10 MB - use a smaller image."}
        folder = DOCS[0] / PORTRAITS
        folder.mkdir(parents=True, exist_ok=True)
        portrait = f"{PORTRAITS}/{nid}.{IMAGE_TYPES[m.group(1)]}"
        (DOCS[0] / portrait).write_bytes(blob)

    if path:   # an existing NPC: change only the editor's fields, in place
        entries = _load(path) or []
        entry = next(e for e in entries if isinstance(e, dict) and (e.get("id") or slug(e.get("name", ""))) == nid)
        if "id" not in entry and slug(fields["name"]) != nid:
            entry["id"] = nid   # renamed: keep the old id, so links to it keep working
        for f, v in fields.items():
            if v:
                entry[f] = v
            else:
                entry.pop(f, None)
        if portrait:
            entry["portrait"] = portrait
        elif data.get("remove_portrait"):
            entry.pop("portrait", None)
        _write(path, entries, _header(path))
        return 200, {"saved": f"data/npcs/{path.name}", "id": nid, "updated": True}

    entry = {"id": nid}
    entry.update({f: v for f, v in fields.items() if v})
    if portrait:
        entry["portrait"] = portrait
    entry = {k: entry[k] for k in sorted(entry, key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER))}
    path = ROOT[0] / "data" / "npcs" / f"{slug(fields['region']) or 'others'}.yml"
    entries = (_load(path) or []) if path.is_file() else []
    header = _header(path) if path.is_file() else f"# {fields['region']}'s people. Fields: see templates/npc.yml.\n\n"
    entries.append(entry)
    _write(path, entries, header)
    return 200, {"saved": f"data/npcs/{path.name}", "id": nid, "updated": False}
