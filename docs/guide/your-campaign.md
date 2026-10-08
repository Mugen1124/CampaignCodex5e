# Your campaign

## Start it

Run **`codex new`** (`codex.bat new` on Windows, `./codex.sh new` elsewhere — `setup` also offers it). It asks for:

- your campaign's name,
- the town or city where the story starts,
- your first story arc's name,
- your party: each player, their character, race, and class, and the party's level.

Then it backs everything up, removes the demo, and writes a clean start: a page set for your town, a first arc, an empty Sessions tab, your party, and your names in `campaign.yml`, `mkdocs.yml`, and `mkdocs-players.yml`. Your Style Guide, templates, the guide, and the SRD's monsters stay.

## campaign.yml

The one settings file. The parts you'll touch most:

| Setting | What it's for |
|---|---|
| `name` | Your campaign's name. (The sites' titles are `site_name` in `mkdocs.yml` and `mkdocs-players.yml`.) |
| `default_region` | The heading for factions with no `region:`. |
| `focus` | The town the party is in now (its file name in `data/locations/`). Transcription gives its names first. |
| `banned` | Words that shouldn't appear outside House Rules — the build warns. |
| `skip_mentions` | Names `add-mentions` should never wrap. |
| `maps: base` | Where your map exports live. |
| `online` | Only if you go online — see [Going online](going-online.md). |

## Add a town

1. **Data:** copy `templates/location.yml` to `data/locations/<town>.yml` (lowercase-with-dashes, like `kells-crossing.yml`), and fill in its districts and locations.
2. **Pages:** copy your first town's folder in `docs/cities/` to `docs/cities/<town>/` and change the names inside — each page is a heading and a marker or two (`{{ locations <town> }}`, `{{ npc-list <town> }}`, `{{ factions <town> }}`).
3. **Nav:** add it to `nav:` at the bottom of `mkdocs.yml` (copy your first town's lines), and to `mkdocs-players.yml` without the Events & Hooks line.
4. Mention it on the [Places](../cities/index.md) page.

## Add people, factions, items, creatures

Each kind is a YAML file in `data/` with a template in `templates/` that lists every field:

- **People** — `data/npcs/<town>.yml` (`templates/npc.yml`). `region:` is the town's name; `location:` and `faction:` connect them to places and groups automatically.
- **Factions** — `data/factions.yml` (`templates/faction.yml`).
- **Items** — `data/items/*.yml` (`templates/item.yml`). Who carries what is set on the Items page while `CampaignCodex5e` is running.
- **Creatures** — `data/monsters/*.yml` (`templates/monster.yml`), or build them in the encounter builder's **New creature** form.
- **Encounters** — made in the encounter builder, saved to `data/encounters/`.

[Data files](data-files.md) has the details. Once someone's in the data, write `[[Their Name]]` anywhere for a link with a hover card — or run `codex add-mentions` to wrap every known name on your story pages at once.

## Add an arc

Copy your first arc's page in `docs/arcs/`, rename it, and add it to the Arcs list in `mkdocs.yml`'s `nav:` and on the [Arcs](../arcs/index.md) page. Arcs never appear on the players' site.

## Add maps

Put your map exports (any PNG or JPG — Wonderdraft, Inkarnate, a photo of a sketch) in `maps/`, then list them in `data/maps.yml`. `players: true` puts a map on the players' site too; without it, a map is yours alone. Show one on any page with `{{ map <id> }}`.

## Keep it safe

Your campaign is plain files, so back it up like any folder: `codex backup` makes a dated zip next to this one, and if you use git, commit after each session.
