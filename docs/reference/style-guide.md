---
toc_depth: 2
---

# Style Guide

The rules every page follows, each with a live example. Examples here are rendered by the same system as the rest of the site, so this page is always accurate. The [Guide](../guide/index.md) explains how to use all of it; this page is the quick reference.

## Page structure

- **One H1**: the page title, and nothing else at that level.
- **H2 for major sections** — a district, a faction, a scene, a room, a session part. These are what the right-hand contents lists.
- **H3 for the parts inside them**, H4 only when truly needed. Never deeper.
- **Long reference pages** (NPC Index, Factions, Items) limit the right-hand contents to their main sections with a setting at the very top of the page:

        ---
        toc_depth: 2
        ---

- **Bold** is for labels and lead-ins only — "**Purpose:**", "**Tactics:**", a name starting a line. Never for emphasis mid-sentence.
- *Italics* are for dialogue, subtitles, and asides.

## Read-aloud and DM text

!!! read-aloud "Read aloud"
    The road drops out of the fog and there's the town all at once: grey roofs stacked up a hill, and over the door of an inn by the harbor, a lantern burning in broad daylight.

Written as `!!! read-aloud "Read aloud"` with the text indented underneath.

!!! dm "DM note"
    The informant sells the same tip to the other side an hour later — no need to show this at the table.

Written as `!!! dm "DM note"`. Guidance you'll want visible while running the scene.

??? dm "DM only — what the villain wants"
    Something the players don't know yet.

Written as `??? dm "DM only — ..."` — folded away until clicked. Use it for secrets and spoilers. Both kinds of DM box are removed from the players' site.

!!! warning "Needs decision"
    Something waiting on your call. Also removed from the players' site.

## Mentions and hover cards

Any NPC, location, faction, item, or creature in the data can be mentioned by name in double brackets, and becomes a link with a hover card:

| You write | You get |
|---|---|
| `[[Hester Vane]]` | an NPC's name, with their hover card |
| `[[The Gull & Lantern]]` | a location |
| `[[The Greywater Watch]]` | a faction |
| `[[Tidewalker Boots]]` | an item, with its full rules on hover |
| `[[Goblin]]` | [[Goblin]] — a creature, with a combat card |

To show different text, add it after a bar: `[[Hester Vane|Hester]]` shows as "Hester" but links to Hester Vane.

- **Only the first mention in each H2 section becomes a link**; later mentions of the same thing in that section are plain text. That keeps busy paragraphs readable.
- **Headings and read-aloud boxes are always plain text**, even if a name inside them is marked.
- **A misspelled or unknown name** shows with a red wavy underline and a warning in the serve window.
- `add-mentions` wraps every known name on your story pages for you.

## NPCs

Each NPC is an entry in a file in `data/npcs/` (one file per region is tidy). Their full entry lives on the [NPC Index](npcs.md); everywhere else they appear as a mention. An entry shows, in order:

- The name, then an italic line: race · role · where they're found · faction, plus a status badge if they're not alive (captive, dead, missing).
- A one- or two-sentence **hook** (or a longer **description**) — who they are at a glance. The hook, plus **personality**, is what the hover card shows.
- Optional **Appearance**, **Personality**, and **Notes**.
- A link to their stat block, if they have one.
- **Secrets** folded under "DM only" — never on the hover card.

Required: name, region, role, hook. Blank template: `templates/npc.yml`.

## Place pages

Every town or city has the same pages, in this order in the sidebar (a village can keep them all on one page, in the same order):

- **Overview** — `cities/<town>/index.md`: an italic one-line tagline; what the place is, in a paragraph; its districts, one line each; **Who holds power**; an **Arrival** read-aloud; secrets in DM boxes.
- **Locations** — the numbered map (`{{ map <id> }}`), then `{{ locations <town> }}`.
- **People** — `{{ npc-list <town> }}`.
- **Factions** — `{{ factions <town> }}`: the factions whose `region:` is that town.
- **Events & Hooks** — drop-in scenes, if the place has any. Mark it `dm_only: true` at the top.

## Locations

Each town is one file in `data/locations/`, split into districts. A location shows its map number and name, an italic subtitle, the description, any features and labeled sections, then **Found here** — built automatically from every NPC whose `location:` points there — and any DM notes or secrets, folded.

Required: name, description. Blank template: `templates/location.yml`.

## Factions

All factions are in `data/factions.yml` and render on the [Factions](../world/factions.md) page, grouped by `region:` (none means `default_region` in `campaign.yml`), and on each town's own Factions page: summary, structure, goals, details, then **Members** — built automatically from every NPC whose `faction:` points there, leader first.

Required: name, summary. Blank template: `templates/faction.yml`.

## Items

Items are in `data/items/` and render on the [Items](items.md) page. An item always carries its **complete rules text**; the hover card shows it in full. Each entry shows type, rarity, attunement, where it was found, flavor, rules, and who holds it once known.

Required: name, type, rarity, text. Blank template: `templates/item.yml`.

## Stat blocks

Creatures are data files in `data/monsters/` and appear on the [Bestiary](bestiary.md) automatically. A page shows one with a marker on its own line — `{{ statblock srd-goblin }}` — which renders as:

{{ statblock srd-goblin }}

Your own creatures use the id you gave them (`{{ statblock bog-lurker }}`); the SRD's start with `srd-`. The encounter builder shows every creature's id.

## Character cards

Each character in `data/party.yml` has a card in the stat block style — gold rules instead of red, so players and monsters are easy to tell apart at a glance. Cards are filled in with **Edit** on the [Party](../party/index.md) page (or by hand; every field is listed in `templates/character.yml`), and show on the Party page and beside the list in the initiative tracker on that character's turn. The marker `{{ party-card kestrel }}` shows one card (the name written as in the card's link on the Party page), and `{{ party-cards }}` shows them all.

## Encounters

Encounters are data files in `data/encounters/`: creatures and counts, plus where the encounter happens. The marker `{{ encounter example-goblins }}` renders the roster and difficulty against the party in `data/party.yml`:

{{ encounter example-goblins }}

Every encounter is also listed on the [Encounters](../encounters/index.md) tab, where you can build new ones.

## Session Log entries

The [Session Log](../session-log.md) is the record of play, newest first, one H2 per session:

- **Heading:** where and which session, then a short title — `## Greywater — Session 1: The Missing Bell`.
- **"Previously…"** (optional): a `!!! read-aloud "Previously…"` recap, ready to read at the start of the next session. Plain, clear prose: short sentences, in order, second person.
- **What happened:** bullets in the order it happened, with bold lead-ins for scenes. Names as `[[mentions]]`; the players' characters by name.
- **Heard at the table** (optional): a few favorite one-liners.
- **What the players don't know yet** goes last, folded away: `??? dm "DM only — where this leaves things"`.

Anything mentioned in the public part of the log shows up on the players' site — that's how the People, Places and Items pages there fill in as the campaign goes.

## Maps

Maps are listed in `data/maps.yml`, pointing at your original exports; the site makes web-sized copies automatically. The marker `{{ map greywater }}` shows one, and clicking opens it full screen. `{{ maps }}` shows every map, grouped — that's the Maps page.

## Tabs

For places that exist in two versions, or alternatives side by side:

=== "Low tide"

    The causeway is dry, slick with weed, and walkable in twenty minutes.

=== "High tide"

    The causeway is under four feet of black water. The lighthouse is an island.

Markers and mentions work inside tabs and folded boxes too — indent them like any other content there.

## Build checks

Every time the site builds, it warns (in the serve window) about:

- a missing required field on any NPC, location, faction, or item
- an NPC pointing at a location, faction, or stat block that doesn't exist
- an unknown `[[mention]]`, or a link to a page or section that doesn't exist
- **similar NPC names** that could be confused at the table — pairs kept on purpose are listed in `data/checks.yml`
- any word listed under `banned:` in `campaign.yml`, outside the [House Rules](../world/house-rules.md)
