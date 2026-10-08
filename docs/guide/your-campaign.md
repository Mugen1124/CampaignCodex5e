# Your campaign

## Start it

Run setup again and answer **Y** to "Set up your own campaign now?" — or run **`codex new`** (`codex.bat new` on Windows, `./codex.sh new` elsewhere). It asks for:

- your campaign's name,
- the town or city where the story starts,
- your first story arc's name,
- your party: each player, their character, race, and class, and the party's level.

Then it backs everything up, removes the demo, and writes a clean start: a page set for your town, a first arc, an empty Sessions tab, your party, and your names in `campaign.yml`, `mkdocs.yml`, and `mkdocs-players.yml`. Your Style Guide, templates, the guide, and the SRD's monsters stay.

**Run it once.** Running it again replaces your campaign's starting files (This Session, the party, factions, maps, menus) with fresh ones. The backup it makes first goes in the `<folder>-backups` folder next to this one.

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
| `output` | Where built sites and caches go: `here` (in this folder) or `local` (on this computer, outside it). Use `local` if this folder is in Google Drive, Dropbox, OneDrive or iCloud, so the cloud only holds your own files. |
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

## Keep up to date

When a new version of CampaignCodex5e comes out, run **`codex update`** (`codex.bat update` on Windows, `./codex.sh update` elsewhere). It shows what will change and asks first, makes a backup, replaces the engine — the code, the guide, the Rules tab, the scripts — and then checks that both sites still build. `codex version` says which version you're on.

Your campaign is never touched: your pages, data, maps, menus (`mkdocs.yml`, `mkdocs-players.yml`), `campaign.yml`, `docs/stylesheets/campaign.css`, `README.md`, and `CLAUDE.md`. The engine's files are listed in `codex/engine-files.txt`; if you'd changed one of those yourself, update tells you, and your version is in the backup. To change how the site looks, use `campaign.css` rather than the engine's `extra.css`, so your changes survive updates.

**Coming from 1.3 or earlier?** Download the new release's zip, copy its `codex` folder into your campaign (replacing yours), then run `codex update --zip <the zip you downloaded>`. It turns your old `mkdocs.yml` into the new kind — your name and menus, with everything else from the engine — and keeps the old one beside it.
