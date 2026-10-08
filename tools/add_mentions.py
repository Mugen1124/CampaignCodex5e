r"""
Add [[mentions]] around known names in story pages, so they get hover cards.

Names come from the data files: NPCs, locations, factions, items, and creatures.
Full names are always used; one-word aliases are used unless they're on the
skip_mentions list in campaign.yml. Longer names win ("Gull & Lantern Inn" before "Gull").

Left alone: headings, admonition titles, {{ markers }}, front matter, code,
existing [[mentions]], Markdown links, and HTML. The site's first-mention rule
decides which marked names actually become links.

    python tools/add_mentions.py            # mark every story page
    python tools/add_mentions.py --dry-run  # show counts only, change nothing

Each changed page is backed up to sources\backups\ first.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DATA = ROOT / "data"

sys.path.insert(0, str(ROOT))
from codex import settings as codex_settings  # noqa: E402

CAMPAIGN = codex_settings.load(ROOT)

# Pages it never touches: generated reference pages, the players' own pages, tool pages.
SKIP_PAGES = ("reference/", "players/", "encounters/", "maps/", "recording.md")

# Names never marked automatically - campaign.yml's skip_mentions (standard rulebook items,
# one-word names that are also ordinary words, and so on).
SKIP_NAMES = set(CAMPAIGN.get("skip_mentions") or [])
SKIP_WORDS = SKIP_NAMES


def story_pages() -> list:
    """Every page under docs/ except the generated and tool pages."""
    return [p.relative_to(DOCS).as_posix() for p in sorted(DOCS.rglob("*.md"))
            if not p.relative_to(DOCS).as_posix().startswith(SKIP_PAGES)]


def _city_names() -> dict:
    out = {}
    for path in sorted((DATA / "locations").glob("*.yml")):
        city = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        out[str(city.get("id") or path.stem)] = str(city.get("name") or path.stem)
    return out


MENTION = re.compile(r"\[\[[^\]]*\]\]")
CURRENT_REGIONS = None
PROTECT = re.compile(
    r"\[\[[^\]]*\]\]"            # existing mentions
    r"|!?\[[^\]]*\]\([^)]*\)"    # Markdown links and images
    r"|`[^`]*`"                  # inline code
    r"|<[^>]+>"                  # HTML tags
    r"|\{[^}]*\}"                # attribute lists { .class }
)


def _as_list(v):
    return v if isinstance(v, list) else ([] if v is None else [v])


def load_names() -> dict:
    """{text to find: name to put in the mention}"""
    names = {}

    def add(text, target, alias=False, region=None):
        text = str(text or "").strip()
        if not text or text in SKIP_NAMES:
            return
        # Names written "The X" are matched without "The" so the article stays in the prose.
        bare = re.sub(r"^The\s+", "", text)
        if alias and " " not in bare and (bare in SKIP_WORDS or len(bare) < 3):
            return
        if '"' in bare or "(" in bare:
            return
        # Only one-word NPC names are limited to their own region.
        names.setdefault(bare, (target, region if " " not in bare else None))

    for path in sorted((DATA / "npcs").glob("*.yml")):
        for n in _as_list(yaml.safe_load(path.read_text(encoding="utf-8"))):
            add(n.get("name"), n.get("name"), region=n.get("region"))
            for a in _as_list(n.get("aliases")):
                add(a, n.get("name"), alias=True, region=n.get("region"))
    for path in sorted((DATA / "locations").glob("*.yml")):
        city = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for d in city.get("districts", []):
            for loc in d.get("locations", []):
                add(loc.get("name"), loc.get("name"))
                for a in _as_list(loc.get("aliases")):
                    add(a, loc.get("name"), alias=True)
    fpath = DATA / "factions.yml"
    if fpath.exists():
        for f in _as_list(yaml.safe_load(fpath.read_text(encoding="utf-8"))):
            add(f.get("name"), f.get("name"))
            for a in _as_list(f.get("aliases")):
                add(a, f.get("name"), alias=True)
    for path in sorted((DATA / "items").glob("*.yml")):
        for i in _as_list(yaml.safe_load(path.read_text(encoding="utf-8"))):
            add(i.get("name"), i.get("name"))
    claimed = set()
    for path in sorted((DATA / "npcs").glob("*.yml")):
        for n in _as_list(yaml.safe_load(path.read_text(encoding="utf-8"))):
            if n.get("statblock"):
                claimed.add(n["statblock"])
    for path in sorted((DATA / "monsters").glob("*.yml")):
        for m in _as_list(yaml.safe_load(path.read_text(encoding="utf-8"))):
            # Imported creatures (SRD etc.) have common names like "Guard" - never auto-marked.
            if str(m.get("id") or path.stem) not in claimed and not m.get("source"):
                add(m.get("name"), m.get("name"))
    return names


def build_pattern(names: dict):
    alts = sorted(names, key=len, reverse=True)
    return re.compile(r"(?<![\w\[])(" + "|".join(re.escape(a) for a in alts) + r")(?![\w\]])")


def page_regions(rel: str, text: str = ""):
    """Which regions a page is about, so one-word names ("Hester") only match their own region's NPCs.
    A city's pages (cities/<id>/...) are that city; any page can say so itself in its front matter:
        ---
        regions: [Greywater, The Marsh]
        ---
    Anything else: one-word names match regardless of region."""
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if m:
        front = yaml.safe_load(m.group(1)) or {}
        if front.get("regions"):
            return set(front["regions"] if isinstance(front["regions"], list) else [front["regions"]])
    parts = rel.split("/")
    if len(parts) > 2 and parts[0] == "cities":
        return {_city_names().get(parts[1], parts[1])}
    return None


def mark_line(line: str, pattern, names) -> tuple:
    """Wrap names in one line, skipping protected spans. Returns (line, count)."""
    out, pos, count = [], 0, 0
    for p in PROTECT.finditer(line):
        chunk = line[pos:p.start()]
        new, c = _mark_chunk(chunk, pattern, names)
        out += [new, p.group(0)]
        count += c
        pos = p.end()
    new, c = _mark_chunk(line[pos:], pattern, names)
    out.append(new)
    return "".join(out), count + c


def _mark_chunk(text, pattern, names):
    count = 0

    def rep(m):
        nonlocal count
        found = m.group(1)
        target, region = names[found]
        if region and CURRENT_REGIONS and region not in CURRENT_REGIONS:
            return found  # a one-word name from another region - probably someone else
        count += 1
        # Mention by the full name; show the text exactly as written. (For "the Gull & Lantern"
        # that means [[The Gull & Lantern|Gull & Lantern]] - the article stays in the prose.)
        return f"[[{target}]]" if target == found else f"[[{target}|{found}]]"

    return pattern.sub(rep, text), count


# An earlier version wrote "the [[The Gull & Lantern]]", which reads "the The Gull & Lantern".
DOUBLED = re.compile(r"\b([Tt]he)( \*\*| _| )\[\[The ([^\]|]+)\]\]")


def repair_doubled(text: str) -> tuple:
    return DOUBLED.subn(lambda m: f"{m.group(1)}{m.group(2)}[[The {m.group(3)}|{m.group(3)}]]", text)


def mark_page(text: str, pattern, names) -> tuple:
    text, repaired = repair_doubled(text)
    lines, total = text.split("\n"), repaired
    in_front = lines[:1] == ["---"]
    fence = False
    for i, line in enumerate(lines):
        s = line.strip()
        if in_front:
            if i > 0 and s == "---":
                in_front = False
            continue
        if s.startswith("```"):
            fence = not fence
            continue
        if (fence or s.startswith("#") or s.startswith("{{") or s.startswith("<!--")
                or re.match(r"^(!!!|\?\?\?\+?)\s", s) or s.startswith("|---")):
            continue
        lines[i], c = mark_line(line, pattern, names)
        total += c
    return "\n".join(lines), total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("pages", nargs="*", help="pages under docs/ (default: every story page)")
    args = ap.parse_args()

    global CURRENT_REGIONS
    names = load_names()
    pattern = build_pattern(names)
    backup = ROOT / "sources" / "backups"
    grand = 0
    for rel in (args.pages or story_pages()):
        path = DOCS / rel
        if not path.exists():
            print(f"  skipped (not found): {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        CURRENT_REGIONS = page_regions(rel, text)
        new, count = mark_page(text, pattern, names)
        grand += count
        if count and not args.dry_run:
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup / rel.replace("/", "__"))
            path.write_text(new, encoding="utf-8")
        print(f"  {count:4d} names marked  {rel}")
    print(f"\n{'Would mark' if args.dry_run else 'Marked'} {grand} names in total"
          f"{' (nothing changed)' if args.dry_run else '; originals are in sources/backups/'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
