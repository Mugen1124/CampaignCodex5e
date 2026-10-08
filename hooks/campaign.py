"""
Campaign data hook for MkDocs.

Creatures and encounters live as YAML files under data/. Pages pull them in
with short markers, which this hook replaces with rendered Markdown before
the page is built:

    {{ statblock bog-lurker }}    one full stat block
    {{ bestiary }}                every creature, grouped, with link anchors
    {{ encounter dock-ambush }}   encounter summary with automatic XP math
    {{ party-cards }}             a card for each character in data/party.yml
    {{ party-card kestrel }}      one character's card (named as in its anchor: pc-kestrel)

Keeping the numbers as data (not prose) is what lets future table tools
(initiative tracker, stat cards, encounter builder) reuse them.
"""

import json
import logging
import posixpath
import re
from pathlib import Path

import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex import settings as codex_settings  # noqa: E402
from codex import rules as codex_rules  # noqa: E402

CAMPAIGN_SLUG = ["campaign"]   # campaign.yml's name, as a slug - set in on_config

log = logging.getLogger("mkdocs.hooks.campaign")

MONSTERS = {}
MONSTER_FILES = {}   # creature id -> the file it came from
DEDUP_HIDDEN = {}    # duplicate creature id -> the copy the builder shows (data/monsters-dedup.yml)
CUSTOM_FILE = "custom.yml"   # creatures made with the builder's New creature form (tools/site_helper.py)
ENCOUNTERS = {}
PARTY = {}
ITEMS_HELD = []    # [{id, name, holder}] from data/items/ - for the "Carrying" line on character cards
FAMILIES = []   # data/families.yml, with names resolved to creature ids
DOCS_DIR = [None]  # set in on_config; used to find which pages show each encounter
PLAYERS = [False]  # the player site (mkdocs-players.yml): no stat blocks, encounters, or DM notes

ENCOUNTER_PAGE = "encounters/index.md"   # the encounters page (list, archive, builder)

BESTIARY_PAGE = "reference/bestiary.md"

# Markers sit alone on their own line. They may be indented (inside a tab or a
# collapsible box); the rendered output is indented to match. To show a marker
# as an example without rendering it, put it in inline code: `{{ statblock x }}`.
MARKER = re.compile(
    r"^([ \t]*)\{\{\s*(statblock|encounters|encounter-builder|encounter|bestiary|party-cards|party-card)\b\s*([A-Za-z0-9_-]*)\s*\}\}[ \t]*$",
    re.MULTILINE,
)

# ---------------------------------------------------------------- reference tables (2014 DMG)

CR_XP = {
    "0": 10, "1/8": 25, "1/4": 50, "1/2": 100,
    "1": 200, "2": 450, "3": 700, "4": 1100, "5": 1800, "6": 2300, "7": 2900,
    "8": 3900, "9": 5000, "10": 5900, "11": 7200, "12": 8400, "13": 10000,
    "14": 11500, "15": 13000, "16": 15000, "17": 18000, "18": 20000,
    "19": 22000, "20": 25000, "21": 33000, "22": 41000, "23": 50000,
    "24": 62000, "25": 75000, "26": 90000, "27": 105000, "28": 120000,
    "29": 135000, "30": 155000,
}

# per-character XP thresholds: easy, medium, hard, deadly
THRESHOLDS = {
    1: (25, 50, 75, 100), 2: (50, 100, 150, 200), 3: (75, 150, 225, 400),
    4: (125, 250, 375, 500), 5: (250, 500, 750, 1100), 6: (300, 600, 900, 1400),
    7: (350, 750, 1100, 1700), 8: (450, 900, 1400, 2100), 9: (550, 1100, 1600, 2400),
    10: (600, 1200, 1900, 2800), 11: (800, 1600, 2400, 3600), 12: (1000, 2000, 3000, 4500),
    13: (1100, 2200, 3400, 5100), 14: (1250, 2500, 3800, 5700), 15: (1400, 2800, 4300, 6400),
    16: (1600, 3200, 4800, 7200), 17: (2000, 3900, 5900, 8800), 18: (2100, 4200, 6300, 9500),
    19: (2400, 4900, 7300, 10900), 20: (2800, 5700, 8500, 12700),
}

# encounter multiplier steps; party-size adjustment moves one step either way
MULTIPLIERS = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5]

ABILITIES = ["str", "dex", "con", "int", "wis", "cha"]


# ---------------------------------------------------------------- loading

def _load_yaml_dir(folder: Path, files: dict = None) -> dict:
    """{id: entry} from every .yml/.json in folder; `files`, if given, gets {id: file name}."""
    items = {}
    if not folder.is_dir():
        return items
    for path in sorted(list(folder.glob("*.yml")) + list(folder.glob("*.json"))):
        try:
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, ValueError) as err:
            log.warning("Could not read %s: %s", path.name, err)
            continue
        # Imported files (tools/import_monsters.py) wrap their creatures in {"creatures": [...]}.
        # (An encounter also has a "creatures" list, but it has its own id - leave those alone.)
        if isinstance(data, dict) and "creatures" in data and "id" not in data:
            data = data["creatures"]
        # A file holds one entry, or a list of entries (e.g. a whole arc's creatures).
        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("id") or path.stem)
            if key in items:
                log.warning("Duplicate id '%s' in %s", key, path.name)
            entry["id"] = key
            items[key] = entry
            if files is not None:
                files[key] = path.name
    return items


def on_config(config, **kwargs):
    root = Path(config.config_file_path).parent / "data"
    CAMPAIGN_SLUG[0] = codex_settings.load(root.parent)["slug"]
    codex_rules.load(root.parent)
    MONSTERS.clear()
    MONSTER_FILES.clear()
    MONSTERS.update(_load_yaml_dir(root / "monsters", MONSTER_FILES))
    DEDUP_HIDDEN.clear()
    dedup_file = root / "monsters-dedup.yml"
    if dedup_file.is_file():
        DEDUP_HIDDEN.update((yaml.safe_load(dedup_file.read_text(encoding="utf-8")) or {}).get("hidden") or {})
    ENCOUNTERS.clear()
    ENCOUNTERS.update(_load_yaml_dir(root / "encounters"))
    PARTY.clear()
    party_file = root / "party.yml"
    if party_file.is_file():
        PARTY.update(yaml.safe_load(party_file.read_text(encoding="utf-8")) or {})
    FAMILIES.clear()
    FAMILIES.extend(_load_families(root / "families.yml"))
    ITEMS_HELD.clear()
    ITEMS_HELD.extend(_load_held_items(root / "items"))
    DOCS_DIR[0] = Path(config["docs_dir"])
    PLAYERS[0] = (config.get("extra") or {}).get("audience") == "players"
    log.info("Campaign data: %d creatures, %d encounters, %d families",
             len(MONSTERS), len(ENCOUNTERS), len(FAMILIES))
    return config


def _item_slug(text: str) -> str:   # the same ids hooks/entities.py gives items
    s = re.sub(r"[^\w\s-]", "", str(text).lower().replace("’", "").replace("'", ""))
    return re.sub(r"[\s_]+", "-", s).strip("-")


def _load_held_items(folder: Path) -> list:
    """Items with a holder: the character's name (as in party.yml), or "Party" for shared loot."""
    held = []
    characters = {str(p.get("character", "")).lower() for p in PARTY.get("members") or [] if isinstance(p, dict)}
    for path in sorted(folder.glob("*.yml")) if folder.is_dir() else []:
        for item in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            if not isinstance(item, dict) or not item.get("holder"):
                continue
            holder = str(item["holder"]).strip()
            if holder.lower() not in ("party", "unclaimed") and holder.lower() not in characters:
                log.warning("Item '%s' (%s): holder '%s' isn't a character in data/party.yml (or \"Party\" / \"Unclaimed\")",
                            item.get("name"), path.name, holder)
            held.append({"id": str(item.get("id") or _item_slug(item.get("name", ""))),
                         "name": str(item.get("name", "")), "holder": holder,
                         "hidden": item.get("revealed") is False})   # hidden from the players (Items page)
    return held


def _carried_by(name: str) -> list:
    return [i for i in ITEMS_HELD if i["holder"].lower() == str(name).lower() and not (PLAYERS[0] and i["hidden"])]


def _load_families(path: Path) -> list:
    """data/families.yml -> [{name, members, leaders, allies}], names resolved to creature ids."""
    if not path.is_file():
        return []
    by_name = {}
    for m in MONSTERS.values():
        if m["id"] not in DEDUP_HIDDEN:   # a name means the copy the builder shows
            by_name.setdefault(str(m.get("name", "")).lower(), m["id"])
    families = []
    for fam in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
        entry = {"name": fam.get("family", "?"), "allies": fam.get("allies") or []}
        for field in ("members", "leaders"):
            ids = []
            for ref in fam.get(field) or []:
                ref = str(ref)
                cid = ref if ref in MONSTERS else by_name.get(ref.lower())
                if cid:
                    ids.append(cid)
                else:
                    log.warning("families.yml: '%s' (in %s) doesn't match any creature", ref, entry["name"])
            entry[field] = ids
        families.append(entry)
    names = {f["name"] for f in families}
    for f in families:
        for ally in f["allies"]:
            if ally not in names:
                log.warning("families.yml: %s lists an ally family '%s' that doesn't exist", f["name"], ally)
    return families


def _attack_kind(text: str):
    """'melee', 'ranged', 'both' (thrown weapons), or None for a non-attack action."""
    if re.search(r"Melee or Ranged Weapon Attack", text):
        return "both"
    if re.search(r"Ranged (Weapon|Spell) Attack", text):
        return "ranged"
    if re.search(r"Melee (Weapon|Spell) Attack", text):
        return "melee"
    return None


def _damage(text: str) -> int:
    m = re.search(r"Hit:\*?\s*(\d+)", text)
    return int(m.group(1)) if m else 0


def _combat_role(m: dict):
    """(primary role, can attack at range) read from the stat block.
    Casters have spellcasting. Ranged creatures use a ranged weapon in their Multiattack,
    have no melee attack, or hit harder at range. Everyone else is melee."""
    actions = [a for a in (m.get("actions") or []) if not str(a.get("name", "")).startswith("Multiattack")]
    multi = " ".join(str(a.get("text", "")) for a in (m.get("actions") or [])
                     if str(a.get("name", "")).startswith("Multiattack")).lower()
    melee, ranged = [], []
    for a in actions:
        kind = _attack_kind(str(a.get("text", "")))
        name = re.sub(r"\s*\(.*?\)", "", str(a.get("name", ""))).lower()
        if kind in ("melee", "both"):
            melee.append((name, _damage(str(a.get("text", "")))))
        if kind == "ranged":
            ranged.append((name, _damage(str(a.get("text", "")))))
    can_range = bool(ranged)
    # Real spellcasters only - innate magic (drow, deep gnomes) doesn't make a creature a caster.
    if any(str(t.get("name", "")).startswith("Spellcasting") for t in m.get("traits") or []):
        return "caster", True
    if ranged and not melee:
        return "ranged", True
    if not ranged:
        return "melee", False
    uses_ranged = "ranged" in multi or any(n and n in multi for n, _ in ranged)
    uses_melee = "melee" in multi or any(n and n in multi for n, _ in melee)
    if uses_ranged and not uses_melee:
        return "ranged", can_range
    if uses_melee and not uses_ranged:
        return "melee", can_range
    return ("ranged" if max(d for _, d in ranged) > max(d for _, d in melee) else "melee"), can_range


# ---------------------------------------------------------------- helpers

def _mod(score: int) -> int:
    return (int(score) - 10) // 2


def _signed(n: int) -> str:
    return f"+{n}" if n >= 0 else f"−{abs(n)}"


def _initiative(m: dict) -> int:
    """Initiative bonus: the stat block's own, else the Dex modifier (as the stat block shows it)."""
    try:
        if m.get("initiative") is not None:
            return int(m["initiative"])
        return _mod((m.get("abilities") or {}).get("dex", 10))
    except (TypeError, ValueError):
        return 0


def _cr_key(cr) -> str:
    return str(cr).strip()


def _xp(monster: dict) -> int:
    if monster.get("xp") is not None:
        return int(monster["xp"])
    return CR_XP.get(_cr_key(monster.get("cr", "0")), 0)


def _clean(text) -> str:
    return " ".join(str(text).split())


def _missing(kind: str, key: str) -> str:
    log.warning("Unknown %s id: %s", kind, key)
    return (f'\n!!! failure "Missing {kind}"\n'
            f"    No {kind} with id `{key}` in `data/{kind}s/`.\n")


def _bestiary_link(page_src: str, monster_id: str) -> str:
    start = posixpath.dirname(page_src) or "."
    rel = posixpath.relpath(BESTIARY_PAGE, start)
    return f"{rel}#monster-{monster_id}"


# ---------------------------------------------------------------- stat block

def render_statblock(monster: dict, anchor: bool = False, mentions: bool = True) -> str:
    m = monster
    lines = ['<div class="statblock" markdown>', ""]

    heading = f"### {m.get('name', m['id'])}"
    if anchor:
        heading += f" {{ #monster-{m['id']} }}"
    lines += [heading, ""]

    subtitle = m.get("type") or ""
    cr = _cr_key(m.get("cr", "?"))
    lines += [f"*{subtitle}{' — ' if subtitle else ''}CR {cr} ({_xp(m):,} XP)*", ""]

    # Placeholder creature (no stat block written out - CR, maybe AC and HP, and a note, like the
    # index-only books that are run from the book): a short card.
    if not m.get("abilities") and not m.get("actions") and not m.get("traits"):
        if m.get("ac") is not None or m.get("hp") is not None:
            lines += [f"**Armor Class** {m.get('ac', '?')} · **Hit Points** {m.get('hp', '?')}", ""]
        if m.get("note"):
            lines += [f"*{_clean(m['note'])}*", ""]
        lines += ["</div>", ""]
        return "\n".join(lines)

    lines += ["---", ""]

    ac = f"**Armor Class** {m.get('ac', '?')}"
    if m.get("ac_note"):
        ac += f" ({m['ac_note']})"
    hp = f"**Hit Points** {m.get('hp', '?')}"
    if m.get("hp_formula"):
        hp += f" ({m['hp_formula']})"
    header = [ac, hp, f"**Speed** {m.get('speed', '30 ft.')}"]

    scores = m.get("abilities") or {}
    if "dex" in scores:
        init = m.get("initiative", _mod(scores["dex"]))
        header.append(f"**Initiative** {_signed(int(init))}")
    lines += ["<br>\n".join(header), ""]

    if scores:
        lines += [
            "| STR | DEX | CON | INT | WIS | CHA |",
            "|:-:|:-:|:-:|:-:|:-:|:-:|",
            "| " + " | ".join(
                f"{scores.get(a, 10)} ({_signed(_mod(scores.get(a, 10)))})" for a in ABILITIES
            ) + " |",
            "",
        ]

    details = []
    for label, key in [
        ("Saving Throws", "saves"), ("Skills", "skills"),
        ("Damage Vulnerabilities", "vulnerabilities"),
        ("Damage Resistances", "resistances"), ("Damage Immunities", "immunities"),
        ("Condition Immunities", "condition_immunities"),
        ("Senses", "senses"), ("Languages", "languages"),
    ]:
        if m.get(key):
            details.append(f"**{label}** {m[key]}")
    if details:
        lines += ["<br>\n".join(details), ""]

    def block(entries, title=None):
        if not entries:
            return []
        out = []
        if title:
            # A styled label rather than a heading, so stat blocks don't flood the page's table of contents.
            out += [f'<p class="sb-section">{title}</p>', ""]
        for e in entries:
            text = _clean(e.get('text', ''))
            if mentions:   # "knocked prone" -> a hover card (the builder's pre-rendered copies skip this)
                text = codex_rules.link_conditions(text)
            out += [f"***{e['name']}.*** {text}", ""]
        return out

    lines += ["---", ""]
    lines += block(m.get("traits"))
    lines += block(m.get("actions"), "Actions")
    lines += block(m.get("bonus_actions"), "Bonus Actions")
    lines += block(m.get("reactions"), "Reactions")
    if m.get("legendary_actions"):
        lines += ['<p class="sb-section">Legendary Actions</p>', ""]
        if m.get("legendary_intro"):
            lines += [_clean(m["legendary_intro"]), ""]
        lines += block(m["legendary_actions"])
    lines += block(m.get("lair_actions"), "Lair Actions")

    if m.get("note"):
        lines += ["---", "", f"*{_clean(m['note'])}*", ""]

    lines += ["</div>", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- character cards

def _pc_id(p: dict) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(p.get("character", "")).lower().replace("'", "")).strip("-")


def render_pc_card(p: dict, anchor: bool = False, index: int = None, mentions: bool = True) -> str:
    """A player character as a stat-block-style card. Every field is optional (see
    templates/character.yml); what isn't filled in shows as a dash. `index` (the member's place
    in party.yml) lets the Party page's editor (javascripts/party-editor.js) find it. Items whose
    holder is this character are listed under Carrying - as [[mentions]] (hover cards) on pages,
    plain names where the card is used outside a page (the initiative tracker)."""
    name = p.get("character", "?")
    where = f' data-pc="{index}"' if index is not None else ""
    lines = [f'<div class="statblock pc-card"{where} markdown>', ""]
    lines += [f"### {name}" + (f" {{ #pc-{_pc_id(p)} }}" if anchor else ""), ""]
    what = " ".join(str(x) for x in (p.get("race"), p.get("class")) if x)
    level = p.get("level", PARTY.get("level"))
    subtitle = what + (f", level {level}" if level else "")
    if p.get("player"):
        subtitle += f" — {p['player']}"
    lines += [f"*{subtitle}*", "", "---", ""]

    scores = p.get("abilities") or {}
    dash = "—"
    ac = f"**Armor Class** {p.get('ac', dash)}" + (f" ({p['ac_note']})" if p.get("ac_note") else "")
    hp = f"**Hit Points** {p.get('hp', dash)}" + (f" ({p['hp_formula']})" if p.get("hp_formula") else "")
    init = p.get("initiative", _mod(scores["dex"]) if "dex" in scores else None)
    header = [ac, hp, f"**Speed** {p.get('speed', dash)}",
              f"**Initiative** {_signed(int(init)) if init is not None else dash}"]
    if p.get("passive_perception") is not None:
        header.append(f"**Passive Perception** {p['passive_perception']}")
    lines += ["<br>\n".join(header), ""]
    lines += [
        "| STR | DEX | CON | INT | WIS | CHA |",
        "|:-:|:-:|:-:|:-:|:-:|:-:|",
        "| " + " | ".join(f"{scores[a]} ({_signed(_mod(scores[a]))})" if a in scores else dash
                          for a in ABILITIES) + " |",
        "",
    ]
    details = [f"**{label}** {p[key]}" for label, key in [
        ("Saving Throws", "saves"), ("Skills", "skills"), ("Damage Resistances", "resistances"),
        ("Damage Immunities", "immunities"), ("Condition Immunities", "condition_immunities"),
        ("Senses", "senses"), ("Languages", "languages")] if p.get(key)]
    if details:
        lines += ["<br>\n".join(details), ""]

    sections = [("features", None), ("actions", "Actions"), ("bonus_actions", "Bonus Actions"),
                ("reactions", "Reactions")]
    body = []
    for key, title in sections:
        if p.get(key):
            if title:
                body += [f'<p class="sb-section">{title}</p>', ""]
            body += [line for e in p[key] for line in (f"***{e['name']}.*** {_clean(e.get('text', ''))}", "")]
    lines += ["---", ""]
    if body:
        lines += body
    elif PLAYERS[0]:
        lines += ["*This card hasn't been filled in yet.*", ""]
    else:
        lines += ["*Nothing here yet — fill it in with Edit on the Party page (on the site at home), "
                  "or under this character in `data/party.yml`.*", ""]
    carried = _carried_by(name)
    if carried:
        lines += ['<p class="sb-section">Carrying</p>', "",
                  " · ".join(f"[[{i['name']}]]" if mentions else i["name"] for i in carried), ""]
    if p.get("note") and not PLAYERS[0]:   # the DM's reminders stay off the player site
        lines += ["---", "", f"*{_clean(p['note'])}*", ""]
    lines += ["</div>", ""]
    return "\n".join(lines)


def _party_members() -> list:
    return [p for p in PARTY.get("members") or [] if isinstance(p, dict)]


def render_party_cards() -> str:
    cards = [render_pc_card(p, anchor=True, index=i) for i, p in enumerate(_party_members())]
    shared = _carried_by("Party")
    tail = ("\n**Shared by the party:** " + " · ".join(f"[[{i['name']}]]" for i in shared) + "\n") if shared else ""
    # On the players' site, javascripts/party-editor.js offers each player "Suggest changes" on their own card.
    audience = ' data-audience="players"' if PLAYERS[0] else ""
    return f'<div class="pc-cards"{audience} markdown>\n\n' + "\n".join(cards) + "\n</div>\n" + tail


# ---------------------------------------------------------------- bestiary

def render_bestiary() -> str:
    groups = {}
    for m in MONSTERS.values():
        if m.get("source"):
            continue  # imported creatures (SRD etc.) live in the encounter builder, not here
        groups.setdefault(m.get("group", "Other"), []).append(m)
    out = []
    for group in sorted(groups):
        out += [f"## {group}", ""]
        blocks = [render_statblock(m, anchor=True)
                  for m in sorted(groups[group], key=lambda x: x.get("name", x["id"]).lower())]
        # A divider between stat blocks, so neighbours don't run together.
        out.append('\n<hr class="entry-divider">\n\n'.join(blocks))
    return "\n".join(out)


# ---------------------------------------------------------------- encounters

def _difficulty(adjusted: int, level: int, size: int):
    per = THRESHOLDS.get(level)
    if not per:
        return None, None
    totals = [t * size for t in per]
    label = "Trivial"
    for name, limit in zip(["Easy", "Medium", "Hard", "Deadly"], totals):
        if adjusted >= limit:
            label = name
    return label, totals


def _multiplier(count: int, party_size: int) -> float:
    if count <= 1:
        step = 1
    elif count == 2:
        step = 2
    elif count <= 6:
        step = 3
    elif count <= 10:
        step = 4
    elif count <= 14:
        step = 5
    else:
        step = 6
    if party_size < 3:
        step += 1
    elif party_size >= 6:
        step -= 1
    return MULTIPLIERS[max(0, min(step, len(MULTIPLIERS) - 1))]


def _encounter_totals(enc: dict):
    level = int(enc.get("party_level", PARTY.get("level", 1)))
    size = int(enc.get("party_size", PARTY.get("size", 4)))
    base = count = 0
    for entry in enc.get("creatures", []):
        m = MONSTERS.get(str(entry.get("id")))
        if m:
            qty = int(entry.get("count", 1))
            base += _xp(m) * qty
            count += qty
    adjusted = int(base * _multiplier(count, size))
    label, _ = _difficulty(adjusted, level, size)
    return level, size, count, adjusted, label


def render_encounter_index() -> str:
    """Every encounter in data/encounters/, one row each."""
    out = ['<div class="encounter" markdown>', "",
           "| Encounter | Where | Creatures | Party | Adjusted XP | Difficulty |",
           "|---|---|:-:|:-:|:-:|:-:|"]
    for enc in ENCOUNTERS.values():
        level, size, count, adjusted, label = _encounter_totals(enc)
        name = enc.get("name", enc["id"])
        if enc.get("page"):
            name = f"[{name}]({enc['page']})"
        out.append(f"| {name} | {enc.get('location', '')} | {count} | {size} × L{level} | "
                   f"{adjusted:,} | {label or '—'} |")
    out += ["", "</div>", ""]
    return "\n".join(out)


SIZES = ("Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan")


def _size_and_type(m: dict):
    """Size and creature type, from explicit fields or the 'type' line ("Large monstrosity, ...")."""
    size, ctype = m.get("size"), m.get("creature_type")
    words = str(m.get("type", "")).replace(",", " ").split()
    if not size and words and words[0] in SIZES:
        size = words[0]
    if not ctype and len(words) > 1 and words[0] in SIZES:
        ctype = words[1].strip("()").lower()
    return size or "", ctype or ""


def _encounter_usage() -> dict:
    """{encounter id: [pages that show it with {{ encounter id }}]}"""
    usage = {}
    if not DOCS_DIR[0]:
        return usage
    marker = re.compile(r"\{\{\s*encounter\s+([A-Za-z0-9_-]+)\s*\}\}")
    for path in DOCS_DIR[0].rglob("*.md"):
        rel = path.relative_to(DOCS_DIR[0]).as_posix()
        for eid in marker.findall(path.read_text(encoding="utf-8", errors="ignore")):
            usage.setdefault(eid, []).append(rel)
    return usage


def _encounter_list() -> list:
    """Every encounter, for the Active and Archive lists on the encounters page."""
    usage = _encounter_usage()
    out = []
    for enc in ENCOUNTERS.values():
        page = str(enc.get("page") or "")
        # Scene links are written relative to the encounters page; point them at the built .html.
        page = re.sub(r"\.md(#|$)", r".html\1", page)
        out.append({
            "id": enc["id"], "name": enc.get("name", enc["id"]), "location": enc.get("location", ""),
            "page": page, "archived": bool(enc.get("archived")),
            "party_level": enc.get("party_level"), "party_size": enc.get("party_size"),
            "creatures": [{"id": str(c.get("id")), "count": int(c.get("count", 1))}
                          for c in enc.get("creatures", [])],
            "used_on": sorted(set(usage.get(enc["id"], []))),
        })
    out.sort(key=lambda e: e["name"].lower())
    return out


def render_encounter_builder() -> str:
    """The encounter builder: every creature (with its stat block pre-rendered),
    the party, and the difficulty tables, embedded for javascripts/encounter-builder.js."""
    import markdown as md_lib
    creatures = []
    # Duplicates (data/monsters-dedup.yml) stay out - unless a saved encounter uses that copy.
    used = {c.get("id") for e in ENCOUNTERS.values() for c in e.get("creatures") or [] if isinstance(c, dict)}
    for m in MONSTERS.values():
        if m["id"] in DEDUP_HIDDEN and m["id"] not in used:
            continue
        size, ctype = _size_and_type(m)
        html = md_lib.markdown(render_statblock(m, mentions=False), extensions=["tables", "attr_list", "md_in_html"])
        # "custom" creatures (custom.yml) can be edited and deleted in the builder; others only copied.
        source = m.get("source") or ("custom" if MONSTER_FILES.get(m["id"]) == CUSTOM_FILE else "campaign")
        creatures.append({
            "id": m["id"], "name": m.get("name", m["id"]), "cr": _cr_key(m.get("cr", "0")),
            "xp": _xp(m), "size": size, "type": ctype, "ac": m.get("ac"), "hp": m.get("hp"),
            "source": source, "env": m.get("environments") or [], "sb": html, "init": _initiative(m),
        })
        creatures[-1]["role"], creatures[-1]["rc"] = _combat_role(m)
    creatures.sort(key=lambda c: c["name"].lower())
    data = {
        "creatures": creatures,
        # each imported source's name (a monster sheet's "title"), for the builder's Source filter
        "sources": {m["source"]: str(m["group"]) for m in MONSTERS.values() if m.get("source") and m.get("group")},
        "party": {"level": int(PARTY.get("level", 1)), "size": int(PARTY.get("size", 4)),
                  # Each character's card (for the initiative tracker) and the numbers it starts from.
                  "members": [{"character": str(p.get("character", "")), "player": str(p.get("player", "")),
                               "ac": p.get("ac"), "hp": p.get("hp"), "init": _initiative(p),
                               "sb": md_lib.markdown(render_pc_card(p, mentions=False), extensions=["tables", "attr_list", "md_in_html"])}
                              for p in _party_members()]},
        "thresholds": THRESHOLDS,
        "multipliers": MULTIPLIERS,
        "encounters": _encounter_list(),
        "families": FAMILIES,
        # what each condition does (the SRD's text), shown when you hover one in the initiative tracker
        "conditions": _condition_texts(),
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return ('<div id="eb-root" class="eb"><p>Loading the encounter builder…</p></div>\n\n'
            f'<script type="application/json" id="eb-data">{payload}</script>\n')


def _condition_texts() -> dict:
    """{"Prone": "A prone creature's only movement option is to crawl..."} - plain text, for tooltips."""
    out = {}
    for c in codex_rules.DATA.get("conditions", []):
        text = re.sub(r"(?m)^\s*[*-]\s+", "• ", c["text"])
        out[c["name"]] = re.sub(r"\*\*|__|\*", "", text).strip()
    return out


def render_encounter(enc: dict, page_src: str) -> str:
    level = int(enc.get("party_level", PARTY.get("level", 1)))
    size = int(enc.get("party_size", PARTY.get("size", 4)))

    rows, base, count = [], 0, 0
    for entry in enc.get("creatures", []):
        mid = str(entry.get("id"))
        qty = int(entry.get("count", 1))
        m = MONSTERS.get(mid)
        if not m:
            rows.append(f"| ⚠ unknown `{mid}` | {qty} | | | | |")
            log.warning("Encounter %s references unknown creature %s", enc["id"], mid)
            continue
        xp = _xp(m)
        base += xp * qty
        count += qty
        # Imported creatures (SRD, the books) aren't on the Bestiary page - put {{ statblock <id> }} on the
        # page instead - so only the campaign's own link there.
        name = f"**{m.get('name', mid)}**" if m.get("source") else f"[{m.get('name', mid)}]({_bestiary_link(page_src, mid)})"
        if entry.get("note"):
            name += f" — {entry['note']}"
        rows.append(f"| {name} | {qty} | {_cr_key(m.get('cr'))} | {xp:,} | {m.get('ac', '?')} | {m.get('hp', '?')} |")

    mult = _multiplier(count, size)
    adjusted = int(base * mult)
    label, totals = _difficulty(adjusted, level, size)

    out = ['<div class="encounter" markdown>', ""]
    out += ["| Creature | # | CR | XP each | AC | HP |", "|---|:-:|:-:|:-:|:-:|:-:|"]
    out += rows
    out += [""]
    summary = (f"**Base XP** {base:,} · **Creatures** {count} · **Multiplier** ×{mult:g} · "
               f"**Adjusted XP** {adjusted:,}")
    out += [summary, ""]
    if totals:
        e, m_, h, d = totals
        out += [f"**Difficulty for {size} level-{level} PCs: {label}** "
                f"(Easy {e:,} · Medium {m_:,} · Hard {h:,} · Deadly {d:,})", ""]
    if page_src != ENCOUNTER_PAGE:
        here = posixpath.dirname(page_src) or "."
        target = posixpath.relpath(ENCOUNTER_PAGE.replace(".md", ".html"), here)
        out += [f'<a class="enc-edit" href="{target}?edit={enc["id"]}">Open in the encounter builder</a> · '
                f'<a class="enc-edit" href="{target}?run={enc["id"]}">Run it in the initiative tracker</a>', ""]
    out += ["</div>", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- page hook

def on_page_markdown(markdown, page, config, files, **kwargs):
    src = page.file.src_uri

    def render(kind, key):
        if kind == "bestiary":
            return render_bestiary()
        if kind == "encounters":
            return render_encounter_index()
        if kind == "encounter-builder":
            return render_encounter_builder()
        if kind == "party-cards":
            return render_party_cards()
        if kind == "party-card":
            p = next((m for m in _party_members() if _pc_id(m) == key), None)
            if p:
                return render_pc_card(p)
            log.warning("Unknown character in {{ party-card %s }} (use the name as in its card's anchor, e.g. kestrel)", key)
            return (f'\n!!! failure "Missing character"\n'
                    f"    No character `{key}` in `data/party.yml` (written like its card's anchor: `kestrel`, `oskar-fenn`).\n")
        if kind == "statblock":
            m = MONSTERS.get(key)
            return render_statblock(m) if m else _missing("monster", key)
        enc = ENCOUNTERS.get(key)
        return render_encounter(enc, src) if enc else _missing("encounter", key)

    def replace(match):
        indent, kind, key = match.group(1), match.group(2), match.group(3)
        if PLAYERS[0] and kind not in ("party-cards", "party-card"):
            return ""   # stat blocks, encounters, the builder: DM material
        text = render(kind, key)
        return "\n".join(indent + line if line else line for line in text.split("\n"))

    return MARKER.sub(replace, markdown)


def on_post_page(output, page, config, **kwargs):
    """Tell the page's scripts which campaign this is, so the encounter builder, recorder, and
    editors keep their saved state per campaign (two campaigns served on one computer share a
    browser address, and would otherwise overwrite each other's)."""
    tag = f'<meta name="codex-campaign" content="{CAMPAIGN_SLUG[0]}">'
    return output.replace("</head>", tag + "</head>", 1)
