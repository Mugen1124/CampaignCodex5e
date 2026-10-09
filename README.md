# CampaignCodex5e

A website for running a D&D campaign — your prep, your world, and your table tools in one place — plus a second, safe website for your players that only ever shows what they've come across.

- **This Session**: one page with everything for the next game, opened first at the table.
- **Hover cards everywhere**: write `[[Hester Vane]]` and get a link with a quick card — people, places, factions, items, creatures.
- **Stat blocks, an encounter builder, and an initiative tracker**, with the SRD's creatures built in and your own added as simple data.
- **A rules encyclopedia**: the whole 5e SRD — conditions, combat, adventuring, spellcasting, every spell and magic item, equipment — searchable, with a one-page DM Screen. `[[Prone]]` or `[[Fireball]]` anywhere gets a hover card, and so do conditions in the initiative tracker.
- **[Character cards](#the-party-page)** for the party: a full card per character — stats, attacks, features, spells, inventory, persona and backstory — imported from the Custom Character Creator 5e (CCC5e) or typed in, with fields players can keep private.
- **A players' site** built from the same files: no prep, no secrets, no stat blocks, and only the people and places they've met — it fills in as you write up each session. A leak check stands guard before anything goes online.
- **Optional extras**: private hosting on Cloudflare (free) with a live initiative page for players' phones, [a live Party page](#the-party-page) players keep up themselves (their own cards, current HP and conditions, spell slots and hit dice, a shared party treasury), and a private notepad for each player; and [session recording with on-device transcription](#recording-and-transcribing-sessions) that turns into a ready-to-read recap.

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
| `codex.bat <command>` | `./codex.sh <command>` | `serve`, `new`, `build`, `players`, `check`, `publish`, `add-mentions`, `import-monsters`, `import-character`, `import-rules`, `transcribe`, `backup`, `update`, `version` |

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

## The Party page

One full-width card per character: AC, HP, speed, initiative and Passive Perception across the top, ability scores and saves, skills, then Actions, Features & traits, Spellcasting, Inventory, and Persona & backstory — tiles at the top of the page jump to each one.

- **Import from CCC5e.** Export a character from the Custom Character Creator 5e (CCC5e) and import the `.ccc5e` file — on the Party page, or with `codex import-character`. You see what will change first; import again after a level-up.
- **Or type it in.** **Edit** is a full form, with a live preview: everything an import fills in, spells and inventory included.
- **Private fields.** A bond, a backstory, an item in the pack — the other players don't see it; you do.

**With the players' site online, the Party page is live.** Each player edits or imports their own card and chooses what's private; everyone sees the changes as they happen. At the table, each card carries its current HP (with temporary HP, and death saves when it hits 0), conditions, inspiration, spell slots and hit dice, with Damage, Heal, Short rest and Long rest. Your initiative tracker starts fights from the party's current HP and keeps the cards up to date as you go. A shared **party treasury** keeps the coin and loot, with a log of who took what.

You keep the say: **History** on each card shows every change, with **Undo**; current HP stays private unless you let the players see each other's; and **Get players' changes** brings their edits into your files. See [the players' site](docs/guide/players-site.md#the-party-page) in the guide.

## Recording and transcribing sessions

**Optional, and only with your table's OK.** Record the session at the table, turn the recording into a written transcript on your own computer, then turn the transcript into the session's page — with a "Previously…" recap ready to read aloud next time. Nothing is uploaded anywhere: the speech recognition runs on your computer.

### Set it up (once)

1. Run setup with transcription: `setup.bat --with-transcribe` (Windows, from a terminal in the folder) or `bash setup.sh --with-transcribe`. It installs [faster-whisper](https://github.com/SYSTRAN/faster-whisper), an open-source version of OpenAI's Whisper speech recognition. The speech model itself (about 1.6 GB) downloads the first time you transcribe.
2. Install **ffmpeg**, which reads the browser's recordings: `winget install ffmpeg` (Windows) or `brew install ffmpeg` (Mac), or from <https://ffmpeg.org>.

### Record

With `CampaignCodex5e` running, open the **Record & Transcribe** tab in Chrome or Edge.

- **Pick the microphone** and watch the level meter while people talk. One microphone in the middle of the table, set to pick up all around (a USB conference or podcast mic), works best.
- **Record.** The audio is saved every few seconds, so a crash or a closed tab loses seconds, not the session.
- **⧉ Pop out** moves the recorder into a small window of its own, so you can use the rest of the site while it records; a **● REC** light shows on every page.
- Recordings go in the `recordings/` folder in your campaign (or wherever **Browse…** points, or `recordings:` in `campaign.yml`). That folder is never built, published, or committed to git.

You can also transcribe a recording made any other way — a phone, a voice recorder, Discord: `.m4a`, `.mp3`, `.wav`, `.flac`, `.ogg`, `.webm`, `.aac`, or `.wma`. Put it in `recordings/`.

### Transcribe

Press **Transcribe** next to a recording on the same tab, and leave the site running — it shows its progress, and takes a while (longer on slower computers). Or from a terminal: `codex.bat transcribe` / `./codex.sh transcribe` for the newest recording, or name a file. On Windows you can drag a recording onto `transcribe.bat`.

It writes `<recording>.transcript.txt` next to the recording, one line per stretch of speech with its time:

```
[01:23:45] I search the captain's desk.
[01:23:51] You find a ledger, and a key on a red cord.
```

What makes it better than a plain transcription:

- **Your names, spelled right.** Before it starts, it's given your campaign's names — the party, the people and places of the town in `focus:` (in `campaign.yml`), factions, items — so it writes *Hester Vane*, not *Hester Bane*. `transcribe --vocab-only` shows the list.
- **Fights, in order.** If you ran the initiative tracker during the recording, its turn log (rounds, whose turn it was, conditions, who joined or left the fight) is woven into the transcript at the right times, marked ⚔.
- **Loot, noticed.** Lines where someone seems to take one of your campaign's items ("Tam grabs the Tidewalker Boots") are collected; the **Items** page lists them for you to assign or dismiss. Nothing changes hands by itself.

Speakers aren't labeled — it's one microphone — so the write-up works out who said what from context.

### From transcript to recap

Write the session's page yourself from the transcript — or let an AI assistant draft it. With [Claude Code](https://claude.com/claude-code) open in this folder (it reads `CLAUDE.md`, which explains the write-up format):

> *"Write up the session from recordings/Session 2026-10-04 1900.transcript.txt."*

You get a **draft**, nothing changed yet:

- a new session page for the **Sessions** tab, with a **"Previously…" recap** written to be read aloud at the start of next session — short sentences, in order, "you", ending on a simple hook;
- what happened, scene by scene, with names as `[[mentions]]`;
- a few favorite lines from the table to choose from;
- DM boxes for what the players don't know yet;
- suggested updates: who died or moved, new people met, items that changed hands, and a new **Now** section for This Session.

Claude asks where the transcript is unclear (who took the sword? who read the scroll?) instead of guessing. Read the draft, correct it, and approve:

> *"Good — but Tam kept the boots, not Kaelen. Go ahead."*

Other prompts that help:

- *"Make the Previously… recap simpler — short sentences, in order."*
- *"Write the recap from Ilvara's point of view."*
- *"Offer me five one-liners from the transcript for the session page."*
- *"Which names in the transcript aren't in our data yet?"*
- *"What did the party promise people this session? List the loose threads."*

Remember that everyone and everything mentioned in the public part of a session page appears on the **players' site** — that's how it fills in. Secrets go in DM boxes.

### Afterward

Transcripts are raw table talk. Keep them private, and **delete the recording and transcript once the session's page is written**, unless everyone at the table is happy to keep them. (*"Delete the recording and transcript"* works too.)

More in the guide: [Recording sessions](docs/guide/recording.md) and [Working with Claude](docs/guide/ai-assistant.md).

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
| `mkdocs.yml`, `mkdocs-players.yml` | the two sites' names and menus |
| `docs/stylesheets/campaign.css` | your own colours and styles |
| `hooks/` | the engine: turns data and markers into pages, and strips the players' site |
| `tools/` | the save helper, leak check, monster and character importers, transcriber, and the rest |
| `publish/players/` | the players' site's worker: the live initiative page, the live Party page, item claims, and each player's notes |
| `codex/` | the commands behind the scripts, and the engine's site settings (`site.yml`, `site-players.yml`) |

Everything that's the engine is listed in `codex/engine-files.txt`, and **`codex update`** keeps it current from new releases without touching anything of yours — see *Keep up to date* in the guide's [Your campaign](docs/guide/your-campaign.md#keep-up-to-date). If your campaign folder is in Google Drive, Dropbox, OneDrive or iCloud, set `output: local` in `campaign.yml` so built sites and caches stay on your computer.

## Keeping your campaign private

Your campaign is full of secrets. If you keep it in git and push it anywhere, make that repository **private**. Never host the DM site anywhere public — the Guide's *Going online* sets it up behind a sign-in, and `publish` checks that it stays that way.

## License

The code is [MIT-licensed](LICENSE). The demo campaign is CC BY 4.0. Monster and rules data from the 5e System Reference Document 5.1 is CC BY 4.0 — see [CREDITS.md](CREDITS.md).
