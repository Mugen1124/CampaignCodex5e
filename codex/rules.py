"""
The rules encyclopedia: the SRD 5.1 (data/rules/srd.json, from tools/import_rules.py) as pages and
hover cards. hooks/rules.py renders the page markers; hooks/entities.py registers conditions, spells
and magic items so [[Prone]], [[Fireball]] and [[Bag of Holding]] get hover cards and links.

Page markers (each alone on its own line):
    {{ rules combat-sequence attacking cover }}   rules chapters, by slug, each as a ## section
    {{ conditions }}                              every condition
    {{ spells }}                                  every spell, by level, with a filter
    {{ srd-magic-items }}                         every SRD magic item, with a filter
    {{ rules-credit }}                            the SRD attribution line
"""

import html
import json
import re
from pathlib import Path

DATA = {}            # the loaded srd.json
ROOT = [None]

PAGES = {"condition": "rules/conditions.md", "spell": "rules/spells.md", "srditem": "rules/magic-items.md",
         "rule": "rules/index.md"}
ANCHOR = {"condition": "condition-", "spell": "spell-", "srditem": "srditem-"}

LEVELS = ["Cantrips", "1st level", "2nd level", "3rd level", "4th level", "5th level", "6th level",
          "7th level", "8th level", "9th level"]
ORD = {1: "1st", 2: "2nd", 3: "3rd"}


def load(root: Path) -> dict:
    root = Path(root)
    if ROOT[0] == root and DATA:
        return DATA
    DATA.clear()
    ROOT[0] = root
    f = root / "data" / "rules" / "srd.json"
    if f.is_file():
        DATA.update(json.loads(f.read_text(encoding="utf-8")))
    DATA["_sections"] = {s["slug"]: s for s in DATA.get("sections", [])}
    DATA["_conditions"] = {c["slug"]: c for c in DATA.get("conditions", [])}
    DATA["_spells"] = {s["slug"]: s for s in DATA.get("spells", [])}
    DATA["_items"] = {i["slug"]: i for i in DATA.get("magic_items", [])}
    return DATA


def loaded() -> bool:
    return bool(DATA.get("_sections") or DATA.get("_spells"))


# ---------------------------------------------------------------- text helpers

def condition_names() -> list:
    return [c["name"] for c in DATA.get("conditions", [])]


_COND_RE = [None]


def link_conditions(text: str) -> str:
    """Wrap condition words ("knocked prone", "is restrained") in [[mentions]], so they get hover
    cards. Leaves headings, existing mentions, links, and code alone."""
    names = condition_names()
    if not names:
        return text
    if _COND_RE[0] is None:
        _COND_RE[0] = re.compile(r"(?<![\w\[|-])(" + "|".join(re.escape(n.lower()) for n in names) + r")(?![\w\]-])",
                                 re.I)
    protect = re.compile(r"\[\[[^\]]*\]\]|\[[^\]]*\]\([^)]*\)|`[^`]*`|<[^>]+>|\{[^}]*\}")
    out = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#") or line.lstrip().startswith("|"):
            out.append(line)     # headings, and tables (a "|" in a mention would break the row)
            continue
        pieces, pos = [], 0
        for m in protect.finditer(line):
            pieces.append(_wrap(line[pos:m.start()]))
            pieces.append(m.group(0))
            pos = m.end()
        pieces.append(_wrap(line[pos:]))
        out.append("".join(pieces))
    return "\n".join(out)


def _wrap(chunk: str) -> str:
    def rep(m):
        word = m.group(1)
        name = next(n for n in condition_names() if n.lower() == word.lower())
        return f"[[{name}]]" if word == name else f"[[{name}|{word}]]"
    return _COND_RE[0].sub(rep, chunk)


def demote(text: str, by: int = 1) -> str:
    """Push the chapter's own headings down a level, so they sit under the page's ## heading."""
    def rep(m):
        return "#" * min(6, len(m.group(1)) + by) + " "
    return re.sub(r"(?m)^(#{1,6})\s+", rep, text)


def level_line(s: dict) -> str:
    school = s.get("school", "").lower()
    if s["level"] == 0:
        line = f"{school.capitalize()} cantrip"
    else:
        line = f"{ORD.get(s['level'], str(s['level']) + 'th')}-level {school}"
    return line + (" (ritual)" if s.get("ritual") else "")


def duration(s: dict) -> str:
    d = s.get("duration", "")
    if s.get("concentration") and not d.lower().startswith("concentration"):
        d = "Concentration, " + (d[0].lower() + d[1:] if d else "")
    return d


def components(s: dict) -> str:
    c = s.get("components", "")
    return f"{c} ({s['material'].rstrip('.')})" if s.get("material") and "M" in c else c


def item_line(i: dict) -> str:
    line = f"{i.get('type', '')}, {i.get('rarity', '')}".strip(", ")
    att = i.get("attunement", "")
    if att:
        line += f" ({att})" if att.lower().startswith("requires") else " (requires attunement)"
    return line


def attr(s: str) -> str:
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- page markers

def render_sections(slugs: list) -> str:
    out = []
    for slug in slugs:
        sec = DATA.get("_sections", {}).get(slug)
        if not sec:
            out += [f'!!! failure "Missing rules section"', f"    No section `{slug}` in data/rules/srd.json.", ""]
            continue
        out += [f"## {sec['name']} {{ #rule-{slug} }}", "", link_conditions(demote(sec["text"])), ""]
    return "\n".join(out)


def render_conditions() -> str:
    out = []
    for c in DATA.get("conditions", []):
        out += [f"## {c['name']} {{ #condition-{c['slug']} }}", "", link_conditions(c["text"]), ""]
    return "\n".join(out)


FILTER = """<div class="rules-filter" data-for="{target}" markdown="0">
<input type="search" class="rf-text" placeholder="Filter by name or text…" aria-label="Filter">
{selects}
<span class="rf-count"></span>
</div>
"""


def _select(name: str, label: str, values: list) -> str:
    opts = "".join(f'<option value="{attr(v.lower())}">{html.escape(v)}</option>' for v in values)
    return f'<select class="rf-sel" data-key="{name}" aria-label="{label}"><option value="">{label}: any</option>{opts}</select>'


def render_spells() -> str:
    spells = DATA.get("spells", [])
    classes = sorted({c for s in spells for c in s.get("classes", [])})
    schools = sorted({s.get("school", "") for s in spells if s.get("school")})
    selects = "\n".join([
        _select("level", "Level", ["Cantrip"] + [f"{n}" for n in range(1, 10)]),
        _select("classes", "Class", classes),
        _select("school", "School", schools),
        '<label class="rf-check"><input type="checkbox" data-key="conc"> Concentration</label>',
        '<label class="rf-check"><input type="checkbox" data-key="ritual"> Ritual</label>',
    ])
    out = [FILTER.format(target="spell", selects=selects), ""]
    for lvl in range(0, 10):
        group = [s for s in spells if s["level"] == lvl]
        if not group:
            continue
        out += [f"## {LEVELS[lvl]} {{ #spells-level-{lvl} }}", ""]
        for s in group:
            level_key = "cantrip" if lvl == 0 else str(lvl)
            out += [f'<div class="rules-entry spell" data-name="{attr(s["name"].lower())}" data-level="{level_key}" '
                    f'data-classes="{attr(" ".join(c.lower() for c in s.get("classes", [])))}" '
                    f'data-school="{attr(s.get("school", "").lower())}" data-conc="{int(bool(s.get("concentration")))}" '
                    f'data-ritual="{int(bool(s.get("ritual")))}" markdown>', "",
                    f"### {s['name']} {{ #spell-{s['slug']} }}", "",
                    f"*{level_line(s)}* · {', '.join(s.get('classes', []))}", "",
                    f"**Casting time:** {s.get('casting_time', '')} · **Range:** {s.get('range', '')} · "
                    f"**Components:** {components(s)} · **Duration:** {duration(s)}", "",
                    link_conditions(s["text"]), ""]
            if s.get("higher_level"):
                out += [f"**At higher levels.** {link_conditions(s['higher_level'])}", ""]
            out += ["</div>", ""]
    return "\n".join(out)


def render_items() -> str:
    items = DATA.get("magic_items", [])
    rarities = ["Common", "Uncommon", "Rare", "Very rare", "Legendary", "Artifact", "Varies"]
    types = sorted({i.get("type", "").split(" (")[0].split(",")[0].strip() for i in items if i.get("type")})
    selects = "\n".join([
        _select("rarity", "Rarity", rarities),
        _select("type", "Type", types),
        '<label class="rf-check"><input type="checkbox" data-key="attune"> Needs attunement</label>',
    ])
    out = [FILTER.format(target="srditem", selects=selects), ""]
    letter = None
    for i in items:
        first = i["name"][0].upper()
        if first != letter:
            letter = first
            out += [f"## {letter} {{ #items-{letter.lower()} }}", ""]
        rarity = i.get("rarity", "").lower()
        rarity_key = next((r.lower() for r in rarities if rarity.startswith(r.lower())), "varies")
        if "varies" in rarity:
            rarity_key = "varies"
        out += [f'<div class="rules-entry srditem" data-name="{attr(i["name"].lower())}" data-rarity="{rarity_key}" '
                f'data-type="{attr(i.get("type", "").split(" (")[0].split(",")[0].strip().lower())}" '
                f'data-attune="{int(bool(i.get("attunement")))}" markdown>', "",
                f"### {i['name']} {{ #srditem-{i['slug']} }}", "",
                f"*{item_line(i)}*", "",
                link_conditions(demote(i["text"], 3)), "", "</div>", ""]
    return "\n".join(out)


def credit() -> str:
    return (f"<small>{html.escape(DATA.get('credit', 'Includes material from the System Reference Document 5.1 by '
                                                     'Wizards of the Coast LLC, licensed under CC BY 4.0.'))}</small>")
