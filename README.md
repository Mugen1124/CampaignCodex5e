# CampaignCodex5e

A website for running a D&D campaign — your prep, your world, and your table tools in one place — plus a second, safe website for your players that only ever shows what they've come across.

- **This Session**: one page with everything for the next game, opened first at the table.
- **Hover cards everywhere**: write `[[Hester Vane]]` and get a link with a quick card — people, places, factions, items, creatures.
- **Stat blocks, an encounter builder, and an initiative tracker**, with the SRD's creatures built in and your own added as simple data.
- **A rules encyclopedia**: the whole 5e SRD — conditions, combat, adventuring, spellcasting, every spell and magic item, equipment — searchable, with a one-page DM Screen. `[[Prone]]` or `[[Fireball]]` anywhere gets a hover card, and so do conditions in the initiative tracker.
- **Character cards** for the party, editable from the browser.
- **A players' site** built from the same files: no prep, no secrets, no stat blocks, and only the people and places they've met — it fills in as you write up each session. A leak check stands guard before anything goes online.
- **Optional extras**: private hosting on Cloudflare (free) with a live initiative page for players' phones, and session recording with on-device transcription.

Everything is plain text files on your computer: Markdown pages (text with simple formatting, like `**bold**`) and YAML data (simple `name: value` lists), built into a website with [MkDocs](https://www.mkdocs.org/) and [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). Nothing goes online unless you put it there.

## Quick start

**What you need:** **Python 3.10 or newer**.

- **Windows:** nothing — setup installs Python if it's missing.
- **macOS:** the Python that comes with macOS is too old. Install the latest from <https://www.python.org/downloads/> first.
- **Linux:** usually already there; on Debian/Ubuntu also `sudo apt install python3-venv`.

Nothing else, unless you later put the sites online (Node.js) or record sessions (ffmpeg) — the guide covers those when you get there.

1. **Download** this repository (green **Code** button → *Download ZIP*), and unzip it somewhere you'll keep it — your campaign lives in this folder.
2. **Run setup**:
    - **Windows**: double-click `setup.bat`.
    - **macOS / Linux**: open **Terminal**, type `cd ` (with a space after it), drag the folder into the window, press Return, then type `bash setup.sh` and press Return.
3. The first run takes a few minutes: it installs what the site needs into a private `.venv` folder inside this one (nothing else on your computer changes). Then it asks **"Set up your own campaign now?"** — answer **N** the first time to explore the **demo campaign**, *The Lantern Coast*. The site opens in your browser at <http://127.0.0.1:8000>. Have a look around, then read the **Guide** tab.
4. When you're ready, start your own: run setup again and answer **Y** (or run `codex.bat new` / `./codex.sh new`). It asks a few questions and replaces the demo with your campaign. Do this once — running it again starts over.

If anything goes wrong, see [Troubleshooting](docs/guide/troubleshooting.md).

From then on, **`CampaignCodex5e`** starts the site whenever you want to work on it: double-click `CampaignCodex5e.bat` (Windows) or `CampaignCodex5e.command` (Mac), or run `./CampaignCodex5e.sh` (Linux).

## Commands

| Windows | macOS / Linux | |
|---|---|---|
| `setup.bat` | `./setup.sh` | install or update (`--with-transcribe` adds session transcription) |
| `CampaignCodex5e.bat` | `CampaignCodex5e.command` (Mac) · `./CampaignCodex5e.sh` (Linux) | start the site at http://127.0.0.1:8000 |
| `publish.bat` | `./publish.sh` | put both sites online (optional — see the Guide's *Going online*) |
| `codex.bat <command>` | `./codex.sh <command>` | `serve`, `new`, `build`, `players`, `check`, `publish`, `add-mentions`, `import-monsters`, `import-rules`, `transcribe`, `backup` |

## The guide

The full guide is part of the site itself — the **Guide** tab, or the Markdown files in [`docs/guide/`](docs/guide/):
[welcome](docs/guide/index.md) ·
[your campaign](docs/guide/your-campaign.md) ·
[writing pages](docs/guide/writing-pages.md) ·
[data files](docs/guide/data-files.md) ·
[at the table](docs/guide/at-the-table.md) ·
[the players' site](docs/guide/players-site.md) ·
[going online](docs/guide/going-online.md) ·
[recording sessions](docs/guide/recording.md) ·
[working with Claude](docs/guide/ai-assistant.md) ·
[troubleshooting](docs/guide/troubleshooting.md)

## Working with Claude

A campaign here is plain text with clear conventions, so an AI assistant that can edit files — such as [Claude Code](https://claude.com/claude-code) — can do much of the busywork: write up a session from a recording, add a town or a batch of NPCs, build encounters, import monsters, even change how the site looks. [Working with Claude](docs/guide/ai-assistant.md) has the prompts that work well, and `CLAUDE.md` tells the assistant the house rules.

## How it's put together

| Folder / file | |
|---|---|
| `campaign.yml` | your campaign's settings — the one file that makes it yours |
| `docs/` | the pages (Markdown) |
| `data/` | people, places, factions, items, creatures, encounters, the party, maps (YAML) |
| `maps/` | your map exports |
| `templates/` | a blank, commented example of every kind of data |
| `mkdocs.yml`, `mkdocs-players.yml` | the two sites' structure and menus |
| `hooks/` | the engine: turns data and markers into pages, and strips the players' site |
| `tools/` | the save helper, leak check, monster importer, transcriber, and the rest |
| `codex/` | the commands behind the scripts |

## Keeping your campaign private

Your campaign is full of secrets. If you keep it in git and push it anywhere, make that repository **private**. Never host the DM site anywhere public — the Guide's *Going online* sets it up behind a sign-in, and `publish` checks that it stays that way.

## License

The code is [MIT-licensed](LICENSE). The demo campaign is CC BY 4.0. Monster and rules data from the 5e System Reference Document 5.1 is CC BY 4.0 — see [CREDITS.md](CREDITS.md).
