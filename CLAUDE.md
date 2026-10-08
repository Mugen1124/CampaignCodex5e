# Working on this campaign

This folder is a D&D campaign site built with campaign-codex: Markdown pages in `docs/`, YAML data in `data/`, built by MkDocs with the hooks in `hooks/`. There are two sites from the same files: the DM's (`mkdocs.yml`) and the players' (`mkdocs-players.yml`). The guide pages in `docs/guide/` explain everything in detail; this file is the short version for an assistant.

## Golden rules

- **Never leak DM material to the players' site.** Secrets go in `??? dm` boxes, `<!-- players: hide -->` stretches, `dm_only: true` pages, or DM-only data fields (`notes`, `secret`, `dm_notes`). Run `python -m codex check` after changes that touch public text; it must end with "OK - no DM material found".
- **Never publish, delete files, or send anything anywhere without the DM asking.** `publish` puts sites online.
- **Draft first.** For write-ups and anything that changes the story, show the DM a draft and wait for their OK before editing files.
- **Keep the DM's wording** when moving content around. Don't paraphrase prep you're relocating.
- **Use the data's names.** Check `data/` for the canonical spelling of every person, place, faction, and item, and write them as `[[mentions]]`.

## Where things live

- `campaign.yml` — the campaign's settings.
- `docs/index.md` — **This Session**, the home page: `## Now` (where we are, open threads, a DM box), a note box for the next session (arc, starting point, running order, drop-ins), then that session's prep.
- `docs/session-log.md` — the record of play, newest first.
- `docs/arcs/` — storyline prep. While a session is being played its prep lives on This Session; afterward it moves back to its arc (kept word for word), and the arc keeps a short "on This Session" pointer.
- `docs/cities/<town>/` — overview, locations (`{{ locations <town> }}`), people (`{{ npc-list <town> }}`), factions, events (`dm_only: true`).
- `data/npcs/`, `data/locations/`, `data/factions.yml`, `data/items/`, `data/monsters/`, `data/encounters/`, `data/party.yml`, `data/maps.yml`, `data/revealed.yml` — every field is documented in `templates/`.

## Session write-ups (from a transcript)

When the DM asks to write up a session from `recordings/<name>.transcript.txt`:

1. Read the whole transcript. Speakers aren't labeled; names are often misheard — match them to `data/`. **Ask** about anything unclear (who took an item, who did what) instead of guessing.
2. Draft a Session Log entry: `## <Place> — Session N: <Title>`, then a `!!! read-aloud "Previously…"` recap, who was absent, bold scene labels with bullets in the order things happened, an optional **Heard at the table** list of a few fun one-liners (offer candidates; the DM picks; nothing crude, no attribution), and `??? dm` boxes for what the players don't know.
3. **The "Previously…" recap is read aloud and shown to players**: plain, clear prose — short sentences, past tense, second person ("you"), in order, a couple of quoted lines at most, no cryptic or clever phrasing, ending on a simple hook for the next session.
4. Big personal moments get a public scene even if only one character experienced them. Out-of-character information (a patron's real name said only out of character, rules talk) stays in DM boxes.
5. Remember that anything `[[mentioned]]` in the public part of the log appears on the players' site.
6. Also propose: data updates (status changes, new NPCs, items changing hands), moving played prep back into the arc, and a new **Now** section. Make changes only after the DM approves.
7. Recordings and transcripts are private. Suggest deleting them once the DM is happy with the write-up; never delete without being asked.

## Checking your work

- `python -m codex check` — builds both sites and runs the leak check.
- Build warnings worth fixing: unknown `[[mentions]]`, unknown ids in markers, missing required fields, broken links.
- With `serve` running, pages reload as files are saved; changes to `hooks/` need a restart.
