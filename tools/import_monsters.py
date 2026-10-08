r"""
Import monsters from outside sources into the site's creature format.

    python tools\import_monsters.py srd        # download and convert the 5e SRD monsters
    python tools\import_monsters.py tob        # Tome of Beasts (Kobold Press, Open Game License)
    python tools\import_monsters.py cc         # also tob2, tob3: Creature Codex, Tome of Beasts 2 and 3
    python tools\import_monsters.py vgm        # also foes: Volo's Guide, Fifth Edition Foes - as an index
    python tools\import_monsters.py all        # every source
    python tools\import_monsters.py file "my creatures.json"   # a monster sheet you filled in
                                               # (templates\monsters.json shows how)
    python tools\import_monsters.py dedup      # hide duplicate creatures (also runs after every import)
    python tools\import_monsters.py --list     # show available sources

Books whose stat blocks aren't open content (Volo's Guide to Monsters, Mordenkainen's Tome of Foes, Fifth Edition Foes) come in as an
index only - name, CR, size, type, alignment, AC, HP, initiative, environments, and the page - from the
Kobold Fight Club project's monster list; you run them from your copy of the book.

Each source writes one generated file, data\monsters\<source>.json. Those files are
replaced on every import, so never edit them - put your own creatures (and any
tweaked copies of imported ones) in YAML files in data\monsters\ instead.

Adding a source: write a function that returns a list of creature dicts in the
site's format (see templates\monster.yml) and register it in SOURCES below.
"""

import argparse
import json
import re
import sys
import urllib.request
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "monsters"


# ---------------------------------------------------------------- helpers

def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "CampaignCodex5e"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def cr_text(value) -> str:
    """0.125 -> '1/8', 2 -> '2'"""
    f = Fraction(value).limit_denominator(8)
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def dice(text: str) -> str:
    """'7d10+21' -> '7d10 + 21'"""
    return re.sub(r"\s*([+-])\s*", r" \1 ", str(text or "")).strip()


def signed(n: int) -> str:
    return f"+{n}" if n >= 0 else f"−{abs(n)}"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------- source: 5e SRD (5e-bits database)

SRD_URL = "https://raw.githubusercontent.com/5e-bits/5e-database/main/src/2014/en/5e-SRD-Monsters.json"
SRD_CREDIT = ("Monster data from the System Reference Document 5.1 by Wizards of the Coast, licensed "
              "under CC BY 4.0, via the 5e-bits 5e-database project.")


def _usage(entry: dict) -> str:
    u = entry.get("usage") or {}
    kind = u.get("type", "")
    if kind == "per day":
        return f" ({u.get('times')}/Day)"
    if kind == "recharge on roll":
        low = u.get("min_value", 6)
        return " (Recharge 6)" if low == 6 else f" (Recharge {low}–6)"
    if kind == "recharge after rest":
        rests = " or ".join(r.title() for r in u.get("rest_types", []))
        return f" (Recharges after a {rests} Rest)" if rests else ""
    return ""


def _entries(items) -> list:
    out = []
    for e in items or []:
        name = e.get("name", "").strip() + _usage(e)
        text = " ".join(str(e.get("desc", "")).split())
        # Italicize the attack label, as printed stat blocks do.
        text = re.sub(r"^((?:Melee|Ranged)(?: or Ranged)? (?:Weapon|Spell) Attack:)", r"*\1*", text)
        text = re.sub(r"\bHit:", "*Hit:*", text, count=1)
        out.append({"name": name, "text": text})
    return out


def convert_srd(m: dict) -> dict:
    subtype = f" ({m['subtype']})" if m.get("subtype") else ""
    ac = (m.get("armor_class") or [{}])[0]
    ac_note = ac.get("type", "")
    if ac_note == "armor" and ac.get("armor"):
        ac_note = ", ".join(a.get("name", "").lower() for a in ac["armor"])
    elif ac_note in ("dex", ""):
        ac_note = None
    elif ac_note == "natural":
        ac_note = "natural armor"

    speed = m.get("speed") or {}
    parts = [speed.get("walk", "0 ft.")] + [f"{k} {v}" for k, v in speed.items()
                                            if k not in ("walk", "hover")]
    speed_text = ", ".join(parts) + (" (hover)" if speed.get("hover") else "")

    saves, skills = [], []
    for p in m.get("proficiencies") or []:
        pname = p.get("proficiency", {}).get("name", "")
        if pname.startswith("Saving Throw: "):
            saves.append(f"{pname.split(': ')[1].title()} {signed(p['value'])}")
        elif pname.startswith("Skill: "):
            skills.append(f"{pname.split(': ')[1]} {signed(p['value'])}")

    senses = m.get("senses") or {}
    sense_parts = [f"{k.replace('_', ' ')} {v}" for k, v in senses.items() if k != "passive_perception"]
    sense_parts.append(f"passive Perception {senses.get('passive_perception', 10)}")

    c = {
        "id": "srd-" + m["index"],
        "name": m["name"],
        "source": "srd",
        "group": "SRD",
        "size": m.get("size"),
        "creature_type": m.get("type"),
        "type": f"{m.get('size', '')} {m.get('type', '')}{subtype}, {m.get('alignment', '')}".strip(),
        "cr": cr_text(m.get("challenge_rating", 0)),
        "xp": m.get("xp"),
        "ac": ac.get("value"),
        "hp": m.get("hit_points"),
        "hp_formula": dice(m.get("hit_points_roll") or m.get("hit_dice")),
        "speed": speed_text,
        "abilities": {k[:3]: m.get(k) for k in
                      ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")},
        "senses": ", ".join(sense_parts),
        "languages": m.get("languages") or "—",
    }
    if ac_note:
        c["ac_note"] = ac_note
    if saves:
        c["saves"] = ", ".join(saves)
    if skills:
        c["skills"] = ", ".join(skills)
    for field, key in (("vulnerabilities", "damage_vulnerabilities"),
                       ("resistances", "damage_resistances"),
                       ("immunities", "damage_immunities")):
        if m.get(key):
            c[field] = ", ".join(m[key])
    if m.get("condition_immunities"):
        c["condition_immunities"] = ", ".join(x.get("name", "").lower() for x in m["condition_immunities"])
    for field, key in (("traits", "special_abilities"), ("actions", "actions"),
                       ("reactions", "reactions"), ("legendary_actions", "legendary_actions")):
        if m.get(key):
            c[field] = _entries(m[key])
    return c


# Environments aren't part of the SRD itself; Open5e's copy of the SRD tags every monster.
OPEN5E_SRD_URL = "https://raw.githubusercontent.com/open5e/open5e-api/main/data/v1/wotc-srd/Monster.json"

# Open5e's environment names, merged into one clean list.
ENVIRONMENTS = {
    "hill": "Hills", "hills": "Hills", "mountain": "Mountains", "mountains": "Mountains",
    "ruin": "Ruins", "ruins": "Ruins", "caverns": "Caverns", "caves": "Caverns",
    "settlement": "Urban", "urban": "Urban", "tundra": "Arctic", "arctic": "Arctic", "ice": "Arctic",
    "ocean": "Water", "lake": "Water", "water": "Water", "volcano": "Mountains",
    "plane of earth": "Elemental Planes", "plane of water": "Elemental Planes",
    "plane of fire": "Elemental Planes", "plane of air": "Elemental Planes",
    "abyss": "Lower Planes", "hell": "Lower Planes",
    "astral plane": "Astral & Ethereal", "ethereal plane": "Astral & Ethereal",
}


def _environment_table() -> dict:
    """{monster name: ([environments], open5e group or None)} from Open5e's SRD data."""
    try:
        rows = fetch_json(OPEN5E_SRD_URL)
    except Exception as err:  # environments are a bonus; the import still works without them
        print(f"  (couldn't fetch environments: {err})")
        return {}
    table = {}
    for row in rows:
        f = row.get("fields", {})
        envs = []
        for e in json.loads(f.get("environments_json") or "[]"):
            name = ENVIRONMENTS.get(e.strip().lower(), e.strip().title())
            if name != "Any" and name not in envs:
                envs.append(name)
        group = f.get("group")
        table[f.get("name", "")] = (sorted(envs), None if group == "Miscellaneous Creatures" else group)
    return table


def source_srd() -> dict:
    raw = fetch_json(SRD_URL)
    envs = _environment_table()
    creatures = []
    for m in raw:
        c = convert_srd(m)
        # Shapechanger forms ("Werebear, Bear Form") share their base creature's environments.
        base = c["name"].split(",")[0].strip()
        env, group = envs.get(c["name"]) or envs.get(base) or ([], None)
        if env:
            c["environments"] = env
        if group:
            c["srd_group"] = group
        creatures.append(c)
    tagged = sum(1 for c in creatures if c.get("environments"))
    print(f"  environments found for {tagged} of {len(creatures)} creatures")
    return {"credit": SRD_CREDIT + " Environments from the Open5e project.", "creatures": creatures}


# ---------------------------------------------------------------- sources: Kobold Press books (Open5e)
# Kobold Press released these books' stat blocks as Open Game Content; the Open5e project keeps them
# as data. Only the stat blocks are imported, not the lore text. Open5e has no environments for them.

OPEN5E_V1 = "https://raw.githubusercontent.com/open5e/open5e-api/main/data/v1/{}/{}.json"
ABILITY_NAMES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def _json_field(value):
    if isinstance(value, str):
        try:
            return json.loads(value) if value.strip() else None
        except ValueError:
            return None
    return value


def convert_open5e(f: dict, prefix: str, source: str, group: str) -> dict:
    """An Open5e (v1 data) monster in the site's format."""
    subtype = f" ({f['subtype']})" if f.get("subtype") else ""
    size, ctype = f.get("size") or "", str(f.get("type") or "").lower()
    speed = _json_field(f.get("speed_json")) or {}
    feet = lambda v: v if isinstance(v, str) and "ft" in v else f"{v} ft."
    parts = [feet(speed.get("walk", 0))] + [f"{k} {feet(v)}" for k, v in speed.items()
                                              if k not in ("walk", "hover") and v not in (None, "", 0, False)]
    saves = [f"{a[:3].title()} {signed(int(f[a + '_save']))}" for a in ABILITY_NAMES if f.get(a + "_save") is not None]
    skills = _json_field(f.get("skills_json")) or {}
    c = {
        "id": f"{prefix}-{slug(f['name'])}",
        "name": f["name"],
        "source": source,
        "group": group,
        "size": size or None,
        "creature_type": ctype or None,
        "type": f"{size} {ctype}{subtype}, {f.get('alignment') or 'unaligned'}".strip(),
        "cr": cr_text(f.get("cr") if f.get("cr") is not None else 0),
        "ac": f.get("armor_class"),
        "hp": f.get("hit_points"),
        "hp_formula": dice(f.get("hit_dice")),
        "speed": ", ".join(parts) + (" (hover)" if speed.get("hover") else ""),
        "abilities": {a[:3]: f.get(a) for a in ABILITY_NAMES},
        "senses": f.get("senses") or "passive Perception 10",
        "languages": f.get("languages") or "—",
    }
    if f.get("armor_desc"):
        c["ac_note"] = f["armor_desc"]
    if saves:
        c["saves"] = ", ".join(saves)
    if skills:
        c["skills"] = ", ".join(f"{k.replace('_', ' ').title()} {signed(int(v))}" for k, v in skills.items())
    for field, key in (("vulnerabilities", "damage_vulnerabilities"), ("resistances", "damage_resistances"),
                       ("immunities", "damage_immunities"), ("condition_immunities", "condition_immunities")):
        if f.get(key):
            c[field] = f[key]
    for field, key in (("traits", "special_abilities_json"), ("actions", "actions_json"),
                       ("bonus_actions", "bonus_actions_json"), ("reactions", "reactions_json"),
                       ("legendary_actions", "legendary_actions_json")):
        entries = _json_field(f.get(key))
        if entries:
            c[field] = _entries(entries)
    if f.get("page_no"):
        c["note"] = f"{group}, p. {f['page_no']}."
    return {k: v for k, v in c.items() if v is not None}


# ---------------------------------------------------------------- Kobold Fight Club's monster index
# Kobold Fight Club (MIT license) lists monsters from many books: name, CR, size, type, alignment, AC,
# HP, initiative, environments, and page. It supplies the environments Open5e lacks, and the index for
# books whose stat blocks aren't open content.

KFC_URL = "https://raw.githubusercontent.com/fantasycalendar/kobold-plus-fight-club/master/public/json/{}.json"
KFC_ENVIRONMENTS = {
    "forest": "Forest", "urban": "Urban", "underground": "Underdark", "underdark": "Underdark",
    "cave": "Caverns", "caves": "Caverns", "caverns": "Caverns", "grassland": "Grassland",
    "grasslands": "Grassland", "plains": "Grassland", "mountain": "Mountains", "mountains": "Mountains",
    "hill": "Hills", "hills": "Hills", "swamp": "Swamp", "desert": "Desert", "ruins": "Ruins",
    "coast": "Coastal", "coastal": "Coastal", "arctic": "Arctic", "tundra": "Arctic",
    "aquatic": "Underwater", "underwater": "Underwater", "water": "Water", "ocean": "Water",
    "jungle": "Jungle", "sewer": "Sewer", "shadowfell": "Shadowfell", "feywild": "Feywild",
    "planar": "Other Planes", "dungeon": "Dungeon", "tomb": "Tomb", "temple": "Temple",
}
_KFC = []


def kfc_monsters() -> list:
    if not _KFC:
        for name in ("se_monsters", "se_third_party_monsters"):
            _KFC.extend(fetch_json(KFC_URL.format(name)))
    return _KFC


def kfc_page(m: dict, book: str):
    """The page in `book` from a Kobold Fight Club entry ("Volo's Guide to Monsters: 131, ..."), or None."""
    for part in str(m.get("sources", "")).split(","):
        name, _, page = part.strip().rpartition(":")
        if name.strip() == book:
            return page.strip() or "?"
    return None


def kfc_environments(m: dict) -> list:
    envs = []
    for e in str(m.get("environment") or "").split(","):
        name = KFC_ENVIRONMENTS.get(e.strip().lower(), e.strip().title())
        if name and name not in envs:
            envs.append(name)
    return sorted(envs)


def add_environments(creatures: list, book: str) -> None:
    """Fill in environments from Kobold Fight Club's list of the same book, matched by name."""
    table = {m["name"].lower(): kfc_environments(m) for m in kfc_monsters() if kfc_page(m, book)}
    tagged = 0
    for c in creatures:
        env = table.get(c["name"].lower())
        if env:
            c["environments"] = env
            tagged += 1
    print(f"  environments found for {tagged} of {len(creatures)} creatures")


def kfc_index_source(key: str, book: str):
    """A source function for a book as an index: no rules text, so you run each creature from the book."""
    def source() -> dict:
        creatures, seen = [], {}
        for m in kfc_monsters():
            page = kfc_page(m, book)
            if page is None or not m.get("name"):
                continue
            ctype = str(m.get("type") or "").lower()
            tags = f" ({m['tags'].lower()})" if m.get("tags") else ""
            c = {"id": f"{key}-{slug(m['name'])}", "name": m["name"], "source": key, "group": book,
                 "books": sorted({s.strip().rpartition(":")[0].strip() for s in str(m.get("sources", "")).split(",") if ":" in s}),
                 "cr": cr_text(m.get("cr") or 0), "size": m.get("size") or None, "creature_type": ctype or None,
                 "type": f"{m.get('size', '')} {ctype}{tags}, {m.get('alignment') or 'unaligned'}".strip(),
                 "ac": m.get("ac"), "hp": m.get("hp"), "initiative": m.get("init"),
                 "note": f"{book}, p. {page} — the full stat block is in the book."}
            env = kfc_environments(m)
            if env:
                c["environments"] = env
            seen[c["id"]] = seen.get(c["id"], 0) + 1
            if seen[c["id"]] > 1:
                c["id"] += f"-{seen[c['id']]}"
            creatures.append({k: v for k, v in c.items() if v not in (None, "")})
        credit = (f"An index of {book} (name, CR, size, type, AC, HP, environments, page) from the Kobold Fight "
                  "Club project - the stat blocks themselves are in the book.")
        return {"credit": credit, "creatures": creatures}
    return source


def open5e_source(key: str, title: str):
    """A source function for one Open5e book: its monsters, credited as the book's legal notice says."""
    def source() -> dict:
        rows = fetch_json(OPEN5E_V1.format(key, "Monster"))
        doc = (fetch_json(OPEN5E_V1.format(key, "Document")) or [{}])[0].get("fields", {})
        creatures = [convert_open5e(r["fields"], key, key, title) for r in rows if r.get("fields", {}).get("name")]
        try:
            add_environments(creatures, title)
        except Exception as err:  # environments are a bonus; the import still works without them
            print(f"  (couldn't fetch environments: {err})")
        seen = {}
        for c in creatures:   # the rare repeated name gets a numbered id
            seen[c["id"]] = seen.get(c["id"], 0) + 1
            if seen[c["id"]] > 1:
                c["id"] += f"-{seen[c['id']]}"
        credit = (f"Monster data from {doc.get('copyright') or title} Open Game Content under the "
                  f"{doc.get('license') or 'Open Game License'} 1.0a, via the Open5e project.")
        return {"credit": credit, "creatures": creatures}
    return source


SOURCES = {
    "srd": ("The 5e System Reference Document 5.1 (334 monsters)", source_srd),
    "tob": ("Tome of Beasts, Kobold Press - Open Game License (391 monsters)", open5e_source("tob", "Tome of Beasts")),
    "tob2": ("Tome of Beasts 2, Kobold Press - Open Game License (383 monsters)", open5e_source("tob2", "Tome of Beasts 2")),
    "tob3": ("Tome of Beasts 3, Kobold Press - Open Game License (397 monsters)", open5e_source("tob3", "Tome of Beasts 3")),
    "cc": ("Creature Codex, Kobold Press - Open Game License (356 monsters)", open5e_source("cc", "Creature Codex")),
    "vgm": ("Volo's Guide to Monsters - index only: run them from the book (129 monsters)",
            kfc_index_source("vgm", "Volo's Guide to Monsters")),
    "foes": ("Fifth Edition Foes - index only: run them from the book (254 monsters)",
             kfc_index_source("foes", "Fifth Edition Foes")),
    "mtf": ("Mordenkainen's Tome of Foes - index only: run them from the book",
            kfc_index_source("mtf", "Mordenkainen's Tome of Foes")),
}


# ---------------------------------------------------------------- source: a monster sheet you filled in
# templates/monsters.json is the sheet: {"source", "title", "creatures": [...]}. Each creature is
# checked and tidied into the site's format; problems are reported by name, and a creature with an
# error is left out rather than imported half-right.

SHEET_FIELDS = ("id", "name", "type", "size", "creature_type", "alignment", "environments", "cr", "ac", "ac_note",
                "hp", "hp_formula", "speed", "abilities", "initiative", "saves", "skills", "vulnerabilities",
                "resistances", "immunities", "condition_immunities", "senses", "languages", "traits", "actions",
                "bonus_actions", "reactions", "legendary_intro", "legendary_actions", "lair_actions", "page", "note",
                # a whole-library sheet (one creature per entry, from several books) may also have:
                "sources", "text_source", "review")
# Read but not needed here (kept in the sheet, not imported).
SHEET_IGNORED = ("tags", "group", "organization", "environment_text", "unique", "legendary", "xp")
SHEET_LISTS = ("traits", "actions", "bonus_actions", "reactions", "legendary_actions", "lair_actions")
SIZES = ("Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan")
CRS = ["0", "1/8", "1/4", "1/2"] + [str(n) for n in range(1, 31)]
ABILITY_KEYS = ("str", "dex", "con", "int", "wis", "cha")


def _italics(text: str) -> str:
    """Attack labels in italics, as printed stat blocks (and the imported books) have them."""
    text = " ".join(str(text).split())
    if "*" not in text:
        text = re.sub(r"^((?:Melee|Ranged)(?: or Ranged)? (?:Weapon|Spell) Attack:)", r"*\1*", text)
        text = re.sub(r"\bHit:", "*Hit:*", text, count=1)
    return text


def _whole(value, what: str, low=-50, high=1000) -> int:
    try:
        n = int(str(value).strip().replace("+", "").replace("−", "-"))
    except ValueError:
        raise ValueError(f"{what} should be a whole number (got {value!r})")
    if not low <= n <= high:
        raise ValueError(f"{what} {n} is out of range")
    return n


def _bonus_list(value, what: str) -> str:
    """'Con +7, Wis +5', or {"con": 7, "wis": 5} -> 'Con +7, Wis +5'."""
    if isinstance(value, dict):
        return ", ".join(f"{k.replace('_', ' ').title()} {signed(_whole(v, what + ' ' + k))}" for k, v in value.items())
    return " ".join(str(value).split())


def sheet_creature(raw: dict, key: str, title: str):
    """(creature, [warnings]) - or raises ValueError with what's wrong."""
    warn = []
    unknown = [k for k in raw if k not in SHEET_FIELDS + SHEET_IGNORED and not k.startswith("_")]
    if unknown:
        warn.append(f"ignored unknown field(s): {', '.join(unknown)}")
    name = " ".join(str(raw.get("name") or "").split())
    if not name:
        raise ValueError("it has no name")
    c = {"id": str(raw.get("id") or f"{key}-{slug(name)}"), "name": name, "source": key, "group": title}
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", c["id"]):
        raise ValueError(f"id '{c['id']}' should be lowercase letters, numbers, and dashes")

    cr = raw.get("cr")
    if cr is None or cr == "":
        raise ValueError("it needs a cr (challenge rating)")
    cr = cr_text(cr) if isinstance(cr, (int, float)) else str(cr).strip()
    if cr not in CRS:
        raise ValueError(f"cr '{raw.get('cr')}' isn't a challenge rating (0, 1/8, 1/4, 1/2, 1 ... 30)")
    c["cr"] = cr

    # the italic line: given, or made from size, type, and alignment - and the filters read from it
    size, ctype = raw.get("size"), raw.get("creature_type")
    line = " ".join(str(raw.get("type") or "").split())
    if line:
        size = size or next((s for s in SIZES if re.match(s + r"\b", line, re.I)), None)
        if not ctype:
            m = re.match(r"^(?:\w+\s+)?([a-z]+)", line.lower())
            ctype = m.group(1) if m and m.group(1) not in [s.lower() for s in SIZES] else None
    else:
        line = f"{str(size or '').title()} {str(ctype or '').lower()}".strip() + (f", {raw['alignment']}" if raw.get("alignment") else "")
    if size and str(size).title() not in SIZES:
        raise ValueError(f"size '{size}' should be one of {', '.join(SIZES)}")
    c.update({k: v for k, v in (("type", line), ("size", str(size).title() if size else None),
                                ("creature_type", str(ctype).lower() if ctype else None)) if v})

    ac = raw.get("ac")
    if ac not in (None, ""):
        m = re.match(r"^\s*(\d+)\s*(?:\((.*)\))?\s*$", str(ac))
        if not m:
            raise ValueError(f"ac should be a number, like 15 or \"15 (natural armor)\" (got {ac!r})")
        c["ac"] = int(m.group(1))
        if m.group(2) and not raw.get("ac_note"):
            c["ac_note"] = m.group(2)
    if raw.get("ac_note"):
        c["ac_note"] = str(raw["ac_note"])
    if raw.get("hp_formula"):
        c["hp_formula"] = dice(raw["hp_formula"])
    if raw.get("hp") not in (None, ""):
        c["hp"] = _whole(raw["hp"], "hp", 1, 10000)
    elif c.get("hp_formula"):
        m = re.fullmatch(r"(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?", c["hp_formula"].replace(" ", ""))
        if m:   # the average, as stat blocks print it
            c["hp"] = max(1, int(m.group(1)) * (int(m.group(2)) + 1) // 2 + (int(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)))

    speed = raw.get("speed")
    if isinstance(speed, dict):
        parts = [f"{speed.get('walk', 30)} ft."] + [f"{k} {v} ft." for k, v in speed.items() if k not in ("walk", "hover")]
        c["speed"] = ", ".join(parts) + (" (hover)" if speed.get("hover") else "")
    elif speed:
        c["speed"] = " ".join(str(speed).split())

    abil = raw.get("abilities")
    if abil not in (None, "", {}):
        if isinstance(abil, list) and len(abil) == 6:
            abil = dict(zip(ABILITY_KEYS, abil))
        if not isinstance(abil, dict) or set(k.lower()[:3] for k in abil) != set(ABILITY_KEYS):
            raise ValueError("abilities needs all six scores: {\"str\": 10, \"dex\": 10, \"con\": 10, \"int\": 10, \"wis\": 10, \"cha\": 10}")
        c["abilities"] = {k.lower()[:3]: _whole(v, f"ability score {k}", 0, 30) for k, v in abil.items()}   # 0 = a "—" score
    if raw.get("initiative") not in (None, ""):
        c["initiative"] = _whole(raw["initiative"], "initiative")
    for field in ("saves", "skills"):
        if raw.get(field):
            c[field] = _bonus_list(raw[field], field)
    for field in ("vulnerabilities", "resistances", "immunities", "condition_immunities", "senses", "languages"):
        value = raw.get(field)
        if value:
            c[field] = ", ".join(map(str, value)) if isinstance(value, list) else " ".join(str(value).split())
    envs = raw.get("environments") or []
    if isinstance(envs, str):
        envs = envs.split(",")
    envs = sorted({KFC_ENVIRONMENTS.get(str(e).strip().lower(), str(e).strip().title()) for e in envs if str(e).strip()})
    if envs:
        c["environments"] = envs

    for field in SHEET_LISTS:
        entries = raw.get(field) or []
        if not isinstance(entries, list):
            raise ValueError(f"{field} should be a list of {{\"name\": ..., \"text\": ...}}")
        rows = []
        for e in entries:
            if isinstance(e, str):   # "Keen Smell. The wolf has advantage..." also works
                name_part, _, text = e.partition(". ")
                e = {"name": name_part, "text": text}
            if not isinstance(e, dict) or not str(e.get("name", "")).strip():
                raise ValueError(f"every entry under {field} needs a name")
            rows.append({"name": " ".join(str(e["name"]).split()), "text": _italics(e.get("text", ""))})
        if rows:
            c[field] = rows

    if raw.get("legendary_intro"):
        c["legendary_intro"] = " ".join(str(raw["legendary_intro"]).split())
    note = " ".join(str(raw.get("note") or "").split())
    if raw.get("page"):
        note = (note + " " if note else "") + f"{title}, p. {raw['page']}."
    books = [b for b in raw.get("sources") or [] if isinstance(b, dict) and b.get("book")]
    c["books"] = sorted({str(b["book"]) for b in books}) or [title]
    if books and not note.startswith("Index entry"):
        note = (note + " " if note else "") + "; ".join(
            f"{b['book']}" + (f", p. {b['page']}" if b.get("page") else "") for b in books) + "."
    if "ocr" in str(raw.get("text_source") or "").lower():
        note += " Read from a scanned page - check it against the book."
    if raw.get("review"):
        items = raw["review"] if isinstance(raw["review"], list) else [raw["review"]]
        note += " To check: " + "; ".join(map(str, items)) + "."
    note = note.strip()
    if note:
        c["note"] = note
    if "abilities" not in c:
        warn.append("no ability scores - it shows as a short card (CR, AC, HP, note)")
    elif "actions" not in c:
        warn.append("no actions")
    if "ac" not in c or "hp" not in c:
        warn.append("no AC or HP - the initiative tracker will leave them blank")
    return c, warn


def source_sheet(path: Path) -> tuple:
    """(file key, result) for a monster sheet."""
    try:
        sheet = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SystemExit(f"No file at {path}.")
    except ValueError as err:
        raise SystemExit(f"{path.name} isn't valid JSON - {err}. (A missing comma or quote is the usual cause.)")
    if not isinstance(sheet, dict) or not isinstance(sheet.get("creatures"), list):
        raise SystemExit(f'{path.name} should look like templates\\monsters.json: {{"source": ..., "title": ..., "creatures": [...]}}')
    key = slug(str(sheet.get("source") or path.stem))
    title = str(sheet.get("title") or key.title())
    # A whole-library sheet names each creature's book(s) in "sources"; each book becomes its own
    # source in the builder (its title in the Source filter), e.g. "book-monster-manual".
    library = any(isinstance(c, dict) and isinstance(c.get("sources"), list) and c["sources"] for c in sheet["creatures"])
    if key in SOURCES or key in ("custom", "campaign", "all", "file", "dedup"):
        raise SystemExit(f'"source": "{key}" is already used - pick another short name for this sheet.')
    creatures, problems, seen = [], 0, set()
    for i, raw in enumerate(sheet["creatures"], 1):
        label = raw.get("name") if isinstance(raw, dict) and raw.get("name") else f"creature #{i}"
        try:
            if not isinstance(raw, dict):
                raise ValueError("it isn't a {...} entry")
            if library and raw.get("sources"):
                book = str(raw["sources"][0].get("book") or title)
                c, warn = sheet_creature(raw, "book-" + slug(book), book)
            else:
                c, warn = sheet_creature(raw, key, title)
            if c["id"] in seen:
                raise ValueError(f"the id '{c['id']}' is used twice in this sheet")
        except ValueError as err:
            problems += 1
            print(f"  LEFT OUT {label}: {err}")
            continue
        seen.add(c["id"])
        creatures.append(c)
        for w in warn:
            if not library:   # a library of hundreds: just the summary below
                print(f"  note - {label}: {w}")
    if problems:
        print(f"  {problems} creature(s) left out - fix them in the sheet and run this again.")
    if library:
        from collections import Counter
        for book, n in Counter(c["group"] for c in creatures).most_common():
            print(f"  {n:4d}  {book}")
    credit = str(sheet.get("credit") or f"{title} - imported from {path.name}.")
    return key, {"credit": credit, "creatures": creatures}


# ---------------------------------------------------------------- dedup
# The same creature often comes from more than one source (the SRD and a Monster Manual sheet, an
# index entry and a full stat block). This picks one of each and lists the rest in
# data/monsters-dedup.yml, which the encounter builder leaves out. Nothing is deleted, and a saved
# encounter that uses a hidden copy still works. The same creature = same name, same CR, and from the
# same book (reprints count - an entry lists every book it's in). Another book's version of a creature
# stays, and so do your own campaign and custom creatures, which dedup leaves alone.

DEDUP_FILE = ROOT / "data" / "monsters-dedup.yml"
OPEN_RANK = {"srd": 5, "tob": 4, "tob2": 4, "tob3": 4, "cc": 4}
OPEN_BOOKS = {"srd": "Monster Manual", "tob": "Tome of Beasts", "tob2": "Tome of Beasts 2", "tob3": "Tome of Beasts 3",
              "cc": "Creature Codex"}


# Reprints the monster index doesn't record: a creature in the first book that has the same name and CR
# as one in these books is that one again.
REPRINTS = {"Mordenkainen's Tome of Foes": {"Princes of the Apocalypse", "The Tortle Package"}}


def _books(c: dict) -> set:
    src = c.get("source")
    books = {OPEN_BOOKS[src]} if src in OPEN_BOOKS else set(c.get("books") or [c.get("group") or src])
    return books.union(*(REPRINTS.get(b, set()) for b in books))
INDEX_ONLY = {"vgm", "mtf", "foes"}


def _norm_name(name: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(name).lower().replace("'", "").replace("’", "")).split())


def _dedup_score(c: dict) -> tuple:
    src = c.get("source") or "campaign"
    # a full stat block, then one with its actions but not all its numbers (a hard scan), then AC/HP only
    full = 3 if c.get("abilities") else 2 if c.get("actions") or c.get("traits") else         1 if c.get("ac") is not None and c.get("hp") is not None else 0
    note = str(c.get("note") or "")
    clean = 0 if "scanned page" in note or "To check:" in note else 1
    rank = OPEN_RANK.get(src, 0 if src in INDEX_ONLY else 3)
    return (full, clean, rank, 1 if c.get("environments") else 0)


def dedup() -> None:
    import yaml
    everything = []
    for path in sorted(OUT_DIR.glob("*.json")) + sorted(OUT_DIR.glob("*.yml")):
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.suffix == ".json" else \
                yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and "creatures" in data and "id" not in data:
            data = data["creatures"]
        for c in data if isinstance(data, list) else [data]:
            if isinstance(c, dict) and c.get("id") and c.get("name"):
                if path.suffix == ".yml" or not c.get("source"):
                    continue   # your campaign and custom creatures: never hidden, never hide anything
                everything.append(c)
    groups = {}
    for c in everything:
        groups.setdefault(_norm_name(c["name"]), []).append(c)
    hidden, kept_both = {}, 0
    for same_name in groups.values():
        if len(same_name) < 2:
            continue
        by_cr = {}
        for c in same_name:
            by_cr.setdefault(str(c.get("cr", "")), []).append(c)
        for twins in by_cr.values():
            twins.sort(key=_dedup_score, reverse=True)
            kept = []
            for c in twins:   # best first: each is hidden behind a better copy from the same book, if any
                keep = next((k for k in kept if _books(k) & _books(c)), None)
                if keep:
                    hidden[c["id"]] = keep["id"]
                else:
                    kept.append(c)
            if len(kept) > 1:
                kept_both += 1
    from collections import Counter
    per_source = Counter(next(c.get("source") for c in everything if c["id"] == h) for h in hidden)
    lines = ["# Made by tools/import_monsters.py dedup (it runs after every import) - don't edit; re-run it.",
             "# Duplicate creatures the encounter builder leaves out: hidden id: the copy it shows instead.",
             "# Same name and CR = the same creature; the kept copy is the most complete, cleanest one.",
             "hidden:"] + [f"  {h}: {k}" for h, k in sorted(hidden.items())]
    DEDUP_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    shown = len(everything) - len(hidden)
    print(f"Dedup: {len(everything)} creatures, {len(hidden)} duplicates hidden, {shown} in the builder.")
    for src, n in per_source.most_common():
        print(f"  {n:4d} hidden from {src}")
    if kept_both:
        print(f"  {kept_both} name(s) are different creatures in different books - all kept.")


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="which source to import, or 'file' for a monster sheet")
    ap.add_argument("sheet", nargs="?", help="with 'file': the monster sheet (.json) to import")
    ap.add_argument("--list", action="store_true", help="list available sources")
    args = ap.parse_args()

    if args.list or not args.source:
        print("Available sources:")
        for key, (desc, _) in SOURCES.items():
            print(f"  {key:10s} {desc}")
        return 0
    if args.source == "file":
        if not args.sheet:
            print("Which sheet? For example:  import-monsters \"my creatures.json\"")
            return 1
        key, result = source_sheet(Path(args.sheet))
        out = OUT_DIR / f"{key}.json"
        payload = {"_generated": f"By tools/import_monsters.py file {Path(args.sheet).name} - edit the sheet, not this; re-run to update.",
                   "credit": result["credit"], "creatures": result["creatures"]}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Wrote {len(result['creatures'])} creatures to {out.relative_to(ROOT)}.")
        dedup()
        return 0
    if args.source == "dedup":
        dedup()
        return 0
    if args.source != "all" and args.source not in SOURCES:
        print(f"Unknown source '{args.source}'. Use --list to see the options.")
        return 1

    for key in (SOURCES if args.source == "all" else [args.source]):
        print(f"Importing {key}...")
        result = SOURCES[key][1]()
        out = OUT_DIR / f"{key}.json"
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"_generated": f"By tools/import_monsters.py {key} - do not edit; re-run to update.",
                   "credit": result["credit"], "creatures": result["creatures"]}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Wrote {len(result['creatures'])} creatures to {out.relative_to(ROOT)}")
    dedup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
