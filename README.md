# campaign-codex

A website for running a D&D campaign — your prep, your world, and your table tools in one place — plus a second, safe website for your players that only ever shows what they've come across.

- **This Session**: one page with everything for the next game, opened first at the table.
- **Hover cards everywhere**: write `[[Hester Vane]]` and get a link with a quick card — people, places, factions, items, creatures.
- **Stat blocks, an encounter builder, and an initiative tracker**, with the SRD's creatures built in and your own added as simple data.
- **Character cards** for the party, editable from the browser.
- **A players' site** built from the same files: no prep, no secrets, no stat blocks, and only the people and places they've met — it fills in as you write the Session Log. A leak check stands guard before anything goes online.
- **Optional extras**: private hosting on Cloudflare (free) with a live initiative page for players' phones, and session recording with on-device transcription.

Everything is plain text files on your computer: Markdown pages and YAML data, built with [MkDocs](https://www.mkdocs.org/) and [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). Nothing goes online unless you put it there.

## Quick start

You need **Python 3.10 or newer** (setup installs it on Windows if it's missing).

1. **Download** this repository (green **Code** button → *Download ZIP*, and unzip it), or `git clone` it.
2. **Run setup**:
    - **Windows**: double-click `setup.bat`.
    - **macOS / Linux**: in a terminal, in this folder: `./setup.sh`
3. Setup installs everything into a private `.venv` folder here, then opens the site at <http://127.0.0.1:8000> with a **demo campaign**, *The Lantern Coast*. Have a look around, then read the **Guide** tab.
4. When you're ready, start your own: `codex.bat new` (Windows) or `./codex.sh new` — a few questions, and the demo is replaced with your campaign.

From then on, **`serve`** (`serve.bat` / `./serve.sh`) starts the site whenever you want to work on it.

## Commands

| Windows | macOS / Linux | |
|---|---|---|
| `setup.bat` | `./setup.sh` | install or update (`--with-transcribe` adds session transcription) |
| `serve.bat` | `./serve.sh` | the live site at http://127.0.0.1:8000 |
| `publish.bat` | `./publish.sh` | put both sites online (optional — see the Guide's *Going online*) |
| `codex.bat <command>` | `./codex.sh <command>` | `new`, `build`, `players`, `check`, `add-mentions`, `import-monsters`, `transcribe`, `backup` |

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
[working with an AI assistant](docs/guide/ai-assistant.md) ·
[troubleshooting](docs/guide/troubleshooting.md)

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

The code is [MIT-licensed](LICENSE). The demo campaign is CC BY 4.0. Monster data from the 5e System Reference Document 5.1 is CC BY 4.0 — see [CREDITS.md](CREDITS.md).
