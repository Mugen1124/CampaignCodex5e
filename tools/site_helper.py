r"""
Local save helper for the site's tools (the encounter builder, custom creatures, the Party
page, and session recording).

A web page can't write files by itself. This tiny server runs on your own machine
alongside CampaignCodex5e and does the writing for it. It only listens on 127.0.0.1 (never
the network), and only writes into data\encounters\, data\monsters\custom.yml, data\party.yml,
and data\families.yml (plus backups in sources\backups\encounters\, creatures\, party\, families\) -
and new session recordings, in the folder chosen on the Record & Transcribe page
(..\recordings\ unless changed). A recording is only ever a new file it named itself.

    GET  /ping               -> {"ok": true}
    POST /encounter          -> save {"encounter": {...}, "overwrite": bool}
    POST /encounter/archive  -> {"id": ..., "archived": true|false}
    POST /encounter/delete   -> {"id": ...}  (archived encounters only; refused if a page shows it)
    GET  /creature?id=...    -> {"creature": {...}, "custom": bool}  (any creature, as written in its file)
    POST /creature           -> save {"creature": {...}, "editing": bool} into custom.yml
    POST /creature/delete    -> {"id": ...}  (custom creatures only; refused while anything uses it)
    GET  /party              -> {"level", "size", "members": [...]}  (data\party.yml as written)
    POST /party/member       -> {"index": n or null (add), "expect": name at n, "member": {...}}
    POST /party/member/delete -> {"index": n, "expect": name at n}
    GET  /recordings?folder= -> {"folder", "default", "files": [...], "job": {...}}  (audio files there)
    POST /folder/browse      -> {"start": folder} -> {"folder": chosen or null}  (a folder picker on this computer)
    POST /recording/start    -> {"folder": ...} -> {"id", "file"}  (creates "Session <date> <time>.webm")
    POST /recording/chunk?id=...  (raw audio bytes, appended in order) -> {"bytes": total so far}
    POST /recording/stop     -> {"id": ...} -> {"file", "bytes"}
    POST /transcribe         -> {"file": path} -> starts tools\transcribe.py in the background
    POST /turnlog            -> {"file": recording, "rec": "hh:mm:ss", "text"} -> a line in <recording>.turns.txt
    POST /family             -> {"family", "creature", "role": "members"|"leaders", "action": "add"|"remove", "new": bool}
                                (data\families.yml: only that family's one line changes; new families go at the end)
    GET  /transcribe         -> {"job": {"file", "running", "progress", "done", "error"}}
    GET  /items              -> {"items": [{"id", "name", "holder"}], "party": [character names]}
    POST /item/holder        -> {"id": item, "holder": character name, "Party", or "" (nobody)}
    POST /item/reveal        -> {"id": item, "reveal": "auto"|"show"|"hide"} (its revealed: line - the players' site)
                                (only that item's holder: line changes; a copy goes to sources\backups\items\ first)
    GET  /item/suggestions?folder= -> pickups tools\transcribe.py found in that folder's transcripts
    POST /item/suggestion    -> {"file": <recording>.items.json, "n": entry, "action": "assign"|"dismiss", "holder"}
    GET  /item/claims        -> items players claimed on the players' site (up-for-grabs items), waiting for you
    POST /item/claim         -> {"id", "action": "approve"|"reject"} (approve gives them the item; other claims on it are declined)
    GET  /party/suggestions  -> changes players suggested for their cards on the players' site, waiting for you
    POST /party/suggestion   -> {"id", "action": "approve"|"reject"} (approve writes it into data\party.yml)
    GET  /tracker/share      -> {"last": how the last send went, "token": bool}
    POST /tracker/share      -> {"view": {...}} -> sends the fight, as the players may see it, to the players'
                                site's live tracker (in the background; the reply says how the last send went).
                                Needs tools\tracker-token.txt (the Cloudflare service token); writes no files.

CampaignCodex5e starts it automatically; closing the CampaignCodex5e window stops it.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codex import settings as codex_settings  # noqa: E402

CAMPAIGN = codex_settings.load(ROOT)
ENCOUNTERS = ROOT / "data" / "encounters"
MONSTERS = ROOT / "data" / "monsters"
CUSTOM = MONSTERS / "custom.yml"
NPCS = ROOT / "data" / "npcs"
DOCS = ROOT / "docs"
BACKUPS = ROOT / "sources" / "backups" / "encounters"
CREATURE_BACKUPS = ROOT / "sources" / "backups" / "creatures"
PORT = 8765
ID_OK = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
FIELD_ORDER = ("id", "name", "location", "page", "party_level", "party_size", "archived", "notes")
WRITE_LOCK = threading.Lock()

# Creature fields in the order templates\monster.yml uses.
CREATURE_ORDER = ("id", "name", "group", "type", "size", "creature_type", "environments", "cr", "ac",
                  "ac_note", "hp", "hp_formula", "speed", "abilities", "initiative", "saves", "skills",
                  "vulnerabilities", "resistances", "immunities", "condition_immunities", "senses",
                  "languages", "traits", "actions", "bonus_actions", "reactions", "legendary_actions", "note")
CREATURE_LISTS = ("traits", "actions", "bonus_actions", "reactions", "legendary_actions")
CREATURE_NUMBERS = ("ac", "hp", "initiative")
ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
CRS = {"0", "1/8", "1/4", "1/2"} | {str(n) for n in range(1, 31)}
RECORDINGS = CAMPAIGN["recordings_dir"]   # the default (campaign.yml); the Record page can choose another folder
AUDIO = (".webm", ".m4a", ".mp3", ".wav", ".flac", ".ogg", ".aac", ".wma")
TRANSCRIBE = ROOT / "tools" / "transcribe.py"
FAMILIES = ROOT / "data" / "families.yml"
ITEMS_DIR = ROOT / "data" / "items"
ITEM_BACKUPS = ROOT / "sources" / "backups" / "items"
ITEM_BACKUPS_KEPT = 30
FAMILY_BACKUPS = ROOT / "sources" / "backups" / "families"
BUILDER_SECTION = "# ---------------------------------------------------------------- made in the encounter builder"
PARTY = ROOT / "data" / "party.yml"
PARTY_BACKUPS = ROOT / "sources" / "backups" / "party"
PARTY_BACKUPS_KEPT = 30
# Character fields in the order templates\character.yml uses.
CHARACTER_ORDER = ("player", "email", "character", "race", "class", "background", "level", "ac", "ac_note", "hp",
                   "hp_formula", "speed", "initiative", "passive_perception", "abilities", "saves", "skills",
                   "resistances", "immunities", "condition_immunities", "senses", "languages", "proficiencies",
                   "features", "actions", "bonus_actions", "reactions", "spellcasting", "inventory", "currency",
                   "persona", "portrait", "private", "source", "note")
# Kept as given (lists and maps the Party page's importer writes; see templates\character.yml).
CHARACTER_STRUCTURED = {"proficiencies": dict, "spellcasting": list, "inventory": list, "currency": dict,
                        "persona": dict, "private": list, "source": dict}
CHARACTER_LISTS = ("features", "actions", "bonus_actions", "reactions")
CHARACTER_NUMBERS = ("level", "ac", "hp", "initiative", "passive_perception")
IDENTITY = ("player", "email", "character", "race", "class", "level")   # members with only these stay on one line
CUSTOM_HEADER = ("# Custom creatures, made with the encounter builder's New creature form (Encounters -> Builder).\n"
                 "# The save helper rewrites this file when you save or delete one there; this header is kept,\n"
                 "# but comments inside entries are not. Same format as templates\\monster.yml.")


# ---------------------------------------------------------------- encounter files

def find_encounter(eid: str):
    """(path, data) of the file holding encounter `eid`, or (None, None)."""
    for path in sorted(ENCOUNTERS.glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and data.get("id") == eid:
            return path, data
    return None, None


def write_encounter(path: Path, enc: dict, header: str = "") -> None:
    """Write one encounter in the site's usual layout, keeping any comment header."""
    lines = [header.rstrip("\n")] if header.strip() else []
    for key in FIELD_ORDER:
        if key in enc and enc[key] not in (None, "", False):
            lines.append(yaml.safe_dump({key: enc[key]}, allow_unicode=True, width=1000).strip())
    lines.append("creatures:")
    for c in enc.get("creatures", []):
        lines.append(f"  - {{id: {c['id']}, count: {int(c.get('count', 1))}}}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def comment_header(path: Path) -> str:
    """The comment lines at the top of a file, so rewriting it doesn't lose them."""
    head = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            head.append(line)
        else:
            break
    return "\n".join(head)


def pages_using(eid: str) -> list:
    """Story pages that show this encounter with {{ encounter id }}."""
    pattern = re.compile(r"\{\{\s*encounter\s+" + re.escape(eid) + r"\s*\}\}")
    return sorted(str(p.relative_to(DOCS)).replace("\\", "/") for p in DOCS.rglob("*.md")
                  if pattern.search(p.read_text(encoding="utf-8", errors="ignore")))


# ---------------------------------------------------------------- creature files

def all_creatures() -> dict:
    """{id: (file name, entry)} for every creature in data\\monsters\\, the way the site loads them."""
    found = {}
    for path in sorted(list(MONSTERS.glob("*.yml")) + list(MONSTERS.glob("*.json"))):
        try:
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, ValueError):
            continue
        if isinstance(data, dict) and "creatures" in data and "id" not in data:
            data = data["creatures"]
        for entry in data if isinstance(data, list) else [data]:
            if isinstance(entry, dict):
                found.setdefault(str(entry.get("id") or path.stem), (path.name, entry))
    return found


def read_custom() -> list:
    if not CUSTOM.is_file():
        return []
    data = yaml.safe_load(CUSTOM.read_text(encoding="utf-8")) or []
    return [e for e in (data if isinstance(data, list) else [data]) if isinstance(e, dict)]


def _scalar(key, value) -> str:
    return yaml.safe_dump({key: value}, allow_unicode=True, width=1000, sort_keys=False).strip()


def dump_creature(c: dict, order=CREATURE_ORDER, lists=CREATURE_LISTS) -> str:
    """One creature (or character) as a list entry, laid out like templates\\monster.yml."""
    keys = [k for k in order if k in c] + [k for k in c if k not in order]
    lines = []
    for key in keys:
        value = c[key]
        if key == "abilities" and isinstance(value, dict):
            line = "abilities: {" + ", ".join(f"{a}: {value[a]}" for a in ABILITIES if a in value) + "}"
        elif key == "environments" and isinstance(value, list):
            line = "environments: " + yaml.safe_dump(value, default_flow_style=True, allow_unicode=True,
                                                     width=1000).strip()
        elif key in lists and isinstance(value, list):
            body = yaml.safe_dump(value, allow_unicode=True, width=1000, sort_keys=False).rstrip("\n")
            line = f"{key}:\n" + "\n".join("  " + ln for ln in body.split("\n"))
        else:
            line = _scalar(key, value)
        lines.append(line)
    text = "\n".join(lines)
    return "- " + text.replace("\n", "\n  ")


def write_custom(creatures: list) -> None:
    header = comment_header(CUSTOM) if CUSTOM.is_file() else ""
    parts = [header or CUSTOM_HEADER, ""]
    parts += [dump_creature(c) + "\n" for c in creatures]
    MONSTERS.mkdir(parents=True, exist_ok=True)
    CUSTOM.write_text("\n".join(parts).rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def clean_creature(raw: dict, keep: dict = None):
    """(creature, error) - the form's data tidied into the file format. Fields the form doesn't
    know about are kept from `keep` (the entry being edited), so hand-added extras survive."""
    c = {k: v for k, v in (keep or {}).items() if k not in CREATURE_ORDER}
    for key in CREATURE_ORDER:
        value = raw.get(key)
        if key in CREATURE_LISTS:
            entries = [{"name": str(e.get("name", "")).strip(), "text": str(e.get("text", "")).strip()}
                       for e in value or [] if isinstance(e, dict)]
            value = [e for e in entries if e["name"] or e["text"]]
            if any(not e["name"] for e in value):
                return None, f"Every entry under {key.replace('_', ' ')} needs a name."
        elif key == "abilities":
            if isinstance(value, dict) and value:
                try:
                    value = {a: int(value.get(a, 10)) for a in ABILITIES}
                except (TypeError, ValueError):
                    return None, "Ability scores must be numbers."
            else:
                value = None
        elif key == "environments":
            value = [str(e).strip() for e in value or [] if str(e).strip()]
        elif key in CREATURE_NUMBERS:
            if value in (None, ""):
                value = None
            else:
                try:
                    value = int(str(value).strip().replace("+", ""))
                except ValueError:
                    return None, f"{key.upper() if key != 'initiative' else 'Initiative'} must be a whole number."
        elif value is not None:
            value = " ".join(str(value).split()) if key != "note" else str(value).strip()
        if value in (None, "", []):
            c.pop(key, None)
        else:
            c[key] = value
    c.pop("source", None)   # a source marks imported creatures; custom ones belong on the Bestiary
    if not ID_OK.match(str(c.get("id", ""))):
        return None, "The id must be lowercase letters, numbers, and dashes."
    if not c.get("name"):
        return None, "Give the creature a name."
    if str(c.get("cr", "")) not in CRS:
        return None, "Pick a CR."
    if str(c["cr"]).isdigit():
        c["cr"] = int(c["cr"])
    return c, None   # dump_creature puts the fields in template order


def creature_users(cid: str) -> list:
    """Everything that would break if creature `cid` went away, as readable strings."""
    users = []
    for path in sorted(ENCOUNTERS.glob("*.yml")):
        try:
            enc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(enc, dict) and any(str(c.get("id")) == cid for c in enc.get("creatures") or []
                                         if isinstance(c, dict)):
            users.append(f"the encounter “{enc.get('name', enc.get('id', path.stem))}”"
                         + (" (archived)" if enc.get("archived") else ""))
    marker = re.compile(r"\{\{\s*statblock\s+" + re.escape(cid) + r"\s*\}\}")
    for p in sorted(DOCS.rglob("*.md")):
        if marker.search(p.read_text(encoding="utf-8", errors="ignore")):
            users.append("the page " + str(p.relative_to(DOCS)).replace("\\", "/"))
    npc_ref = re.compile(r"^\s*statblock:\s*['\"]?" + re.escape(cid) + r"['\"]?\s*$", re.MULTILINE)
    for p in sorted(NPCS.glob("*.yml")):
        if npc_ref.search(p.read_text(encoding="utf-8", errors="ignore")):
            users.append(f"an NPC in data/npcs/{p.name}")
    return users


# ---------------------------------------------------------------- party file

def split_members(text: str):
    """(lines before the members, [each member's lines], lines after) of party.yml, so a rewrite
    can keep every member it didn't change exactly as written - spacing, quotes, comments."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if re.match(r"^members:\s*(#.*)?$", ln)), None)
    if start is None:
        return lines, [], []
    chunks, i = [], start + 1
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^\s+-\s", ln):
            chunks.append([ln])
        elif ln.strip() and not ln[:1].isspace():
            break                                   # a top-level line: the members list is over
        elif chunks:
            chunks[-1].append(ln)
        else:
            lines[start] += "\n" + ln                # blank/comment lines before the first member
        i += 1
    return lines[:start + 1], chunks, lines[i:]


def _chunk_member(chunk: list):
    try:
        data = yaml.safe_load("\n".join(chunk))
    except yaml.YAMLError:
        return None
    return data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else None


def dump_member(m: dict) -> str:
    """A member written fresh: one line if it's only name/player/race/class/level, else in full."""
    keys = [k for k in CHARACTER_ORDER if k in m] + [k for k in m if k not in CHARACTER_ORDER]
    if set(m) <= set(IDENTITY):
        parts = [yaml.safe_dump({k: m[k]}, default_flow_style=True, allow_unicode=True, width=1000).strip()[1:-1]
                 for k in keys]
        return "  - {" + ", ".join(parts) + "}"
    return "\n".join("  " + ln for ln in dump_creature(m, CHARACTER_ORDER, CHARACTER_LISTS).split("\n"))


def write_party(members: list, size=None) -> None:
    """Rewrite party.yml with these members, reusing the original lines of any member that
    didn't change. `size`, if given, replaces the size: line."""
    head, chunks, tail = split_members(PARTY.read_text(encoding="utf-8"))
    old = [(_chunk_member(c), c) for c in chunks]
    out = []
    for m in members:
        match = next((o for o in old if o[0] == m), None)
        if match:
            old.remove(match)
            out.append("\n".join(match[1]).rstrip("\n"))
        else:
            out.append(dump_member(m))
    head_text = "\n".join(head)
    if size is not None:
        head_text = re.sub(r"^size:.*$", f"size: {size}", head_text, count=1, flags=re.MULTILINE)
    text = head_text + "\n" + "\n".join(out) + "\n" + "\n".join(tail)
    PARTY.write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")   # site files use Unix line endings


def backup_party() -> None:
    """A copy of party.yml before each change; the newest PARTY_BACKUPS_KEPT are kept."""
    PARTY_BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    shutil.copy2(PARTY, PARTY_BACKUPS / f"party-{stamp}.yml")
    for old in sorted(PARTY_BACKUPS.glob("party-*.yml"))[:-PARTY_BACKUPS_KEPT]:
        old.unlink()


def clean_member(raw: dict, keep: dict = None):
    """(member, error) - the form's data tidied into party.yml's format. Fields the form doesn't
    know about are kept from `keep` (the member being edited)."""
    m = {k: v for k, v in (keep or {}).items() if k not in CHARACTER_ORDER}
    for key in CHARACTER_ORDER:
        # A field the form doesn't send at all (the imported inventory, persona, spellcasting... which it
        # doesn't show) keeps its value; one it sends empty is cleared.
        value = raw.get(key) if key in raw else (keep or {}).get(key)
        if key in CHARACTER_LISTS:
            entries = [{"name": str(e.get("name", "")).strip(), "text": str(e.get("text", "")).strip()}
                       for e in value or [] if isinstance(e, dict)]
            value = [e for e in entries if e["name"] or e["text"]]
            if any(not e["name"] for e in value):
                return None, f"Every entry under {key.replace('_', ' ')} needs a name."
        elif key in CHARACTER_STRUCTURED:
            value = value if isinstance(value, CHARACTER_STRUCTURED[key]) and value else None
        elif key == "abilities":
            scores = {}
            for a in ABILITIES:
                v = (value or {}).get(a) if isinstance(value, dict) else None
                if v not in (None, ""):
                    try:
                        scores[a] = int(v)
                    except (TypeError, ValueError):
                        return None, "Ability scores must be numbers."
            value = scores or None
        elif key in CHARACTER_NUMBERS:
            if value in (None, ""):
                value = None
            else:
                try:
                    value = int(str(value).strip().replace("+", ""))
                except ValueError:
                    label = {"ac": "AC", "hp": "HP"}.get(key, key.replace("_", " ").capitalize())
                    return None, f"{label} must be a whole number."
        elif value is not None:
            value = " ".join(str(value).split()) if key != "note" else str(value).strip()
        if value in (None, "", []):
            m.pop(key, None)
        else:
            m[key] = value
    if not m.get("character"):
        return None, "Give the character a name."
    if m.get("email"):
        m["email"] = m["email"].strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", m["email"]):
            return None, "That email doesn't look right."
    return m, None


# ---------------------------------------------------------------- encounter families

def _flow(items: list) -> str:
    return yaml.safe_dump(items, default_flow_style=True, allow_unicode=True, width=10000).strip()


def edit_family(text: str, family: str, creature: str, role: str, add: bool, new: bool):
    """(new text, error): families.yml with one creature added to or taken out of one family's
    members/leaders line. Every other line - comments, spacing, other families - stays as it is."""
    lines = text.split("\n")
    heads = [i for i, ln in enumerate(lines) if re.match(r"^- family:\s*", ln)]
    def name_at(i):
        value = yaml.safe_load(lines[i][2:]) or {}
        return str(value.get("family", "")).strip()
    found = next((i for i in heads if name_at(i).lower() == family.lower()), None)
    if new:
        if found is not None:
            return None, f"There's already a family called {name_at(found)}."
        block = [f"- family: {_flow([family])[1:-1]}", f"  {role}: {_flow([creature])}"]
        if BUILDER_SECTION not in text:
            block = [BUILDER_SECTION] + block
        body = text.rstrip("\n").split("\n")
        return "\n".join(body + [""] + block) + "\n", None
    if found is None:
        return None, f"No family called {family}."
    end = next((i for i in heads if i > found), len(lines))
    # the family's block ends before any trailing blank or comment lines
    while end - 1 > found and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    at = next((i for i in range(found + 1, end) if re.match(rf"^\s+{role}:\s*\[", lines[i])), None)
    if at is None:
        if not add:
            return None, f"{creature} isn't one of the {family} {role}."
        insert = found + 1
        if role == "leaders":   # after the members line, if there is one
            insert = next((i + 1 for i in range(found + 1, end) if re.match(r"^\s+members:", lines[i])), insert)
        lines.insert(insert, f"  {role}: {_flow([creature])}")
        return "\n".join(lines), None
    m = re.match(r"^(\s+" + role + r":\s*)(\[.*?\])(\s*#.*)?$", lines[at])
    if not m:
        return None, f"The {role} line of {family} is written in a way the builder can't edit - change it by hand."
    items = [str(x) for x in (yaml.safe_load(m.group(2)) or [])]
    present = [x for x in items if x.lower() == creature.lower()]
    if add and present:
        return None, f"{creature} is already one of the {family} {role}."
    if not add and not present:
        return None, f"{creature} isn't one of the {family} {role}."
    items = items + [creature] if add else [x for x in items if x.lower() != creature.lower()]
    if items:
        lines[at] = m.group(1) + _flow(items) + (m.group(3) or "")
    else:
        del lines[at]
    return "\n".join(lines), None


def backup_families() -> None:
    FAMILY_BACKUPS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FAMILIES, FAMILY_BACKUPS / f"families-{datetime.now():%Y%m%d-%H%M%S-%f}.yml")
    for old in sorted(FAMILY_BACKUPS.glob("families-*.yml"))[:-PARTY_BACKUPS_KEPT]:
        old.unlink()


# ---------------------------------------------------------------- session recordings

OPEN_RECORDINGS = {}          # id -> Path of a recording in progress (only files this helper created)
LAST_AUDIO = {}               # id -> time the last audio arrived; quiet for 30 s = the recorder is gone
LIVE_SECONDS = 30
JOB = {}                      # the one transcription running (or last run): file, process, log
REC_LOCK = threading.Lock()


def recording_folder(folder) -> Path:
    """The folder asked for, if it exists; otherwise the default (created if need be)."""
    if folder:
        path = Path(str(folder))
        if path.is_dir():
            return path
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    return RECORDINGS


def live_recordings() -> set:
    """Recordings still being made. One whose window was closed without Stop goes quiet, and
    after LIVE_SECONDS counts as finished (it can be transcribed; the audio up to then is kept)."""
    now = time.time()
    return {str(p) for rid, p in OPEN_RECORDINGS.items() if now - LAST_AUDIO.get(rid, 0) < LIVE_SECONDS}


def list_recordings(folder: Path) -> list:
    files = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    recording = live_recordings()
    return [{"name": p.name, "path": str(p), "bytes": p.stat().st_size,
             "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
             "transcript": p.with_name(p.stem + ".transcript.txt").is_file(),
             "recording": str(p) in recording} for p in files]


def new_recording(folder: Path) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d %H%M")
    path, n = folder / f"Session {stamp}.webm", 2
    while path.exists():
        path, n = folder / f"Session {stamp} ({n}).webm", n + 1
    path.touch()
    return path


def browse_folder(start: str):
    """A folder picker, opened on this computer (the one running CampaignCodex5e). macOS and Linux use the
    system's own dialog - tkinter can't open windows from the helper's threads there."""
    title = "Where should session recordings be saved?"
    start = start or str(RECORDINGS)
    if sys.platform == "darwin":
        script = (f'POSIX path of (choose folder with prompt "{title}" '
                  f'default location POSIX file "{start}")')
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return str(Path(r.stdout.strip())) if r.returncode == 0 and r.stdout.strip() else None
    if sys.platform.startswith("linux") and shutil.which("zenity"):
        r = subprocess.run(["zenity", "--file-selection", "--directory", f"--title={title}",
                            f"--filename={start.rstrip('/')}/"], capture_output=True, text=True)
        return str(Path(r.stdout.strip())) if r.returncode == 0 and r.stdout.strip() else None
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    chosen = filedialog.askdirectory(parent=root, initialdir=start, mustexist=True, title=title)
    root.destroy()
    return str(Path(chosen)) if chosen else None


def job_status() -> dict:
    if not JOB:
        return {}
    log = JOB["log"].read_text(encoding="utf-8", errors="replace") if JOB["log"].is_file() else ""
    lines = [ln.strip() for ln in log.splitlines() if ln.strip()]
    progress = next((ln for ln in reversed(lines) if "%" in ln and "to go" in ln), "")
    running = JOB["process"].poll() is None
    code = JOB["process"].returncode
    done = next((ln for ln in reversed(lines) if ln.startswith("Done in")), "")
    error = ""
    if not running and code != 0:
        error = next((ln for ln in reversed(lines) if "Error" in ln or "No recording" in ln), lines[-1] if lines else "It stopped unexpectedly.")
    return {"file": JOB["file"], "running": running, "progress": progress, "done": done, "error": error}


# ---------------------------------------------------------------- item holders
# Who carries each item (data/items/*.yml, "holder:"). Only that one line of the file is changed -
# comments, order, and wording stay as written.

def item_slug(text: str) -> str:   # the ids hooks/entities.py gives items without one
    s = re.sub(r"[^\w\s-]", "", str(text).lower().replace("’", "").replace("'", ""))
    return re.sub(r"[\s_]+", "-", s).strip("-")


def party_characters() -> list:
    data = yaml.safe_load(PARTY.read_text(encoding="utf-8")) or {} if PARTY.is_file() else {}
    return [str(p["character"]) for p in data.get("members") or [] if isinstance(p, dict) and p.get("character")]


def all_items() -> list:
    out = []
    for path in sorted(ITEMS_DIR.glob("*.yml")) if ITEMS_DIR.is_dir() else []:
        for item in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            if isinstance(item, dict) and item.get("name"):
                out.append({"id": str(item.get("id") or item_slug(item["name"])), "name": str(item["name"]),
                            "holder": str(item.get("holder") or ""), "file": path})
    return out


def _yaml_value(text: str) -> str:
    if text.lower() in ("yes", "no", "on", "off", "true", "false", "null", "y", "n", "~"):
        return json.dumps(text)   # YAML would read these as true/false/nothing
    return text if re.match(r"^[A-Za-z][A-Za-z0-9 '.-]*$", text) and not text.endswith(("-", " ")) else json.dumps(text)


def set_item_holder(item_id: str, holder: str) -> Path:
    """Sets (or, with "", removes) one item's holder: line. Returns the file changed."""
    return set_item_line(item_id, "holder", holder or None)


def set_item_line(item_id: str, key: str, value) -> Path:
    """Sets (or, with None, removes) one line of one item - holder: or revealed:. Returns the file changed."""
    item = next((i for i in all_items() if i["id"] == item_id), None)
    if not item:
        raise ValueError(f"No item '{item_id}' in data/items.")
    path = item["file"]
    raw = path.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(nl)
    starts = [i for i, ln in enumerate(lines) if ln.startswith("- ")] + [len(lines)]
    block = None
    for a, b in zip(starts, starts[1:]):
        entry = (yaml.safe_load(nl.join(lines[a:b])) or [None])[0]
        if isinstance(entry, dict) and str(entry.get("id") or item_slug(entry.get("name", ""))) == item_id:
            block = (a, b)
            break
    if not block:
        raise ValueError(f"Couldn't find '{item_id}' in {path.name}.")
    a, b = block
    at = next((i for i in range(a, b) if re.match(rf"^  {key}\s*:", lines[i])), None)
    shown = ("true" if value else "false") if isinstance(value, bool) else _yaml_value(value) if value is not None else None
    new_line = f"  {key}: {shown}" if shown is not None else None
    if at is not None:
        lines[at:at + 1] = [new_line] if new_line else []
    elif new_line:
        # before the long fields (flavor, text...), so a folded value is never split
        at = next((i for i in range(a + 1, b) if re.match(r"^  (flavor|text|also|aliases)\s*:", lines[i])), None)
        if at is None:
            at = b
            while at > a + 1 and not lines[at - 1].strip():
                at -= 1
        lines.insert(at, new_line)
    text = nl.join(lines)
    check = next((i for i in (yaml.safe_load(text) or []) if isinstance(i, dict)
                  and str(i.get("id") or item_slug(i.get("name", ""))) == item_id), None)
    if not check or check.get(key) != value:   # reads back exactly as meant
        raise ValueError(f"Changing {path.name} didn't come out right, so it was left alone.")
    ITEM_BACKUPS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, ITEM_BACKUPS / f"{path.stem}-{datetime.now():%Y%m%d-%H%M%S}.yml")
    for old in sorted(ITEM_BACKUPS.glob(f"{path.stem}-*.yml"))[:-ITEM_BACKUPS_KEPT]:
        old.unlink()
    path.write_text(text, encoding="utf-8", newline="")
    return path


def check_holder(holder) -> str:
    holder = str(holder or "").strip()
    if not holder or holder.lower() in ("party", "unclaimed"):
        return holder.title() if holder else ""   # "Unclaimed": found, up for grabs on the players' site
    match = next((c for c in party_characters() if c.lower() == holder.lower()), None)
    if not match:
        raise ValueError(f"'{holder}' isn't a character in data/party.yml.")
    return match


def item_suggestions(folder) -> list:
    """Pickups tools/transcribe.py noticed (<recording>.items.json), not yet assigned or dismissed."""
    out = []
    for path in sorted(recording_folder(folder).glob("*.items.json")):
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for n, e in enumerate(entries):
            if isinstance(e, dict) and not e.get("done"):
                out.append(dict(e, file=str(path), n=n, recording=path.name[:-len(".items.json")]))
    return out


# ---------------------------------------------------------------- the players' live tracker
# The initiative tracker's "Share with players" sends each change here; a background thread passes
# the newest one to the players' site (publish/players/worker.js), so a slow connection never holds
# up the tracker, and changes in between are skipped rather than queued. Only names, initiative, the
# turn, and conditions go out - clean_share() drops everything else.
# campaign.yml's online: settings say where the players' site is; CODEX_TRACKER_URL is for testing only.
TRACKER_URL = os.environ.get("CODEX_TRACKER_URL") or (CAMPAIGN["players_url"] + "api/tracker" if CAMPAIGN["players_url"] else "")
TRACKER_TOKEN = ROOT / "tools" / "tracker-token.txt"
NOT_ONLINE = ("The players' site isn't online yet - set online: in campaign.yml and publish it "
              "(see Going online in the guide).")
SHARE = {"view": None, "wake": threading.Event(), "thread": None,
         "last": {"ok": None, "error": "", "at": 0, "watching": None}}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):   # sent to the login page = the token wasn't accepted
        return None


SHARE_OPENER = build_opener(_NoRedirect)


def tracker_token():
    """(client id, secret) from tools/tracker-token.txt: two lines; labels like "CF-Access-Client-Id:" are fine."""
    if not TRACKER_TOKEN.is_file():
        return None
    lines = [re.sub(r"^[A-Za-z-]+\s*[:=]\s*", "", ln.strip())
             for ln in TRACKER_TOKEN.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    return (lines[0], lines[1]) if len(lines) >= 2 else None


def clean_share(raw) -> dict:
    if not isinstance(raw, dict) or not raw.get("active"):
        return {"active": False, "victory": True} if isinstance(raw, dict) and raw.get("victory") is True else {"active": False}

    def whole(v):
        return v if isinstance(v, int) and not isinstance(v, bool) and abs(v) < 1000 else None
    rows = []
    for x in (raw.get("list") or [])[:60]:
        if not isinstance(x, dict):
            continue
        rows.append({"name": str(x.get("name") or "")[:60], "init": whole(x.get("init")), "pc": bool(x.get("pc")),
                     "cur": bool(x.get("cur")), "out": bool(x.get("out")), "conc": bool(x.get("conc")),
                     "conds": [{"n": str(c.get("n") or "")[:30], "r": whole(c.get("r"))}
                               for c in (x.get("conds") or [])[:15] if isinstance(c, dict)]})
    return {"active": True, "started": bool(raw.get("started")), "round": whole(raw.get("round")) or 1, "list": rows}


# ---------------------------------------------------------------- card suggestions
# Players suggest changes to their own card on the players' site; the worker keeps them until you
# decide. These fields are all a suggestion can change (not the name, player, email, or DM note).
PLAYER_FIELDS = ("race", "class", "level", "ac", "ac_note", "hp", "hp_formula", "speed", "initiative",
                 "passive_perception", "abilities", "saves", "skills", "resistances", "immunities",
                 "condition_immunities", "senses", "languages", "features", "actions", "bonus_actions", "reactions")
FIELD_LABELS = {"ac": "AC", "ac_note": "AC note", "hp": "HP", "hp_formula": "HP formula",
                "passive_perception": "Passive Perception", "condition_immunities": "Condition immunities",
                "bonus_actions": "Bonus actions"}


def players_api(method: str, path: str, body=None):
    """A call to the players' site's worker with the service token: (status, json)."""
    if not TRACKER_URL:
        raise ValueError(NOT_ONLINE)
    token = tracker_token()
    if not token:
        raise ValueError("tools/tracker-token.txt is missing - see Going online in the guide.")
    base = TRACKER_URL.rsplit("/api/", 1)[0]
    req = Request(base + path, data=json.dumps(body).encode("utf-8") if body is not None else None, method=method,
                  headers={"Content-Type": "application/json", "User-Agent": "CampaignCodex5e-helper",
                           "CF-Access-Client-Id": token[0], "CF-Access-Client-Secret": token[1]})
    try:
        with SHARE_OPENER.open(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"{}")
    except HTTPError as err:
        if err.code in (301, 302, 303, 401, 403):
            raise ValueError("The players' site didn't accept the token - check tools/tracker-token.txt.")
        raise ValueError(f"The players' site answered {err.code}.")
    except (URLError, OSError) as err:
        raise ValueError(f"Couldn't reach the players' site ({getattr(err, 'reason', err)}).")


def _shown(key, value) -> str:
    if value in (None, "", [], {}):
        return "—"
    if key == "abilities":
        return ", ".join(f"{a.upper()} {value[a]}" for a in ABILITIES if a in value)
    if isinstance(value, list):
        return "; ".join(f"{e.get('name', '')}: {e.get('text', '')}" for e in value)
    return str(value)


def card_changes(current: dict, proposed: dict) -> list:
    out = []
    for key in PLAYER_FIELDS:
        old, new = current.get(key), proposed.get(key)
        if (old in (None, "", [], {}) and new in (None, "", [], {})) or old == new:
            continue
        out.append({"field": FIELD_LABELS.get(key, key.replace("_", " ").capitalize()),
                    "old": _shown(key, old), "new": _shown(key, new)})
    return out


def share_sender():
    while True:
        SHARE["wake"].wait()
        SHARE["wake"].clear()
        view, SHARE["view"] = SHARE["view"], None
        if view is None:
            continue
        token = tracker_token()
        last = {"ok": False, "error": "", "at": time.time(), "watching": None}
        if not TRACKER_URL:
            last["error"] = NOT_ONLINE
        elif not token:
            last["error"] = "tools/tracker-token.txt is missing - see Going online in the guide."
        else:
            req = Request(TRACKER_URL, data=json.dumps(view).encode("utf-8"), method="POST", headers={
                "Content-Type": "application/json", "User-Agent": "CampaignCodex5e-helper",
                "CF-Access-Client-Id": token[0], "CF-Access-Client-Secret": token[1]})
            try:
                with SHARE_OPENER.open(req, timeout=10) as r:
                    body = json.loads(r.read() or b"{}")
                last.update(ok=True, watching=body.get("watching"))
            except HTTPError as err:
                last["error"] = ("The players' site didn't accept the token - check tools/tracker-token.txt and the "
                                 "tracker push policy (see Going online in the guide)." if err.code in (301, 302, 303, 401, 403)
                                 else f"The players' site answered {err.code}.")
            except (URLError, OSError, ValueError) as err:
                last["error"] = f"Couldn't reach the players' site ({getattr(err, 'reason', err)})."
        SHARE["last"] = last


# ---------------------------------------------------------------- the server

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        # Pages served by CampaignCodex5e, or opened from disk (origin "null").
        origin = self.headers.get("Origin", "")
        if origin in ("null", "") or origin.startswith(("http://127.0.0.1", "http://localhost")):
            self.send_header("Access-Control-Allow-Origin", origin or "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _reply(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/ping":
            return self._reply(200, {"ok": True})
        if url.path == "/creature":
            return self.get_creature((parse_qs(url.query).get("id") or [""])[0])
        if url.path == "/party":
            return self.get_party()
        if url.path == "/recordings":
            return self.get_recordings((parse_qs(url.query).get("folder") or [""])[0])
        if url.path == "/transcribe":
            return self._reply(200, {"job": job_status()})
        if url.path == "/tracker/share":
            return self._reply(200, {"last": SHARE["last"], "token": TRACKER_TOKEN.is_file()})
        if url.path == "/party/suggestions":
            return self.party_suggestions()
        if url.path == "/item/claims":
            return self.item_claims()
        if url.path == "/items":
            return self._reply(200, {"items": [{k: i[k] for k in ("id", "name", "holder")} for i in all_items()],
                                     "party": party_characters()})
        if url.path == "/item/suggestions":
            return self._reply(200, {"suggestions": item_suggestions((parse_qs(url.query).get("folder") or [""])[0])})
        self._reply(404, {"error": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/recording/chunk":   # raw audio, not JSON
            q = parse_qs(url.query)
            return self.recording_chunk((q.get("id") or [""])[0], (q.get("file") or [""])[0])
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._reply(400, {"error": "Couldn't read the request."})
        # Recording and the folder picker don't touch the data files, so they skip the write lock
        # (a folder picker left open mustn't hold up the encounter builder).
        if url.path in ("/folder/browse", "/recording/start", "/recording/stop", "/transcribe", "/turnlog",
                        "/tracker/share"):
            handler = {"/folder/browse": self.folder_browse, "/recording/start": self.recording_start,
                       "/recording/stop": self.recording_stop, "/transcribe": self.transcribe_start,
                       "/turnlog": self.turnlog, "/tracker/share": self.tracker_share}[url.path]
            try:
                return handler(data)
            except OSError as err:
                return self._reply(500, {"error": f"Couldn't write the file: {err}"})
        routes = {"/encounter": self.save, "/encounter/archive": self.archive,
                  "/encounter/delete": self.delete, "/creature": self.save_creature,
                  "/creature/delete": self.delete_creature, "/party/member": self.save_member,
                  "/party/member/delete": self.delete_member, "/family": self.family,
                  "/item/holder": self.item_holder, "/item/suggestion": self.item_suggestion,
                  "/party/suggestion": self.party_suggestion, "/item/claim": self.item_claim,
                  "/party/import": self.party_import,
                  "/item/reveal": self.item_reveal}
        if self.path not in routes:
            return self._reply(404, {"error": "not found"})
        try:
            with WRITE_LOCK:
                routes[self.path](data)
        except OSError as err:
            self._reply(500, {"error": f"Couldn't write the file: {err}"})
        except yaml.YAMLError as err:
            self._reply(500, {"error": f"data/monsters/custom.yml couldn't be read - fix it by hand first. ({err})"})

    # -------------------------------------------------------------- actions

    def party_suggestions(self):
        try:
            _, body = players_api("GET", "/api/cards/suggestions")
        except ValueError as err:
            return self._reply(502, {"error": str(err)})
        _, members = self._party()
        out = []
        for s in body.get("suggestions") or []:
            current = next((m for m in members if str(m.get("character", "")).lower() == str(s.get("character", "")).lower()), None)
            out.append({"id": s.get("id"), "character": s.get("character"), "email": s.get("email"), "at": s.get("at"),
                        "missing": current is None, "changes": card_changes(current or {}, s.get("member") or {})})
        self._reply(200, {"suggestions": out})

    def party_suggestion(self, data):
        action = data.get("action")
        if action not in ("approve", "reject"):
            return self._reply(400, {"error": "Approve or reject?"})
        try:
            _, body = players_api("GET", "/api/cards/suggestions")
            s = next((x for x in body.get("suggestions") or [] if x.get("id") == data.get("id")), None)
            if not s:
                return self._reply(404, {"error": "That suggestion isn't waiting any more - reload the page."})
            if action == "approve":
                party, members = self._party()
                index = next((i for i, m in enumerate(members)
                              if str(m.get("character", "")).lower() == str(s.get("character", "")).lower()), None)
                if index is None:
                    return self._reply(404, {"error": f"{s.get('character')} isn't in data/party.yml any more."})
                current, proposed = members[index], s.get("member") or {}
                merged = {k: v for k, v in current.items() if k not in PLAYER_FIELDS}
                merged.update({k: proposed[k] for k in PLAYER_FIELDS if k in proposed})
                member, error = clean_member(merged, current)
                if error:
                    return self._reply(400, {"error": error})
                members[index] = member
                backup_party()
                write_party(members)
            players_api("POST", "/api/cards/resolve", {"id": s["id"], "status": "approved" if action == "approve" else "rejected"})
        except ValueError as err:
            return self._reply(502, {"error": str(err)})
        self._reply(200, {"ok": True, "character": s.get("character"), "action": action})

    def item_claims(self):
        try:
            _, body = players_api("GET", "/api/items/claims")
        except ValueError as err:
            return self._reply(502, {"error": str(err)})
        names = {i["id"]: i for i in all_items()}
        out = [dict(c, item_name=names.get(c.get("item"), {}).get("name", c.get("item")),
                    holder=names.get(c.get("item"), {}).get("holder", ""))
               for c in body.get("claims") or [] if c.get("status") == "pending"]
        self._reply(200, {"claims": out})

    def item_claim(self, data):
        action = data.get("action")
        if action not in ("approve", "reject"):
            return self._reply(400, {"error": "Approve or decline?"})
        try:
            _, body = players_api("GET", "/api/items/claims")
            claims = body.get("claims") or []
            c = next((x for x in claims if x.get("id") == data.get("id") and x.get("status") == "pending"), None)
            if not c:
                return self._reply(404, {"error": "That claim isn't waiting any more - reload the page."})
            if action == "approve":
                holder = check_holder(c.get("character"))
                set_item_holder(str(c.get("item")), holder)
                for other in claims:   # the others who asked for it
                    if other.get("item") == c["item"] and other.get("id") != c["id"] and other.get("status") == "pending":
                        players_api("POST", "/api/items/resolve", {"id": other["id"], "status": "rejected"})
            players_api("POST", "/api/items/resolve", {"id": c["id"], "status": "approved" if action == "approve" else "rejected"})
        except ValueError as err:
            return self._reply(502, {"error": str(err)})
        self._reply(200, {"ok": True, "character": c.get("character"), "action": action})

    def item_reveal(self, data):
        choice = data.get("reveal")
        if choice not in ("auto", "show", "hide"):
            return self._reply(400, {"error": "Automatic, show, or hide?"})
        try:
            path = set_item_line(str(data.get("id", "")), "revealed", {"auto": None, "show": True, "hide": False}[choice])
        except ValueError as err:
            return self._reply(400, {"error": str(err)})
        self._reply(200, {"ok": True, "reveal": choice, "file": f"data/items/{path.name}"})

    def item_holder(self, data):
        try:
            holder = check_holder(data.get("holder"))
            path = set_item_holder(str(data.get("id", "")), holder)
        except ValueError as err:
            return self._reply(400, {"error": str(err)})
        self._reply(200, {"ok": True, "holder": holder, "file": f"data/items/{path.name}"})

    def item_suggestion(self, data):
        path = Path(str(data.get("file", "")))
        if not path.name.endswith(".items.json") or not path.is_file():
            return self._reply(400, {"error": "That suggestion list isn't there any more."})
        entries = json.loads(path.read_text(encoding="utf-8"))
        n = data.get("n")
        if not isinstance(n, int) or not 0 <= n < len(entries):
            return self._reply(400, {"error": "That suggestion isn't there any more."})
        e = entries[n]
        if data.get("action") == "assign":
            try:
                holder = check_holder(data.get("holder"))
                if not holder:
                    raise ValueError("Pick who has it first.")
                set_item_holder(str(e.get("item_id", "")), holder)
            except ValueError as err:
                return self._reply(400, {"error": str(err)})
            e["done"] = f"assigned to {holder}"
        else:
            e["done"] = "dismissed"
        path.write_text(json.dumps(entries, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
        self._reply(200, {"ok": True, "done": e["done"]})

    def tracker_share(self, data):
        SHARE["view"] = clean_share(data.get("view"))
        if SHARE["thread"] is None:
            SHARE["thread"] = threading.Thread(target=share_sender, daemon=True)
            SHARE["thread"].start()
        SHARE["wake"].set()
        return self._reply(200, {"queued": True, "last": SHARE["last"], "token": TRACKER_TOKEN.is_file()})

    def save(self, data):
        enc = data.get("encounter") or {}
        eid = str(enc.get("id", ""))
        if not ID_OK.match(eid):
            return self._reply(400, {"error": "The id must be lowercase letters, numbers, and dashes."})
        creatures = [{"id": str(c["id"]), "count": max(1, int(c.get("count", 1)))}
                     for c in enc.get("creatures", []) if c.get("id")]
        if not creatures:
            return self._reply(400, {"error": "The encounter has no creatures."})
        path, existing = find_encounter(eid)
        if path and not data.get("overwrite"):
            return self._reply(409, {"error": f"An encounter with the id {eid} already exists.", "exists": True})
        header = comment_header(path) if path else "# Saved by the encounter builder."
        merged = dict(existing or {})   # keep fields the builder doesn't edit: page, pinned level, archived
        merged.update({"id": eid, "name": str(enc.get("name") or eid).strip(), "creatures": creatures})
        location = str(enc.get("location") or "").strip()
        if location:
            merged["location"] = location
        else:
            merged.pop("location", None)
        ENCOUNTERS.mkdir(parents=True, exist_ok=True)
        path = path or ENCOUNTERS / f"{eid}.yml"
        write_encounter(path, merged, header)
        self._reply(200, {"saved": f"data/encounters/{path.name}", "updated": bool(existing)})

    def archive(self, data):
        eid = str(data.get("id", ""))
        path, enc = find_encounter(eid)
        if not path:
            return self._reply(404, {"error": f"No encounter with the id {eid}."})
        if data.get("archived", True):
            enc["archived"] = True
        else:
            enc.pop("archived", None)
        write_encounter(path, enc, comment_header(path))
        self._reply(200, {"id": eid, "archived": bool(enc.get("archived"))})

    def delete(self, data):
        eid = str(data.get("id", ""))
        path, enc = find_encounter(eid)
        if not path:
            return self._reply(404, {"error": f"No encounter with the id {eid}."})
        if not enc.get("archived"):
            return self._reply(409, {"error": "Only archived encounters can be deleted - archive it first."})
        used = pages_using(eid)
        if used:
            return self._reply(409, {"error": "This encounter is shown on " + ", ".join(used) +
                                     ". Remove it from the page first - or keep it archived.", "pages": used})
        BACKUPS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(path), str(BACKUPS / f"{path.stem}-{stamp}.yml"))
        self._reply(200, {"deleted": eid, "backup": f"sources/backups/encounters/{path.stem}-{stamp}.yml"})

    # -------------------------------------------------------------- creatures

    def get_creature(self, cid):
        fname, entry = all_creatures().get(cid, (None, None))
        if not entry:
            return self._reply(404, {"error": f"No creature with the id {cid}."})
        self._reply(200, {"creature": entry, "custom": fname == CUSTOM.name, "file": f"data/monsters/{fname}"})

    def save_creature(self, data):
        raw = data.get("creature") or {}
        cid = str(raw.get("id", ""))
        existing = read_custom()
        index = next((i for i, e in enumerate(existing) if str(e.get("id")) == cid), None)
        if data.get("editing"):
            if index is None:
                return self._reply(404, {"error": f"There's no custom creature with the id {cid} to update."})
        else:
            fname, _ = all_creatures().get(cid, (None, None))
            if fname:
                return self._reply(409, {"error": f"The id {cid} is already used by a creature in "
                                                  f"data/monsters/{fname}. Pick another."})
        creature, error = clean_creature(raw, existing[index] if index is not None else None)
        if error:
            return self._reply(400, {"error": error})
        if index is None:
            existing.append(creature)
        else:
            existing[index] = creature
        write_custom(existing)
        self._reply(200, {"saved": "data/monsters/custom.yml", "id": cid, "updated": index is not None})

    def delete_creature(self, data):
        cid = str(data.get("id", ""))
        existing = read_custom()
        entry = next((e for e in existing if str(e.get("id")) == cid), None)
        if not entry:
            return self._reply(404, {"error": "Only custom creatures can be deleted here."})
        users = creature_users(cid)
        if users:
            return self._reply(409, {"error": "Still used by " + "; ".join(users) +
                                     ". Take it out of those first.", "users": users})
        CREATURE_BACKUPS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = CREATURE_BACKUPS / f"{cid}-{stamp}.yml"
        backup.write_text(f"# Deleted from data/monsters/custom.yml on {datetime.now():%Y-%m-%d %H:%M}.\n"
                          "# To bring it back, paste the entry below into custom.yml.\n"
                          + dump_creature(entry) + "\n", encoding="utf-8", newline="\n")
        write_custom([e for e in existing if e is not entry])
        self._reply(200, {"deleted": cid, "backup": f"sources/backups/creatures/{backup.name}"})

    # -------------------------------------------------------------- party

    def _party(self):
        data = yaml.safe_load(PARTY.read_text(encoding="utf-8")) or {}
        members = [m for m in data.get("members") or [] if isinstance(m, dict)]
        return data, members

    def _check_index(self, members, data):
        """The member the page means, or None after replying (the file changed under it)."""
        index = data.get("index")
        if not isinstance(index, int) or not 0 <= index < len(members) or \
                str(members[index].get("character", "")) != str(data.get("expect", "")):
            self._reply(409, {"error": "data/party.yml has changed since this page loaded - reload the page and try again."})
            return None
        return index

    def get_party(self):
        data, members = self._party()
        self._reply(200, {"level": data.get("level"), "size": data.get("size"), "members": members})

    def save_member(self, data):
        party, members = self._party()
        editing = data.get("index") is not None
        index = self._check_index(members, data) if editing else None
        if editing and index is None:
            return
        member, error = clean_member(data.get("member") or {}, members[index] if editing else None)
        if error:
            return self._reply(400, {"error": error})
        name = member["character"].strip().lower()
        if any(str(m.get("character", "")).strip().lower() == name for i, m in enumerate(members) if i != index):
            return self._reply(409, {"error": f"There's already a character called {member['character']}."})
        size = None
        if editing:
            members[index] = member
        else:
            members.append(member)
            if party.get("size") == len(members) - 1:   # the size followed the party: keep it that way
                size = len(members)
        backup_party()
        write_party(members, size)
        self._reply(200, {"saved": "data/party.yml", "character": member["character"], "updated": editing,
                          "size": size})

    def party_import(self, data):
        """A CCC5e export (.ccc5e) onto the Party page: {"file": its text, "index": the card to update (or none:
        the character of that name, or a new one), "expect": that card's name, "save": false for the preview}.
        The preview lists what would change; saving keeps the player, email, note and private marks."""
        import import_ccc5e as ccc
        try:
            src = ccc.load_text(str(data.get("file") or ""), str(data.get("name") or "That file"))
        except ValueError as err:
            return self._reply(400, {"error": str(err)})
        new = ccc.card(src)
        if not new.get("character"):
            return self._reply(400, {"error": "That file's character has no name."})
        party, members = self._party()
        if data.get("index") is not None:
            index = self._check_index(members, data)
            if index is None:
                return
        else:
            index = ccc.find(members, new["character"])
        old = members[index] if index is not None else {}
        merged = ccc.merge(old, new)
        if old.get("portrait"):
            merged["portrait"] = old["portrait"]
        merged, error = clean_member(merged)
        if error:
            return self._reply(400, {"error": error})
        name = merged["character"].strip().lower()
        if any(str(m.get("character", "")).strip().lower() == name for i, m in enumerate(members) if i != index):
            return self._reply(409, {"error": f"There's already a character called {merged['character']} - import it onto that card."})
        if not data.get("save"):
            return self._reply(200, {
                "character": merged["character"], "adding": index is None, "replacing": old.get("character"),
                "has_sheet": isinstance(src.get("Sheet"), dict), "portrait": bool(ccc.portrait_bytes(src)),
                "summary": " ".join(str(x) for x in (merged.get("race"), merged.get("class"), merged.get("level")) if x),
                "changes": [list(c) for c in ccc.changes(old, merged)] if old else []})
        portrait = ccc.save_portrait(src, merged["character"])
        if portrait:
            merged["portrait"] = portrait
        size = None
        backup_party()
        if index is None:
            members.append(merged)
            if party.get("size") == len(members) - 1:   # the size followed the party: keep it that way
                size = len(members)
        else:
            members[index] = merged
        write_party(members, size)
        self._reply(200, {"saved": "data/party.yml", "character": merged["character"], "added": index is None})

    def delete_member(self, data):
        party, members = self._party()
        index = self._check_index(members, data)
        if index is None:
            return
        gone = members.pop(index)
        size = len(members) if party.get("size") == len(members) + 1 else None
        backup_party()
        write_party(members, size)
        self._reply(200, {"removed": gone.get("character"), "size": size})

    # -------------------------------------------------------------- encounter families

    def family(self, data):
        family = " ".join(str(data.get("family", "")).split())
        creature = " ".join(str(data.get("creature", "")).split())
        role, add, new = data.get("role"), data.get("action", "add") == "add", bool(data.get("new"))
        if role not in ("members", "leaders") or not family or not creature or len(family) > 80:
            return self._reply(400, {"error": "Pick a family, a creature, and member or leader."})
        if new and not add:
            return self._reply(400, {"error": "A new family starts with a creature in it."})
        known = {str(e.get("name", "")).lower() for _, e in all_creatures().values()} | set(all_creatures())
        if creature.lower() not in known and creature not in known:
            return self._reply(404, {"error": f"No creature called {creature}."})
        before = FAMILIES.read_text(encoding="utf-8") if FAMILIES.is_file() else ""
        after, error = edit_family(before, family, creature, role, add, new)
        if error:
            return self._reply(409, {"error": error})
        # Check the edited file reads back with exactly the change asked for, before writing it.
        parsed = yaml.safe_load(after) or []
        entry = next((f for f in parsed if str(f.get("family", "")).lower() == family.lower()), None)
        listed = [str(x).lower() for x in (entry or {}).get(role) or []]
        if not isinstance(parsed, list) or (add and creature.lower() not in listed) or (not add and creature.lower() in listed):
            return self._reply(500, {"error": "That change didn't come out right, so families.yml was left as it was."})
        if FAMILIES.is_file():
            backup_families()
        FAMILIES.write_text(after, encoding="utf-8", newline="\n")
        self._reply(200, {"family": entry.get("family"), "role": role, "members": entry.get("members") or [],
                          "leaders": entry.get("leaders") or []})

    # -------------------------------------------------------------- session recordings

    def get_recordings(self, folder):
        path = recording_folder(folder)
        self._reply(200, {"folder": str(path), "default": str(recording_folder(None)),
                          "asked": folder, "found": not folder or Path(folder).is_dir(),
                          "files": list_recordings(path), "job": job_status()})

    def folder_browse(self, data):
        try:
            chosen = browse_folder(str(data.get("start") or ""))
        except Exception as err:   # no display, tkinter missing...
            return self._reply(500, {"error": f"Couldn't open the folder picker: {err}"})
        self._reply(200, {"folder": chosen})

    def recording_start(self, data):
        folder = recording_folder(data.get("folder"))
        with REC_LOCK:
            path = new_recording(folder)
            rid = datetime.now().strftime("%Y%m%d%H%M%S%f")
            OPEN_RECORDINGS[rid] = path
            LAST_AUDIO[rid] = time.time()
        self._reply(200, {"id": rid, "file": str(path), "name": path.name})

    def recording_chunk(self, rid, file=""):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        path = OPEN_RECORDINGS.get(rid)
        if not path and file:
            # CampaignCodex5e was restarted mid-recording: carry on in the same file - but only one of
            # this helper's own recordings (an existing "Session ....webm"), never anything else.
            candidate = Path(file)
            if candidate.is_file() and re.match(r"^Session .+\.webm$", candidate.name):
                with REC_LOCK:
                    OPEN_RECORDINGS[rid] = path = candidate
        if not path:
            return self._reply(404, {"error": "That recording isn't open."})
        try:
            with REC_LOCK, open(path, "ab") as f:
                f.write(body)
                f.flush()
                os.fsync(f.fileno())   # on disk now, not just in memory - a crash loses seconds at most
            LAST_AUDIO[rid] = time.time()
        except OSError as err:
            return self._reply(500, {"error": f"Couldn't write the recording: {err}"})
        self._reply(200, {"bytes": path.stat().st_size})

    def recording_stop(self, data):
        with REC_LOCK:
            path = OPEN_RECORDINGS.pop(str(data.get("id", "")), None)
            LAST_AUDIO.pop(str(data.get("id", "")), None)
        if not path:
            return self._reply(404, {"error": "That recording isn't open."})
        self._reply(200, {"file": str(path), "name": path.name, "bytes": path.stat().st_size})

    def turnlog(self, data):
        """One line of the initiative tracker's turn log, added to <recording>.turns.txt next to the
        recording it happened during (only one of this helper's own recordings)."""
        audio = Path(str(data.get("file", "")))
        rec, text = str(data.get("rec", "")), " ".join(str(data.get("text", "")).split())
        if not (audio.is_file() and re.match(r"^Session .+\.webm$", audio.name)) or \
                not re.match(r"^\d\d:\d\d:\d\d$", rec) or not text:
            return self._reply(400, {"error": "Not a turn log line for a recording."})
        log = audio.with_name(audio.stem + ".turns.txt")
        with REC_LOCK, open(log, "a", encoding="utf-8", newline="\n") as f:
            f.write(f"[{rec}] {text[:300]}\n")
        self._reply(200, {"saved": log.name})

    def transcribe_start(self, data):
        audio = Path(str(data.get("file", "")))
        if not audio.is_file() or audio.suffix.lower() not in AUDIO:
            return self._reply(404, {"error": "That recording wasn't found."})
        if str(audio) in live_recordings():
            return self._reply(409, {"error": "That one is still being recorded - stop it first."})
        with REC_LOCK:
            if JOB and JOB["process"].poll() is None:
                return self._reply(409, {"error": f"Already transcribing {Path(JOB['file']).name} - one at a time."})
            log = Path(tempfile.gettempdir()) / "CampaignCodex5e-transcribe-log.txt"   # progress, read by job_status()
            env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
            with open(log, "w", encoding="utf-8") as out:
                proc = subprocess.Popen([sys.executable, str(TRANSCRIBE), str(audio)], stdout=out,
                                        stderr=subprocess.STDOUT, cwd=str(ROOT), env=env,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            JOB.clear()
            JOB.update({"file": str(audio), "process": proc, "log": log})
        self._reply(200, {"job": job_status()})

    def log_message(self, fmt, *args):
        pass  # keep the CampaignCodex5e window quiet


def main() -> int:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Save helper: port {PORT} is already in use (is another copy running?).")
        return 1
    print(f"Save helper running at http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
