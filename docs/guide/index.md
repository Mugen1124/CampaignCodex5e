# Welcome

**campaign-codex** is a website for running a tabletop campaign — your prep, your world, and your table tools in one place — plus a second, stripped-down website for your players that only ever shows what they've come across.

Everything lives as plain text files in this folder: Markdown pages in `docs/`, and data (people, places, creatures, items, encounters) in `data/`. The site is built from those files on your own computer. Nothing goes online unless you choose to put it there.

## The two sites

**Your DM site** (this one) has everything: the prep, the secrets, stat blocks, the encounter builder and initiative tracker, and these guide pages.

**The players' site** is built from the same files, minus everything that's yours alone: DM boxes, secrets, stat blocks, prep pages, and anyone or anything the party hasn't come across yet. It fills in by itself as you write the [Session Log](../session-log.md). See [The players' site](players-site.md).

<!-- demo: the setup wizard (new) removes everything from here to the end marker -->
## What's here right now

You're looking at a small **demo campaign**, *The Lantern Coast* — a fishing town, a stolen bell, and a drowned cult. It uses every feature, so poke around:

- **[This Session](../index.md)** — the page you open at the table: where things stand, then the next session's prep.
- **[Session Log](../session-log.md)** — what happened at the table, newest first.
- **[Party](../party/index.md)** — character cards. With `serve` running, **Edit** fills them in.
- **[Places → Greywater](../cities/greywater/index.md)** — a town's overview, locations (with who's found where), people, and factions.
- **[Arcs → The Drowned Bell](../arcs/the-drowned-bell.md)** — a storyline's prep, scene by scene.
- **[Encounters](../encounters/index.md)** — the encounter builder and initiative tracker.
- **[Reference → Style Guide](../reference/style-guide.md)** — every kind of box, marker, and card, live.

Hover any name with a dotted underline for a quick card.
<!-- /demo -->

## The commands

Each is a script in this folder: double-click the `.bat` on Windows, or run the `.sh` in a terminal on macOS and Linux (`./serve.sh`). Anything without its own script runs through `codex`: `codex.bat backup`, `./codex.sh backup`.

| Command | What it does |
|---|---|
| `setup` | One-time install (run it again to update). Offers to start your own campaign. |
| `serve` | The live site at <http://127.0.0.1:8000>. Updates as you save files. Leave its window open. |
| `codex new` | Replaces the demo with your own campaign — see [Your campaign](your-campaign.md). |
| `codex build` | A copy in `site/` you can open straight from disk, no server needed. |
| `codex players` | Builds the players' site and opens it — see what they'll see. |
| `codex check` | Builds both sites and runs the leak check — a quick "is everything OK?". |
| `publish` | Puts both sites online, if you've set that up — see [Going online](going-online.md). |
| `codex add-mentions` | Wraps every known name on your story pages in `[[mentions]]`. |
| `import-monsters` | Adds monsters: the SRD's are already in; also Kobold Press's open books, or your own sheet. |
| `transcribe` | Turns a session recording into a transcript — see [Recording sessions](recording.md). |
| `codex backup` | A dated zip of everything that's yours. |

## How a campaign runs here

1. **Prep** goes on [This Session](../index.md): the scenes, read-alouds, encounters, and stat blocks for next time, all on one page.
2. **Play** from that page. Run fights from [Encounters](../encounters/index.md).
3. **Afterward**, write what happened in the [Session Log](../session-log.md), and move the played prep back into its arc. The players' site picks up everyone and everything the log mentions.

[At the table](at-the-table.md) walks through it.
