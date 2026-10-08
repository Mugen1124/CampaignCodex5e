# Working on this campaign

This folder is a D&D campaign site built with CampaignCodex5e: Markdown pages in `docs/`, YAML data in `data/`, built by MkDocs with the hooks in `hooks/`. There are two sites from the same files: the DM's (`mkdocs.yml`) and the players' (`mkdocs-players.yml`). The guide pages in `docs/guide/` explain everything in detail; this file is the short version for an assistant.

## Golden rules

- **Never leak DM material to the players' site.** Secrets go in `??? dm` boxes, `<!-- players: hide -->` stretches, `dm_only: true` pages, or DM-only data fields (`notes`, `secret`, `dm_notes`). Run the check after changes that touch public text (`codex.bat check` on Windows, `./codex.sh check` elsewhere; or `.venv/Scripts/python -m codex check` / `.venv/bin/python -m codex check`); the leak check must say "OK - no DM material found" and the run ends with "All good."
- **Never publish, delete files, or send anything anywhere without the DM asking.** `publish` puts sites online.
- **Draft first.** For write-ups and anything that changes the story, show the DM a draft and wait for their OK before editing files.
- **Keep the DM's wording** when moving content around. Don't paraphrase prep you're relocating.
- **Use the data's names.** Check `data/` for the canonical spelling of every person, place, faction, and item, and write them as `[[mentions]]`.

## Where things live

- `campaign.yml` — the campaign's settings.
- `docs/index.md` — **This Session**, the home page: `## Now` (where we are, open threads, a DM box), a note box for the next session (arc, starting point, running order, drop-ins), then that session's prep.
- `docs/sessions/` — the record of play: one page per session, each starting with `order: N` front matter and a `# <Place> — Session N: <Title>` heading. The Sessions tab lists them automatically, newest first.
- `docs/arcs/` — storyline prep. While a session is being played its prep lives on This Session; afterward it moves back to its arc (kept word for word), and the arc keeps a short "on This Session" pointer.
- `docs/cities/<town>/` — overview, locations (`{{ locations <town> }}`), people (`{{ npc-list <town> }}`), factions, events (`dm_only: true`).
- `docs/rules/` — the SRD rules encyclopedia (from `data/rules/srd.json`); conditions, spells and SRD magic items can be `[[mentioned]]` for hover cards.
- `data/npcs/`, `data/locations/`, `data/factions.yml`, `data/items/`, `data/monsters/`, `data/encounters/`, `data/party.yml`, `data/maps.yml`, `data/revealed.yml` — every field is documented in `templates/`.

## Session write-ups (from a transcript)

When the DM asks to write up a session from `recordings/<name>.transcript.txt`:

1. Read the whole transcript. Speakers aren't labeled; names are often misheard — match them to `data/`. **Ask** about anything unclear (who took an item, who did what) instead of guessing.
2. Draft a new session page, `docs/sessions/<place>-<n>.md`: `order:` one higher than the last session's, `# <Place> — Session N: <Title>`, then a `!!! read-aloud "Previously…"` recap, who was absent, bold scene labels with bullets in the order things happened, an optional **Heard at the table** list of a few fun one-liners (offer candidates; the DM picks; nothing crude, no attribution), and `??? dm` boxes for what the players don't know.
3. **The "Previously…" recap is read aloud and shown to players**: plain, clear prose — short sentences, past tense, second person ("you"), in order, a couple of quoted lines at most, no cryptic or clever phrasing, ending on a simple hook for the next session.
4. Big personal moments get a public scene even if only one character experienced them. Out-of-character information (a patron's real name said only out of character, rules talk) stays in DM boxes.
5. Remember that anything `[[mentioned]]` in the public part of a session page appears on the players' site.
6. Also propose: data updates (status changes, new NPCs, items changing hands), moving played prep back into the arc, and a new **Now** section. Make changes only after the DM approves.
7. Recordings and transcripts are private. Suggest deleting them once the DM is happy with the write-up; never delete without being asked.

## Common jobs

- **A new town:** `templates/location.yml` → `data/locations/<town>.yml`; pages in `docs/cities/<town>/` (copy an existing town's set); add them to `nav:` in both `mkdocs.yml` and `mkdocs-players.yml` under World. Set `focus:` in `campaign.yml` if the party is there now.
- **NPCs, factions, items:** follow `templates/npc.yml`, `faction.yml`, `item.yml`; ids are lowercase-with-dashes. Check new names against existing ones and warn the DM about names that are easy to confuse at the table.
- **Monsters:** SRD creatures are already in (`srd-` ids). `codex import-monsters <source>` adds open books (`--list` shows them); a creature from a book the DM owns goes in `data/monsters/*.yml` (format in `templates/monster.yml`) — only for the DM's own table, never copied into public text.
- **Encounters:** `data/encounters/<id>.yml`, shown with `{{ encounter <id> }}`; check the difficulty against the party in `data/party.yml`.
- **Prep:** the next session's material goes on This Session (`docs/index.md`) under its note box. After play, move it back to the arc word for word and leave a pointer.
- **Changing the site itself:** the DM's own colors and styles go in `docs/stylesheets/campaign.css` (never `extra.css`); menus are `nav:` in both `mkdocs*.yml` (which hold only names and menus - engine settings are in `codex/site.yml` / `site-players.yml`); behavior is in `hooks/`. Files listed in `codex/engine-files.txt` are replaced by `codex update`, so the DM's own changes belong elsewhere when possible; if an engine file must change, tell the DM it'll need redoing after an update (restart the site after editing those). Keep changes small, and run the check.

## Checking your work

- `codex.bat check` / `./codex.sh check` — builds both sites and runs the leak check; changes nothing.
- Build warnings worth fixing: unknown `[[mentions]]`, unknown ids in markers, missing required fields, broken links.
- With `CampaignCodex5e` running, pages reload as files are saved; changes to `hooks/` need a restart.
