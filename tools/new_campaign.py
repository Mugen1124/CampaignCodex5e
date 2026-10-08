r"""
Sets up your own campaign: replaces the demo (The Lantern Coast) with a clean start of yours.

    python -m codex new                     asks a few questions
    python -m codex new --name "Ashes of Varn" --town "Kell's Crossing" \
        --party "Sam:Kestrel:Halfling:Rogue" --party "Ana:Brother Ott:Human:Cleric" --level 1 --yes

It asks for your campaign's name, the town or city the story starts in, and your party, then:
  - makes a backup zip of everything first (next to this folder),
  - removes the demo's pages, data and maps,
  - writes starter pages for your town and a first arc, an empty Sessions tab, your party, and
    campaign.yml / mkdocs.yml / mkdocs-players.yml with your names in them.
The engine (hooks/, tools/, codex/), templates/, the guide, and the SRD monsters are left alone.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codex.settings import slug  # noqa: E402

DOCS, DATA = ROOT / "docs", ROOT / "data"

DEMO_FILES = [
    "docs/sessions/greywater-1.md",
    "data/npcs/greywater.yml", "data/locations/greywater.yml", "data/items/greywater.yml",
    "data/monsters/lantern-coast.yml", "data/encounters/dock-ambush.yml", "data/encounters/bellwether-rite.yml",
    "maps/greywater.png", "maps/bellwether-light.png", "docs/arcs/the-drowned-bell.md",
]
DEMO_DIRS = ["docs/cities/greywater"]


# ---------------------------------------------------------------- questions

def ask(prompt: str, default: str = "") -> str:
    shown = f" [{default}]" if default else ""
    answer = input(f"  {prompt}{shown}: ").strip()
    return answer or default


def ask_party() -> list:
    print("\n  Your party. For each player: their name, their character's name, race, and class.")
    print("  (Leave the player's name empty when you're done.)\n")
    party = []
    while True:
        n = len(party) + 1
        player = ask(f"Player {n}'s name")
        if not player:
            break
        character = ask(f"  {player}'s character") or f"Character {n}"
        race = ask(f"  {character}'s race")
        cls = ask(f"  {character}'s class")
        party.append({"player": player, "character": character, "race": race, "class": cls})
    return party


def parse_party(specs: list) -> list:
    out = []
    for spec in specs:
        parts = (spec.split(":") + ["", "", "", ""])[:4]
        out.append({"player": parts[0].strip(), "character": parts[1].strip() or parts[0].strip(),
                    "race": parts[2].strip(), "class": parts[3].strip()})
    return out


# ---------------------------------------------------------------- writing

def write(rel: str, text: str):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8", newline="\n")


def set_yaml_value(text: str, key: str, value: str) -> str:
    """Replace a top-level `key: value` line, keeping its comment."""
    def rep(m):
        return f"{key}: {value}{m.group(2)}"
    new, n = re.subn(rf"(?m)^{re.escape(key)}:[^\n#]*?(\s*#.*)?$",
                     lambda m: f"{key}: {value}" + ((" " + m.group(1).strip()) if m.group(1) else ""), text, count=1)
    return new if n else text + f"\n{key}: {value}\n"


def q(s: str) -> str:
    """A YAML-safe scalar."""
    return yaml.safe_dump(s, default_flow_style=True, allow_unicode=True).strip().removesuffix("...").strip()


def campaign_yml(name: str, town: str, town_id: str):
    path = ROOT / "campaign.yml"
    s = path.read_text(encoding="utf-8")
    s = set_yaml_value(s, "name", q(name))
    s = set_yaml_value(s, "tagline", q(""))
    s = set_yaml_value(s, "default_region", q(town))
    s = set_yaml_value(s, "focus", town_id)
    s = set_yaml_value(s, "skip_mentions", "[]")
    s = re.sub(r'(?m)^(  intro: ).*$', lambda m: m.group(1) + q(f"A Dungeons & Dragons session, in {town}."), s, count=1)
    path.write_text(s, encoding="utf-8", newline="\n")


def nav_dm(town: str, town_id: str, arc: str, arc_id: str) -> str:
    return f"""nav:
  - Sessions: []          # filled in by hooks/sessions.py: This Session, then each session, newest first
  - Record & Transcribe: recording.md
  - Party: party/index.md
  - World:
      - world/index.md
      - Factions: world/factions.md
      - Maps: maps/index.md
      - Places: cities/index.md
      - {q(town)}:
          - cities/{town_id}/index.md
          - Locations: cities/{town_id}/locations.md
          - People: cities/{town_id}/people.md
          - Factions: cities/{town_id}/factions.md
          - Events & Hooks: cities/{town_id}/events.md
  - Arcs:
      - arcs/index.md
      - {q(arc)}: arcs/{arc_id}.md
  - Encounters: encounters/index.md
  - Rules:
      - rules/index.md
      - House Rules: world/house-rules.md
      - DM Screen: rules/dm-screen.md
      - Conditions: rules/conditions.md
      - Combat: rules/combat.md
      - Abilities & checks: rules/abilities.md
      - Adventuring: rules/adventuring.md
      - Spellcasting: rules/spellcasting.md
      - Spells: rules/spells.md
      - Magic Item Rules: rules/magic-item-rules.md
      - Magic Items: rules/magic-items.md
      - Equipment: rules/equipment.md
      - Characters: rules/characters.md
      - Monsters, NPCs & planes: rules/more.md
  - Reference:
      - Bestiary: reference/bestiary.md
      - Items: reference/items.md
      - NPC Index: reference/npcs.md
      - Style Guide: reference/style-guide.md
  - Guide:
      - guide/index.md
      - Your campaign: guide/your-campaign.md
      - Writing pages: guide/writing-pages.md
      - Data files: guide/data-files.md
      - At the table: guide/at-the-table.md
      - The players' site: guide/players-site.md
      - Going online: guide/going-online.md
      - Recording sessions: guide/recording.md
      - Working with Claude: guide/ai-assistant.md
      - Troubleshooting: guide/troubleshooting.md
"""


def nav_players(town: str, town_id: str) -> str:
    return f"""nav:
  - Sessions: []          # filled in by hooks/sessions.py: each session, newest first (the home page is the latest)
  - Initiative: players/tracker.md
  - My Notes: players/notes.md
  - Party:
      - party/index.md
      - About this site: players/about.md
      - People: reference/npcs.md
      - Items: reference/items.md
  - World:
      - world/index.md
      - Factions: world/factions.md
      - Maps: maps/index.md
      - Places: cities/index.md
      - {q(town)}:
          - cities/{town_id}/index.md
          - Locations: cities/{town_id}/locations.md
          - People: cities/{town_id}/people.md
          - Factions: cities/{town_id}/factions.md
  - Rules:
      - rules/index.md
      - House Rules: world/house-rules.md
      - DM Screen: rules/dm-screen.md
      - Conditions: rules/conditions.md
      - Combat: rules/combat.md
      - Abilities & checks: rules/abilities.md
      - Adventuring: rules/adventuring.md
      - Spellcasting: rules/spellcasting.md
      - Spells: rules/spells.md
      - Magic Item Rules: rules/magic-item-rules.md
      - Magic Items: rules/magic-items.md
      - Equipment: rules/equipment.md
      - Characters: rules/characters.md
      - Monsters, NPCs & planes: rules/more.md
"""


def mkdocs_yml(name: str, town: str, town_id: str, arc: str, arc_id: str):
    for file, title, nav in (("mkdocs.yml", f"{name} — DM", nav_dm(town, town_id, arc, arc_id)),
                             ("mkdocs-players.yml", f"{name} — Players", nav_players(town, town_id))):
        path = ROOT / file
        s = path.read_text(encoding="utf-8")
        s = re.sub(r"(?m)^site_name:.*$", lambda m: f"site_name: {q(title)}", s, count=1)
        s = s[:s.index("\nnav:\n") + 1] + nav
        path.write_text(s, encoding="utf-8", newline="\n")


def party_yml(party: list, level: int):
    lines = ["# The party. Encounters use level and size for their difficulty math.",
             "# Fill in each card with Edit on the Party page while CampaignCodex5e is running (every field is listed",
             "# in templates/character.yml). email: (optional) is the address a player signs in to the",
             "# players' site with - only needed if you put it online. Emails never appear on any page.",
             f"level: {level}", f"size: {len(party)}", "members:"]
    for p in party:
        fields = ", ".join(f"{k}: {q(p[k])}" for k in ("player", "character", "race", "class") if p.get(k))
        lines.append(f"  - {{{fields}}}")
    if not party:
        lines[-1] = "members: []"
    write("data/party.yml", "\n".join(lines) + "\n")


def pages(name: str, town: str, town_id: str, arc: str, arc_id: str, party: list, level: int):
    write("data/locations/" + town_id + ".yml", f"""
# {town}'s locations, split into districts. Numbers match the pins on your town map.
# Fields: see templates/location.yml. NPCs aren't listed here - each NPC's location: puts them
# under "Found here" automatically.

id: {town_id}
name: {q(town)}
page: cities/{town_id}/locations.md
districts:
  - name: The Old Quarter
    blurb: Replace this district with your own.
    locations:
      - id: the-first-inn
        number: 1
        name: The First Inn
        subtitle: Where the story starts
        description: >
          Every campaign needs an inn. Rename this one, describe it, and add the places around it.
""")
    write("data/npcs/" + town_id + ".yml", f"""
# {town}'s people. Fields: see templates/npc.yml.

- id: the-innkeeper
  name: The Innkeeper
  region: {q(town)}
  role: Runs the First Inn
  location: the-first-inn
  hook: Rename them, give them a voice, and give them something they want.
""")
    write("data/factions.yml", "# Factions. Fields: see templates/faction.yml.\n[]\n")
    write("data/items/" + town_id + ".yml", "# Items found around " + town + ". Fields: see templates/item.yml.\n[]\n")
    write("data/monsters/" + slug(name) + ".yml",
          "# Your own creatures. Fields: see templates/monster.yml. (The SRD's are already in the builder.)\n[]\n")
    write("data/maps.yml", """
# Maps shown on the site. Put your map exports in the maps/ folder (campaign.yml: maps: base:),
# then list them here. players: true also puts a map on the players' site.

maps: []
#  - id: town
#    players: true
#    group: Town
#    title: The town
#    source: town.png
""")
    write("data/revealed.yml", """
# What the players have come across that no session page mentions. See the guide
# (The players' site). Use the names you'd write in a [[mention]].
reveal: []
hide: []
names_ok: []
""")
    party_yml(party, level)

    table = "\n".join(f"| {p['player']} | {p['character']} | {p['race']} | {p['class']} | {level} |" for p in party)
    write("docs/party/index.md", f"""
# Party

| Player | Character | Race | Class | Level |
|---|---|---|---|:-:|
{table}

## Character cards

{{{{ party-cards }}}}

<!-- players: hide -->
## Personal hooks

- One line per character: what ties them to the story.
<!-- players: end -->

## Backgrounds

""" + "\n".join(f"### {p['character']}\n\nA few lines from {p['player']}.\n" for p in party))

    write("docs/index.md", f"""
# This Session

The page to open first at the table: where things stand, then everything for the next session. Once it's played, what was prepped moves back into its arc, and what actually happened gets its own page under **Sessions** (see the Style Guide: Session pages).

## Now

### Where we are

The party is about to arrive in **{town}**.

### Open threads

- The first thread of the story.

!!! note "Session 1 — {town}"
    **Arc:** [{arc}](arcs/{arc_id}.md) · **Starting point:** where the story opens.

    **Running order:** the opening → the first scene → the first choice.

    **If the table wanders:** drop-ins on [Events & Hooks](cities/{town_id}/events.md).

## Opening

!!! read-aloud "Read aloud"
    The first thing your players hear. Set the scene in a few sentences.

## The first scene

What happens, who's there, and what they want.
""")
    write("docs/players/about.md", f"""
# About this site

The players' side of {name}: what's happened, who you've met, and where you've been. It grows as the story does.

- **Sessions** — a page for every session played, newest first. The site opens on the latest one.
- **[Initiative](tracker.md)** — follow the fight from your phone while the DM runs it.
- **[My Notes](notes.md)** — your own notepad. Only you can read it; it saves as you type.
- **[Party](../party/index.md)** — the characters, with their cards and backgrounds.
- **[People](../reference/npcs.md)** — everyone the party has met.
- **[Items](../reference/items.md)** — the party's notable finds.
- **[World](../world/index.md)** — the world, its places, the factions you've come across, and the maps.
- **[Rules](../rules/index.md)** — the house rules, then the game's rules, searchable.

Names with a dotted underline show a short reminder when you hover over them, and link to more.
""")
    write("docs/world/index.md", f"""
# {name}

*A one-line tagline for your world.*

What every character knows about the world: its shape, its powers, its troubles. Keep it short —
the details live on each place's pages.

<!-- players: hide -->
??? dm "DM only — the world's secret"
    What the players don't know yet.
<!-- players: end -->
""")
    write("docs/cities/index.md", f"""
# Places

The towns and places of the campaign.

- **[{town}]({town_id}/index.md)** — where the story starts.
""")
    write(f"docs/cities/{town_id}/index.md", f"""
# {town}

*A one-line tagline.*

What the place is, in a paragraph.

## Districts

- **The Old Quarter** — one line each.

## Who holds power

Who runs it, and who would like to.

## Arrival

!!! read-aloud "Arriving in {town}"
    What the party sees as they come in.

<!-- players: hide -->
??? dm "DM only — secrets"
    What's really going on here.
<!-- players: end -->
""")
    write(f"docs/cities/{town_id}/locations.md", f"""
---
toc_depth: 2
---

# {town} — Locations

Numbers match the pins on the map. Each location lists the people found there.

{{{{ locations {town_id} }}}}
""")
    write(f"docs/cities/{town_id}/people.md", f"# {town} — People\n\n{{{{ npc-list {town_id} }}}}\n")
    write(f"docs/cities/{town_id}/factions.md", f"# {town} — Factions\n\n{{{{ factions {town_id} }}}}\n")
    write(f"docs/cities/{town_id}/events.md", f"""
---
dm_only: true
---

# {town} — Events & Hooks

Drop-in scenes for when the table wanders off the plan. (This page never appears on the players' site.)

## A first drop-in

Something small that can happen anywhere in {town}.
""")
    write("docs/arcs/index.md", f"""
# Arcs

Story arcs: the prep for each storyline, scene by scene. While a session is being played, its prep lives on [This Session](../index.md); afterward it comes back here.

- **[{arc}]({arc_id}.md)** — the first storyline.
""")
    write(f"docs/arcs/{arc_id}.md", f"""
---
regions: [{q(town)}]
---

# {arc}

*One line: what this arc is about.*

## Overview

The situation, the people behind it, and what happens if the party does nothing.

## Scene 1 — The Hook

How the party gets pulled in.
""")
    guide = DOCS / "guide" / "index.md"
    if guide.is_file():   # the welcome page's tour of the demo
        g = guide.read_text(encoding="utf-8")
        g = re.sub(r"<!-- demo:.*?<!-- /demo -->\n*", "", g, flags=re.S)
        guide.write_text(g, encoding="utf-8", newline="\n")
    families = DATA / "families.yml"
    if families.is_file():
        s = families.read_text(encoding="utf-8")
        i = s.find("# ---------------------------------------------------------------- the demo campaign")
        if i >= 0:
            families.write_text(s[:i].rstrip() + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Set up your own campaign (replaces the demo).")
    ap.add_argument("--name")
    ap.add_argument("--town")
    ap.add_argument("--arc")
    ap.add_argument("--party", action="append", default=[], help='"Player:Character:Race:Class" (repeatable)')
    ap.add_argument("--level", type=int)
    ap.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    interactive = not (args.name and args.town)
    print("\n  Set up your own campaign\n  ------------------------")
    print("  This replaces the demo campaign (The Lantern Coast) with a clean start of yours.\n")
    name = args.name or ask("Your campaign's name", "My Campaign")
    town = args.town or ask("The town or city where the story starts", "Millbrook")
    arc = args.arc or (ask("Your first story arc's name", "The First Adventure") if interactive else "The First Adventure")
    party = parse_party(args.party) if args.party else (ask_party() if interactive else [])
    level = args.level or (int(ask("The party's level", "1") or 1) if interactive else 1)
    town_id, arc_id = slug(town) or "town", slug(arc) or "first-arc"

    if not args.yes:
        print(f"\n  Campaign: {name}\n  Starting town: {town}\n  First arc: {arc}\n  Party: "
              + (", ".join(f"{p['character']} ({p['player']})" for p in party) or "none yet") + f", level {level}")
        if ask("\nReplace the demo with this? (y/n)", "y").lower()[:1] != "y":
            print("  Nothing changed.")
            return 1

    if not args.no_backup:
        print("\n  Backing up first...")
        subprocess.call([sys.executable, str(ROOT / "tools" / "backup.py")], cwd=ROOT)

    for rel in DEMO_FILES:
        (ROOT / rel).unlink(missing_ok=True)
    for rel in DEMO_DIRS:
        shutil.rmtree(ROOT / rel, ignore_errors=True)
    for f in (DATA / "encounters").glob("*.yml"):
        if (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("id") in ("dock-ambush", "bellwether-rite"):
            f.unlink()

    campaign_yml(name, town, town_id)
    mkdocs_yml(name, town, town_id, arc, arc_id)
    pages(name, town, town_id, arc, arc_id, party, level)
    print(f"""
  Done - {name} is ready.

  Next:
    - Start CampaignCodex5e (or keep it running) and open http://127.0.0.1:8000
    - Read the Guide tab: "Your campaign" walks through adding places, people, and sessions.
    - Fill in the character cards with Edit on the Party page.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
