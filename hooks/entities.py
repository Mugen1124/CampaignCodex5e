"""
Campaign entities: NPCs, locations, factions, and items as data.

Data files (one list or mapping per file; see templates/ for every field):
    data/npcs/*.yml         NPCs, grouped into regions on the NPC Index
    data/locations/*.yml    one file per city, grouped into districts
    data/factions.yml       factions
    data/items/*.yml        magic items and notable loot

Page markers (each alone on its own line):
    {{ npc-index }}              every NPC, full entries, grouped by region and group
    {{ npc-list greywater }}     a region's NPCs as a compact who's-who (names hover)
    {{ locations greywater }}    a city's locations, with the NPCs found at each
    {{ factions }}               every faction, with its members
    {{ items }}                  every item, full rules text

Mentions, anywhere in page text:
    [[Hester Vane]]          link with a hover card (NPC, location, faction, item, or creature)
    [[Hester Vane|Hester]]   same, different display text
Only the first mention of a thing in each ## section becomes a link; later ones
are plain text. Mentions in headings and read-aloud boxes are always plain text.

Page setting (front matter at the very top of a page):
    ---
    toc_depth: 2
    ---
limits the right-hand table of contents to ## headings.

Build checks (warnings in the serve/build window): missing required fields,
unknown [[mentions]], references to locations/factions that don't exist,
near-identical names (allow known pairs in data/checks.yml), and any mention of
a word listed under banned: in campaign.yml (a feat your table has removed, say).
"""

import difflib
import html
import json
import logging
import posixpath
import re
from pathlib import Path

import sys

import markdown as md_lib
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex import settings as codex_settings  # noqa: E402
from codex import rules as codex_rules  # noqa: E402

log = logging.getLogger("mkdocs.hooks.entities")

NPC_PAGE = "reference/npcs.md"
RULE_KINDS = ("condition", "spell", "srditem")
ITEM_PAGE = "reference/items.md"
FACTION_PAGE = "world/factions.md"
BESTIARY_PAGE = "reference/bestiary.md"

REQUIRED = {
    "npc": ["name", "region", "role", "hook"],
    "location": ["name", "description"],
    "faction": ["name", "summary"],
    "item": ["name", "type", "rarity", "text"],
}

NPCS, LOCATIONS, CITIES, FACTIONS, ITEMS, CREATURES = {}, {}, {}, {}, {}, {}
REGISTRY = {}          # normalized name/alias -> (kind, id)
ALLOW_SIMILAR = set()  # frozensets of ids allowed to have similar names

# The player site (mkdocs-players.yml, extra: audience: players) shows only what the party has
# come across: anything mentioned in the Session Log, anything marked `revealed: true` in its
# data (or listed under reveal: in data/revealed.yml), and never anything marked `revealed: false`
# (or listed under hide:). DM-only fields (notes, secret, dm_notes...) are never shown there.
PLAYERS = [False]
REVEALED = set()       # (kind, id) the players may see
DATA_ROOT = [None]   # data/, set in on_config
SETTINGS = [codex_settings.DEFAULTS]   # campaign.yml, set in on_config

MENTION = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]")
MARKER = re.compile(r"^([ \t]*)\{\{\s*(npc-index|npc-list|locations|factions|items)\b\s*([A-Za-z0-9_-]*)\s*\}\}[ \t]*$",
                    re.MULTILINE)


# ---------------------------------------------------------------- helpers

def slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower().replace("’", "").replace("'", ""))
    return re.sub(r"[\s_]+", "-", s).strip("-")


def key(name: str) -> str:
    """Matching key for names: case-, apostrophe-, and leading-'the'-insensitive."""
    k = name.lower().replace("’", "'").strip()
    k = re.sub(r"^the\s+", "", k)
    return re.sub(r"\s+", " ", k)


def mdhtml(text) -> str:
    return md_lib.markdown(plain_refs(text), extensions=["attr_list"])


def plain_refs(text) -> str:
    """For hover cards: [[mentions]] and [links](...) become their display text."""
    text = MENTION.sub(lambda m: (m.group(2) or m.group(1)).strip(), str(text or ""))
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)


def mdinline(text) -> str:
    out = mdhtml(plain_refs(text)).strip()
    return re.sub(r"^<p>(.*)</p>$", r"\1", out, flags=re.S)


def rel(page_src: str, target: str) -> str:
    start = posixpath.dirname(page_src) or "."
    return posixpath.relpath(target, start)


def _load(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        log.warning("Could not read %s: %s", path.name, err)
        return None


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _register(kind: str, eid: str, names, source: str):
    for n in names:
        if not n:
            continue
        k = key(str(n))
        if k in REGISTRY and REGISTRY[k] != (kind, eid):
            other = REGISTRY[k]
            log.warning("Name '%s' is used by both %s '%s' and %s '%s' (%s)",
                        n, other[0], other[1], kind, eid, source)
            continue
        REGISTRY[k] = (kind, eid)


def _check_required(kind: str, entry: dict, source: str):
    missing = [f for f in REQUIRED[kind] if not entry.get(f)]
    if missing:
        log.warning("%s '%s' in %s is missing: %s", kind.capitalize(),
                    entry.get("name", entry.get("id", "?")), source, ", ".join(missing))


# ---------------------------------------------------------------- loading

def on_config(config, **kwargs):
    root = Path(config.config_file_path).parent / "data"
    DATA_ROOT[0] = root
    SETTINGS[0] = codex_settings.load(root.parent)
    for d in (NPCS, LOCATIONS, CITIES, FACTIONS, ITEMS, CREATURES, REGISTRY):
        d.clear()
    ALLOW_SIMILAR.clear()

    checks = _load(root / "checks.yml") if (root / "checks.yml").is_file() else None
    for pair in (checks or {}).get("allow_similar", []):
        ALLOW_SIMILAR.add(frozenset(pair))

    # Locations: one file per city.
    for path in sorted((root / "locations").glob("*.yml")):
        city = _load(path) or {}
        cid = city.get("id") or path.stem
        city["id"] = cid
        CITIES[cid] = city
        for district in city.get("districts", []):
            for loc in district.get("locations", []):
                loc.setdefault("id", slug(loc.get("name", "")))
                loc["_city"], loc["_district"] = cid, district.get("name")
                _check_required("location", loc, path.name)
                LOCATIONS[loc["id"]] = loc
                _register("location", loc["id"], [loc.get("name")] + _as_list(loc.get("aliases")), path.name)

    # Factions: one file.
    fpath = root / "factions.yml"
    for fac in _as_list(_load(fpath) if fpath.is_file() else None):
        fac.setdefault("id", slug(fac.get("name", "")))
        _check_required("faction", fac, fpath.name)
        FACTIONS[fac["id"]] = fac
        _register("faction", fac["id"], [fac.get("name")] + _as_list(fac.get("aliases")), fpath.name)

    # NPCs: any number of files, each a list.
    for path in sorted((root / "npcs").glob("*.yml")):
        for npc in _as_list(_load(path)):
            npc.setdefault("id", slug(npc.get("name", "")))
            npc["_order"] = len(NPCS)
            _check_required("npc", npc, path.name)
            if npc["id"] in NPCS:
                log.warning("Duplicate NPC id '%s' in %s", npc["id"], path.name)
            NPCS[npc["id"]] = npc
            _register("npc", npc["id"], [npc.get("name")] + _as_list(npc.get("aliases")), path.name)

    # Items: any number of files, each a list.
    for path in sorted((root / "items").glob("*.yml")):
        for item in _as_list(_load(path)):
            item.setdefault("id", slug(item.get("name", "")))
            _check_required("item", item, path.name)
            ITEMS[item["id"]] = item
            _register("item", item["id"], [item.get("name")] + _as_list(item.get("aliases")), path.name)

    # Creatures (from the Bestiary data) - hover cards only. An NPC that has a
    # stat block claims the name, so [[Captain Oren Hask]] shows the NPC card, not the creature's.
    claimed = {n.get("statblock") for n in NPCS.values() if n.get("statblock")}
    # Duplicates the encounter builder hides (tools/import_monsters.py dedup) never take a name, so
    # [[Spy]] means the copy the builder shows.
    dedup = root / "monsters-dedup.yml"
    hidden = set(((_load(dedup) or {}).get("hidden") or {}) if dedup.is_file() else [])
    for path in sorted(list((root / "monsters").glob("*.yml")) + list((root / "monsters").glob("*.json"))):
        data = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else _load(path)
        if isinstance(data, dict) and "creatures" in data:
            data = data["creatures"]
        for mon in _as_list(data):
            mid = str(mon.get("id") or path.stem)
            mon["id"] = mid
            CREATURES[mid] = mon
            # (an imported creature an NPC uses - a Veteran, say - keeps its own name: the NPC has another)
            if (mid in claimed and not mon.get("source")) or mid in hidden:
                continue
            # Imported creatures never override a name your own data already uses.
            if mon.get("source") and key(str(mon.get("name", ""))) in REGISTRY:
                continue
            _register("creature", mid, [mon.get("name")], path.name)

    # The rules encyclopedia (data/rules/srd.json): conditions, spells, and the SRD's magic items get
    # hover cards too - but never take a name your own data already uses.
    codex_rules.load(root.parent)
    for kind, table in (("condition", "_conditions"), ("spell", "_spells"), ("srditem", "_items")):
        for rid, entry in codex_rules.DATA.get(table, {}).items():
            if key(entry["name"]) not in REGISTRY:
                REGISTRY[key(entry["name"])] = (kind, rid)

    _check_references()
    _check_similar_names()
    log.info("Entities: %d NPCs, %d locations, %d factions, %d items",
             len(NPCS), len(LOCATIONS), len(FACTIONS), len(ITEMS))

    PLAYERS[0] = (config.get("extra") or {}).get("audience") == "players"
    REVEALED.clear()
    # Worked out on both sites: the player site shows only this; the DM's Items page says, per item,
    # whether players see it.
    _find_revealed(root, Path(config["docs_dir"]))
    return config


# The Session Log as the players read it: without <!-- players: hide --> stretches or DM boxes
# (their marker line and everything indented under it), with <!-- players: show --> text in.
_HIDE = re.compile(r"<!--\s*players:\s*hide\s*-->.*?<!--\s*players:\s*end\s*-->", re.S)
_SHOW = re.compile(r"<!--\s*players:\s*show[ \t]*\n(.*?)-->", re.S)
_DM_BOX = re.compile(r"^(\s*)(\?\?\?\+?|!!!)\s+(dm|warning)\b")


def _public_text(text: str) -> str:
    text = _SHOW.sub(lambda m: m.group(1), _HIDE.sub("", text))
    out, skipping, indent = [], False, 0
    for line in text.split("\n"):
        if skipping:
            if not line.strip() or len(line) - len(line.lstrip()) > indent:
                continue
            skipping = False
        m = _DM_BOX.match(line)
        if m:
            skipping, indent = True, len(m.group(1))
            continue
        out.append(line)
    return "\n".join(out)


def _find_revealed(data_root: Path, docs: Path):
    """What the players have come across: Session Log mentions, then revealed: flags and
    data/revealed.yml, with revealed: false / hide: taking anything back out."""
    log_page = docs / "session-log.md"
    if log_page.is_file():
        # only what the players can read counts - a name in a DM note isn't something they've met
        for m in MENTION.finditer(_public_text(log_page.read_text(encoding="utf-8"))):
            hit = _resolve(m.group(1).strip())
            if hit and hit[0] != "creature":
                REVEALED.add(hit)
    tables = {"npc": NPCS, "location": LOCATIONS, "faction": FACTIONS, "item": ITEMS}
    for kind, table in tables.items():
        for eid, entry in table.items():
            if entry.get("revealed") is True:
                REVEALED.add((kind, eid))
    for eid, item in ITEMS.items():   # an item someone in the party carries, they know about
        if item.get("holder"):
            REVEALED.add(("item", eid))
    extra = _load(data_root / "revealed.yml") if (data_root / "revealed.yml").is_file() else None
    for name in (extra or {}).get("reveal") or []:
        hit = _resolve(str(name))
        if hit and hit[0] != "creature":
            REVEALED.add(hit)
        elif not hit:
            log.warning("revealed.yml: '%s' doesn't match anything", name)
    for kind, table in tables.items():
        for eid, entry in table.items():
            if entry.get("revealed") is False:
                REVEALED.discard((kind, eid))
    for name in (extra or {}).get("hide") or []:
        hit = _resolve(str(name))
        if hit:
            REVEALED.discard(hit)
    counts = {k: sum(1 for kind, _ in REVEALED if kind == k) for k in tables}
    log.info("Player site shows: %d of %d NPCs, %d of %d locations, %d of %d factions, %d of %d items",
             counts["npc"], len(NPCS), counts["location"], len(LOCATIONS), counts["faction"], len(FACTIONS),
             counts["item"], len(ITEMS))


def _npc_location(n: dict):
    """Where an NPC is. On the player site, player_location replaces it when set - an empty one
    means the party doesn't know (a captive, someone in hiding)."""
    if PLAYERS[0] and "player_location" in n:
        return n["player_location"] or None
    return n.get("location")


def _player_text(entry: dict, field: str):
    """On the player site, player_hook / player_description replace hook / description when set -
    for entries whose usual text was written from the DM's side of the screen."""
    if PLAYERS[0] and entry.get(f"player_{field}"):
        return entry[f"player_{field}"]
    return entry.get(field)


def visible(kind: str, eid) -> bool:
    """Everything shows on the DM site; on the player site, only what's been revealed."""
    if not PLAYERS[0] or kind in RULE_KINDS:   # the rules are no secret
        return True
    return kind != "creature" and (kind, eid) in REVEALED


def _check_references():
    for npc in NPCS.values():
        if npc.get("location") and npc["location"] not in LOCATIONS:
            log.warning("NPC '%s': location '%s' doesn't exist", npc["name"], npc["location"])
        for fid in _as_list(npc.get("faction")):
            if fid not in FACTIONS:
                log.warning("NPC '%s': faction '%s' doesn't exist", npc["name"], fid)
        if npc.get("statblock") and npc["statblock"] not in CREATURES:
            log.warning("NPC '%s': stat block '%s' doesn't exist", npc["name"], npc["statblock"])
    for fac in FACTIONS.values():
        if fac.get("leader") and fac["leader"] not in NPCS:
            log.warning("Faction '%s': leader '%s' isn't an NPC", fac["name"], fac["leader"])


TITLES = ("Lady", "Lord", "Sir", "Captain", "Sergeant", "Brother", "Sister", "Old", "Governor",
          "Harbormaster", "Dockmaster", "Foreman", "Shrinekeeper", "Consul", "Watchman", "Archmage",
          "High", "Priestess", "Justicar", "Knight-Lieutenant", "Inquisitor", "Chancellor", "King",
          "Queen", "Prince", "Princess", "Magister", "Warden", "Master", "Grand", "Vizier", "Sentinel",
          "Court", "Chronicler", "Market", "Overseer", "Forge-Master", "Trader", "Madame", "Windcaller",
          "Acolyte", "Lieutenant", "Elder", "Banker", "Quartermaster")


def _sort_name(name: str) -> str:
    """The name without leading titles: 'Captain Oren Hask' -> 'oren hask'."""
    words = name.split()
    while len(words) > 1 and words[0] in TITLES:
        words = words[1:]
    return " ".join(words).lower()


def _name_parts(name: str):
    """(given, surname or None) from a name, ignoring titles, quotes and nicknames."""
    plain = re.sub(r'"[^"]*"', " ", _sort_name(name)).replace("’", "'")
    words = [w for w in re.split(r"\s+", plain) if w]
    if not words:
        return "", None
    return words[0], (words[-1] if len(words) > 1 else None)


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _check_similar_names():
    """Warn about names likely to be confused at the table. Shared surnames are fine
    (families); flagged: the same word used as a first name in one and any part of the
    other, very close first names, and near-identical (but different) surnames."""
    people = [(n["id"], _name_parts(n["name"])) for n in NPCS.values() if n.get("name")]
    for i, (aid, (ag, asur)) in enumerate(people):
        for bid, (bg, bsur) in people[i + 1:]:
            if frozenset((aid, bid)) in ALLOW_SIMILAR:
                continue
            a_all, b_all = {ag, asur} - {None}, {bg, bsur} - {None}
            reason = None
            if ag == bg or ag in b_all or bg in a_all:
                reason = "share a name"
            elif _similar(ag, bg) > 0.8:
                reason = "have near-identical first names"
            elif asur and bsur and asur != bsur and _similar(asur, bsur) >= 0.85:
                reason = "have near-identical surnames"
            elif (asur is None or bsur is None) and any(_similar(x, y) >= 0.85 for x in a_all for y in b_all):
                reason = "sound alike"
            if reason:
                log.warning("Similar NPC names: '%s' and '%s' %s (allow in data/checks.yml if intended)",
                            NPCS[aid]["name"], NPCS[bid]["name"], reason)


# ---------------------------------------------------------------- hover cards (HTML)

def _npc_card(n: dict) -> str:
    lid = _npc_location(n)
    where = _loc_name(lid, n.get("role")) if visible("location", lid) else None
    meta = " · ".join(html.escape(str(x)) for x in [n.get("race"), n.get("role"), where] if x)
    parts = [f'<div class="rc-title">{html.escape(n["name"])}</div>']
    if meta:
        parts.append(f'<div class="rc-meta">{meta}</div>')
    hook = _player_text(n, "hook")
    if hook:
        parts.append(f'<div class="rc-body">{mdinline(hook)}</div>')
    if n.get("personality"):
        parts.append(f'<div class="rc-body"><b>Personality:</b> {mdinline(n["personality"])}</div>')
    return "".join(parts)


def _loc_name(lid, role=None):
    """The NPC's location name - unless their role already names it."""
    if lid not in LOCATIONS:
        return None
    name = LOCATIONS[lid]["name"]
    if role and key(name) in key(str(role)):
        return None
    return name


def _location_card(loc: dict) -> str:
    parts = [f'<div class="rc-title">{html.escape(loc["name"])}</div>']
    if loc.get("subtitle"):
        parts.append(f'<div class="rc-meta">{html.escape(loc["subtitle"])}</div>')
    sentences = re.split(r"(?<=[.!?])\s+", str(_player_text(loc, "description") or "").strip())
    parts.append(f'<div class="rc-body">{mdinline(" ".join(sentences[:2]))}</div>')
    return "".join(parts)


def _faction_card(fac: dict) -> str:
    return (f'<div class="rc-title">{html.escape(fac["name"])}</div>'
            f'<div class="rc-body">{mdinline(fac.get("summary", ""))}</div>')


def _item_subtitle(item: dict) -> str:
    sub = f"{item.get('type', '')}, {item.get('rarity', '')}"
    extras = []
    att = item.get("attunement")
    if att:
        extras.append("requires attunement" if att is True else f"requires attunement {att}")
    if item.get("cursed"):
        extras.append("cursed")
    if item.get("sentient"):
        extras.append("sentient")
    return sub + (f" ({', '.join(extras)})" if extras else "")


def _item_card(item: dict) -> str:
    return (f'<div class="rc-title">{html.escape(item["name"])}</div>'
            f'<div class="rc-meta">{html.escape(_item_subtitle(item))}</div>'
            f'<div class="rc-body rc-scroll">{mdhtml(item.get("text", ""))}</div>')


def _condition_card(slug: str) -> str:
    c = codex_rules.DATA["_conditions"][slug]
    return (f'<div class="rc-title">{html.escape(c["name"])}</div><div class="rc-meta">Condition</div>'
            f'<div class="rc-body">{mdhtml(c["text"])}</div>')


def _spell_card(slug: str) -> str:
    sp = codex_rules.DATA["_spells"][slug]
    facts = " · ".join(x for x in (sp.get("casting_time"), sp.get("range"), sp.get("components"),
                                    codex_rules.duration(sp)) if x)
    body = mdhtml(sp["text"]) + (mdhtml("**At higher levels.** " + sp["higher_level"]) if sp.get("higher_level") else "")
    return (f'<div class="rc-title">{html.escape(sp["name"])}</div>'
            f'<div class="rc-meta">{html.escape(codex_rules.level_line(sp))} · {html.escape(", ".join(sp.get("classes", [])))}</div>'
            f'<div class="rc-meta">{html.escape(facts)}</div><div class="rc-body rc-scroll">{body}</div>')


def _srditem_card(slug: str) -> str:
    it = codex_rules.DATA["_items"][slug]
    return (f'<div class="rc-title">{html.escape(it["name"])}</div>'
            f'<div class="rc-meta">{html.escape(codex_rules.item_line(it))}</div>'
            f'<div class="rc-body rc-scroll">{mdhtml(it["text"])}</div>')


def _creature_card(m: dict) -> str:
    stats = " · ".join(x for x in [
        f"AC {m['ac']}" if m.get("ac") is not None else "",
        f"HP {m['hp']}" if m.get("hp") is not None else "",
        str(m.get("speed", "")),
        f"CR {m.get('cr', '?')}",
    ] if x)
    parts = [f'<div class="rc-title">{html.escape(m.get("name", m["id"]))}</div>',
             f'<div class="rc-meta">{html.escape(stats)}</div>']
    for section in ("actions", "bonus_actions", "reactions"):
        for a in m.get(section) or []:
            text = " ".join(str(a.get("text", "")).split())
            if len(text) > 150:
                text = text[:147].rsplit(" ", 1)[0] + "…"
            parts.append(f'<div class="rc-line"><b>{html.escape(a["name"])}.</b> {mdinline(text)}</div>')
    if m.get("note") and m.get("ac") is None:
        parts.append(f'<div class="rc-body">{mdinline(m["note"])}</div>')
    return "".join(parts)


def _target(kind: str, eid: str):
    """(page, anchor) where the full entry lives."""
    if kind == "npc":
        return NPC_PAGE, f"npc-{eid}"
    if kind == "location":
        city = CITIES.get(LOCATIONS[eid]["_city"], {})
        return city.get("page", ""), f"loc-{eid}"
    if kind == "faction":
        return FACTION_PAGE, f"faction-{eid}"
    if kind == "item":
        return ITEM_PAGE, f"item-{eid}"
    if kind in RULE_KINDS:
        return codex_rules.PAGES[kind], codex_rules.ANCHOR[kind] + eid
    return BESTIARY_PAGE, f"monster-{eid}"


def _card(kind: str, eid: str) -> str:
    return {"npc": lambda: _npc_card(NPCS[eid]),
            "location": lambda: _location_card(LOCATIONS[eid]),
            "faction": lambda: _faction_card(FACTIONS[eid]),
            "item": lambda: _item_card(ITEMS[eid]),
            "creature": lambda: _creature_card(CREATURES[eid]),
            "condition": lambda: _condition_card(eid),
            "spell": lambda: _spell_card(eid),
            "srditem": lambda: _srditem_card(eid)}[kind]()


# ---------------------------------------------------------------- mentions

def _resolve(name: str):
    return REGISTRY.get(key(name))


def _mention_html(kind, eid, text, page_src) -> str:
    # A regular Markdown link (not raw HTML), so MkDocs rewrites it to .html and
    # validates that the target page and anchor exist.
    if kind == "creature" and CREATURES[eid].get("source"):
        # Imported creatures (SRD, the books) aren't on the Bestiary page: the name shows their stat
        # card on hover, and goes nowhere on click.
        return (f'<a class="ref ref-{kind}" data-ref="{kind}:{eid}" tabindex="0">'
                f'{html.escape(text, quote=False)}</a>')
    page, anchor = _target(kind, eid)
    href = f"{rel(page_src, page)}#{anchor}" if page else f"#{anchor}"
    label = text.replace("[", "(").replace("]", ")")
    return f'[{label}]({href}){{ .ref .ref-{kind} data-ref="{kind}:{eid}" }}'


def _process_mentions(markdown: str, page) -> tuple:
    """Replace [[mentions]]. Returns (markdown, set of (kind, id) linked on the page)."""
    used = set()
    seen = set()          # (kind, id) already linked in the current ## section
    in_readaloud = False
    fence = False
    out = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            fence = not fence
        if line.startswith("## "):
            seen = set()
        if re.match(r"^(!!!|\?\?\?\+?)\s+read-aloud\b", stripped):
            in_readaloud = True
        elif in_readaloud and line and not line.startswith((" ", "\t")):
            in_readaloud = False
        plain = fence or in_readaloud or line.lstrip().startswith("#")

        def replace(m):
            name, display = m.group(1).strip(), (m.group(2) or m.group(1)).strip()
            if plain:
                return display
            hit = _resolve(name)
            if not hit:
                log.warning("Unknown mention [[%s]] in %s", name, page.file.src_uri)
                return f'<span class="ref-missing" title="Unknown: {html.escape(name)}">{display}</span>'
            if not visible(*hit):
                return display   # player site: not come across yet - just the words, no link or card
            if hit in seen:
                return display
            seen.add(hit)
            used.add(hit)
            return _mention_html(hit[0], hit[1], display, page.file.src_uri)

        # Inline `code` shows [[mention]] syntax as-is; only text outside it is processed.
        parts = re.split(r"(`[^`]*`)", line)
        out.append("".join(p if p.startswith("`") else MENTION.sub(replace, p) for p in parts))
    return "\n".join(out), used


# ---------------------------------------------------------------- page renderers

def _npc_entry(n: dict, page_src: str) -> str:
    players = PLAYERS[0]
    lines = [f"#### {n['name']} {{ #npc-{n['id']} .npc-name }}", ""]
    meta = [n.get("race"), n.get("role")]
    lid = _npc_location(n)
    if _loc_name(lid, n.get("role")) and visible("location", lid):
        meta.append(f"[[{LOCATIONS[lid]['name']}]]")
    for fid in _as_list(n.get("faction")):
        if fid in FACTIONS and visible("faction", fid):   # players don't learn a faction from a name tag
            meta.append(f"[[{FACTIONS[fid]['name']}]]")
    line = "*" + " · ".join(str(x) for x in meta if x) + "*"
    status = n.get("status", "alive")
    if status != "alive" and not players:
        line += f' <span class="npc-status">{html.escape(status.capitalize())}</span>'
    lines += [line, ""]
    hook = _player_text(n, "description") or _player_text(n, "hook")   # the longer write-up, when there is one
    if hook:
        lines += [str(hook).strip(), ""]
    fields = [("Appearance", "appearance"), ("Personality", "personality")] + ([] if players else [("Notes", "notes")])
    details = [(label, n.get(field)) for label, field in fields]
    details = [d for d in details if d[1]]
    if details:
        lines += [f"- **{label}:** {' '.join(str(value).split())}" for label, value in details] + [""]
    if players:
        return "\n".join(lines)   # no stat block link, no secret
    sb = CREATURES.get(n.get("statblock"))
    if sb and not sb.get("source"):   # your own creatures are on the Bestiary page
        lines += [f"[Stat block]({rel(page_src, BESTIARY_PAGE)}#monster-{n['statblock']})", ""]
    elif sb:                           # an imported one (the SRD...) isn't - name it, with its hover card
        lines += [f"**Stat block:** [[{sb.get('name', n['statblock'])}]]", ""]
    if n.get("secret"):
        lines += ['??? dm "DM only"', ""] + ["    " + l for l in str(n["secret"]).strip().split("\n")] + [""]
    return "\n".join(lines)


def _grouped(region=None):
    """{region: {group: [npcs]}} in data-file order."""
    regions = {}
    for n in sorted(NPCS.values(), key=lambda x: x["_order"]):
        r = n.get("region", "Other")
        if region and slug(r) != region or not visible("npc", n["id"]):
            continue
        regions.setdefault(r, {}).setdefault(n.get("group", "Others"), []).append(n)
    return regions


def render_npc_index(page_src: str) -> str:
    out = []
    for region, groups in _grouped().items():
        out += [f"## {region}", ""]
        for group, people in groups.items():
            out += [f"### {group} {{ .npc-group }}", ""]
            for n in people:
                out.append(_npc_entry(n, page_src))
    return "\n".join(out)


def render_npc_list(region: str, page_src: str) -> str:
    regions = _grouped(region)
    if not regions:
        if PLAYERS[0]:
            return "*Nobody here yet - people the party meets are added as the Session Log records them.*\n"
        log.warning("No NPCs with region '%s' for {{ npc-list }}", region)
        return ""
    out = []
    for groups in regions.values():
        for group, people in groups.items():
            out += [f"## {group}", ""]
            for n in people:
                status = n.get("status", "alive")
                tag = f" *({status})*" if status != "alive" and not PLAYERS[0] else ""
                out.append(f"- [[{n['name']}]] — {n.get('role', '')}{tag}")
            out.append("")
    return "\n".join(out)


def render_locations(city_id: str, page_src: str) -> str:
    city = CITIES.get(city_id)
    if not city:
        log.warning("Unknown city '%s' in {{ locations }}", city_id)
        return f'!!! failure "Missing city"\n    No file `data/locations/{city_id}.yml`.\n'
    out = []
    for district in city.get("districts", []):
        shown = [loc for loc in district.get("locations", []) if visible("location", loc["id"])]
        if not shown:
            continue   # player site: nowhere in this district come across yet
        out += [f"## {district['name']}", ""]
        blurb = str(district.get("blurb") or "").strip()
        if blurb:
            # A one-line blurb is an italic tagline; a longer one is ordinary paragraphs.
            out += [blurb if "\n" in blurb else f"*{blurb}*", ""]
        for loc in shown:
            num = f"{loc['number']} — " if loc.get("number") is not None else ""
            out += [f"### {num}{loc['name']} {{ #loc-{loc['id']} }}", ""]
            if loc.get("subtitle"):
                out += [f"*{loc['subtitle']}*", ""]
            out += [str(_player_text(loc, "description") or "").strip(), ""]
            for feat in _as_list(loc.get("features")):
                out.append(f"- {' '.join(str(feat).split())}")
            if loc.get("features"):
                out.append("")
            for sec in _as_list(loc.get("sections")):
                out += [f"#### {sec['title']} {{ .loc-section }}", "", str(sec.get("text", "")).strip(), ""]
            people = [n for n in NPCS.values() if _npc_location(n) == loc["id"] and visible("npc", n["id"])]
            if people:
                out += ["**Found here:**", ""]
                out += [f"- [[{n['name']}]] — {n.get('role', '')}" for n in people] + [""]
            if PLAYERS[0]:
                continue   # no DM notes or secrets
            if loc.get("dm_notes"):
                out += ['??? dm "DM notes"', ""] + ["    " + l for l in str(loc["dm_notes"]).strip().split("\n")] + [""]
            if loc.get("secret"):
                out += ['??? dm "DM only"', ""] + ["    " + l for l in str(loc["secret"]).strip().split("\n")] + [""]
    return "\n".join(out)


NL = "\n"


def render_factions(page_src: str, city: str = "") -> str:
    """{{ factions }}: every faction, grouped by region (campaign.yml's default_region if none). {{ factions greywater }}:
    just that city's, for its own Factions page."""
    out = []
    regions = {}   # in file order
    for fac in FACTIONS.values():
        if visible("faction", fac["id"]):
            regions.setdefault(str(fac.get("region") or SETTINGS[0]["default_region"]), []).append(fac)
    if city:
        facs = regions.get(next((r for r in regions if slug(r) == city), ""), [])
        if not facs:
            return ("*None yet - they're added as the party comes across them.*" if PLAYERS[0]
                    else f"*No factions with region: {city} in data/factions.yml yet.*") + NL
        for fac in facs:
            out += _faction_entry(fac, "##")
        return NL.join(out)
    for region, facs in regions.items():
        out += [f"## {region} {{ #{slug(region)} }}", ""]
        for fac in facs:
            out += _faction_entry(fac)
    return "\n".join(out)


def _faction_entry(fac: dict, level: str = "###") -> list:
    out = [f"{level} {fac['name']} {{ #faction-{fac['id']} }}", ""]
    out += [str(fac.get("summary", "")).strip(), ""]
    # Players get the summary and the members they've met; structure, goals and details
    # can hold what the party doesn't know yet.
    for label, field in ([] if PLAYERS[0] else [("Structure", "structure"), ("Goals", "goals")]):
        if fac.get(field):
            out += [f"**{label}:** {' '.join(str(fac[field]).split())}", ""]
    if fac.get("details") and not PLAYERS[0]:
        out += [str(fac["details"]).strip(), ""]
    members = [n for n in NPCS.values() if fac["id"] in _as_list(n.get("faction")) and visible("npc", n["id"])]
    if members:
        leader = fac.get("leader")
        out += ["**Members:**", ""]
        for n in sorted(members, key=lambda x: (x["id"] != leader, _sort_name(x["name"]))):
            tag = " *(leader)*" if n["id"] == leader else ""
            out.append(f"- [[{n['name']}]] — {n.get('role', '')}{tag}")
        out.append("")
    if fac.get("secret") and not PLAYERS[0]:
        out += ['??? dm "DM only"', ""] + ["    " + l for l in str(fac["secret"]).strip().split("\n")] + [""]
    return out


def render_items(page_src: str) -> str:
    groups = {}
    for item in ITEMS.values():
        if visible("item", item["id"]):
            groups.setdefault(item.get("group", "Other"), []).append(item)
    if not groups and PLAYERS[0]:
        return "*No items yet - they're added as the Session Log records them.*\n"
    # On the DM site at home, javascripts/items-editor.js turns these into the Held by pickers and
    # the list of pickups found in session transcripts.
    out = [] if PLAYERS[0] else ['<div class="item-suggest"></div>', ""]
    party = _party_names()
    # Found but nobody's yet (holder: Unclaimed). On the players' site, players/items-live.js adds
    # "Claim" to each; on the DM's site at home, items-editor.js lists the claims to approve.
    grabs = [i for i in ITEMS.values() if str(i.get("holder") or "").strip().lower() == "unclaimed"
             and visible("item", i["id"])]
    if grabs:
        out += ["## Up for grabs", "",
                "Found, and nobody has claimed them yet." +
                (" Claim one for your character - the DM decides who gets it." if PLAYERS[0] else ""), ""]
        out += [f'- [[{i["name"]}]] <span class="item-claim" data-item="{html.escape(i["id"])}"></span>' for i in grabs]
        out.append("")
    if not PLAYERS[0]:
        out += ['<div class="item-claims"></div>', ""]
    for group, items in groups.items():
        out += [f"## {group}", ""]
        for item in items:
            out += [f"### {item['name']} {{ #item-{item['id']} .entry-name }}", ""]
            sub = f"*{_item_subtitle(item)}*"
            if item.get("found"):
                sub += f" — {item['found']}"
            out += [sub, ""]
            if item.get("flavor"):
                out += [str(item["flavor"]).strip(), ""]
            out += [str(item.get("text", "")).strip(), ""]
            if item.get("also"):
                out += [str(item["also"]).strip(), ""]
            if item.get("holder"):
                out += [f"**Held by:** {_holder_link(item['holder'], party, page_src)}", ""]
            if not PLAYERS[0]:
                # items-editor.js: the Held by and Players' site pickers. data-reveal: this item's own
                # setting (revealed: true/false, or auto); data-shown: whether the player site shows it now.
                setting = {True: "show", False: "hide"}.get(item.get("revealed"), "auto")
                shown = "1" if ("item", item["id"]) in REVEALED else "0"
                why = ("someone carries it" if item.get("holder") else "the Session Log or revealed.yml mentions it") \
                    if shown == "1" else "the Session Log doesn't mention it yet"
                out += [f'<div class="item-hold" data-item="{html.escape(item["id"])}" data-reveal="{setting}" '
                        f'data-shown="{shown}" data-why="{html.escape(why)}"></div>', ""]
    return "\n".join(out)


def _party_names() -> dict:
    """{lowercased character name: card anchor} from data/party.yml."""
    path = Path(DATA_ROOT[0]) / "party.yml" if DATA_ROOT[0] else None
    members = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("members") if path and path.is_file() else []
    out = {}
    for p in members or []:
        if isinstance(p, dict) and p.get("character"):
            name = str(p["character"])
            out[name.lower()] = (name, re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-"))
    return out


def _holder_link(holder, party: dict, page_src: str) -> str:
    holder = str(holder).strip()
    if holder.lower() == "party":
        return "the party (shared)"
    if holder.lower() == "unclaimed":
        return "nobody yet - up for grabs"
    if holder.lower() in party:
        name, anchor = party[holder.lower()]
        return f"[{name}]({posixpath.relpath('party/index.md', posixpath.dirname(page_src) or '.')}#pc-{anchor})"
    return holder


# ---------------------------------------------------------------- MkDocs events

def on_page_markdown(markdown, page, config, files, **kwargs):
    src = page.file.src_uri

    if "house-rules" not in src:
        for word in SETTINGS[0].get("banned") or []:
            if re.search(r"\b" + re.escape(str(word)) + r"\b", markdown, re.I):
                log.warning("'%s' mentions %s, which campaign.yml lists as banned", src, word)

    def render(match):
        indent, kind, arg = match.groups()
        text = {"npc-index": lambda: render_npc_index(src),
                "npc-list": lambda: render_npc_list(arg, src),
                "locations": lambda: render_locations(arg, src),
                "factions": lambda: render_factions(src, arg),
                "items": lambda: render_items(src)}[kind]()
        return "\n".join(indent + l if l else l for l in text.split("\n"))

    markdown = MARKER.sub(render, markdown)
    # The DM's Party page: which items the players can see, so "Give an item" (items-editor.js) only
    # offers those - hidden ones are given from the Items page, if at all.
    if not PLAYERS[0] and '<div class="pc-cards"' in markdown:
        ids = " ".join(sorted(eid for kind, eid in REVEALED if kind == "item"))
        markdown += f'\n\n<div class="items-visible" hidden data-ids="{html.escape(ids)}"></div>\n'
    markdown, used = _process_mentions(markdown, page)
    page.meta["_refs"] = sorted(used)
    return markdown


def on_page_content(html_out, page, config, files, **kwargs):
    # Hover-card data for this page, read by javascripts/refs.js.
    refs = page.meta.get("_refs") or []
    if refs:
        data = {f"{k}:{i}": _card(k, i) for k, i in refs}
        html_out += ('<script type="application/json" id="ref-data">'
                     + json.dumps(data).replace("</", "<\\/") + "</script>")

    # Optional per-page table-of-contents depth.
    depth = page.meta.get("toc_depth")
    if depth and page.toc:
        def prune(items):
            for item in items:
                if item.level >= int(depth):
                    item.children = []
                else:
                    prune(item.children)
        prune(page.toc.items if hasattr(page.toc, "items") else page.toc)
    return html_out


# ---------------------------------------------------------------- cache busting

def on_post_page(output, page, config, **kwargs):
    """Stamp our stylesheet and script links with a content fingerprint, so browsers
    fetch the new version whenever they change instead of using a cached copy."""
    import hashlib
    docs = Path(config["docs_dir"])
    for rel_path in ("stylesheets/extra.css", "javascripts/refs.js", "javascripts/encounter-builder.js"):
        f = docs / rel_path
        if f.is_file():
            v = hashlib.md5(f.read_bytes()).hexdigest()[:8]
            output = re.sub(r'(%s)(["\'])' % re.escape(rel_path), rf"\1?v={v}\2", output)
    return output
