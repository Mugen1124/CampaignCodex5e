# Changelog

What this fork adds on top of [CampaignCodex5e](https://github.com/Mugen1124/CampaignCodex5e) 1.6.0.
Everything below is in the demo campaign, *The Lantern Coast*, so you can try it straight away.

## Abyss theme

A dark teal-black look for the DM's site and the players' site, in `docs/stylesheets/campaign.css`.

- **Colours:** a deep teal-black page with light grey-blue text, in one palette defined at the top of the file.
- **Fonts:** Cinzel for headings and Alegreya Sans for text, bundled in `docs/fonts/` so the site works offline.
- **Headings:** each `##` section heading has a small diamond in front of it.
- **Boxes:** info boxes, notes and DM boxes have rounded borders. DM boxes are dashed and show a lock icon.
- **Lore pages:** the italic tagline under a title gets a divider with a diamond. An "At a glance" box lines up its labels in a column. A `## Unknown` list becomes a dashed box with diamond bullets.
- **Menus:** the side menu is a framed panel with separators, and regions and towns in the World menu are dropdowns.
- **Record & Transcribe** is an outlined button at the far right of the tab bar, under the search box.
- **Party cards** use the same rounded panels and diamond dividers.
- **Wider pages:** the middle column can be up to 1760px wide, instead of 1440px.

## NPC cards

The NPC Index (`docs/reference/npcs.md`) shows every NPC as a card, grouped by region.

- **On each card:** portrait (or the first letter of the name), race, role, location and faction, a status label (dead, missing, captive…), description, appearance, personality, notes and private theories.
- **One town only:** `{{ npc-cards }}` shows everyone, and `{{ npc-cards <town> }}` shows just one town's people.
- **Side menu:** every NPC's name, by region, under NPC Index.
- **Edit and Add NPC:** these appear while the site runs locally. They save to `data/npcs/`, and portraits to `docs/npc-portraits/`. A backup of the changed file goes to `sources/backups/npcs/` first.
- **Players' site:** players get the engine's own NPC list instead, so notes and secrets never reach it.

Files: `hooks/npc_cards.py`, `docs/javascripts/npc-cards.js`.

## Page editor

A pencil next to each page's title on the DM site edits that page in the browser while the site runs locally.

- **Visual mode:** for session pages, This Session, World and town pages. You type as in a document, no Markdown needed. Boxes like *Previously…* and DM boxes are edited in place, and parts the site fills in show as grey bars.
- **Markdown mode:** for every other page, with a toolbar.
- **Pictures:** pasted or uploaded pictures go to `docs/uploads/`.
- **Safe saving:** every save keeps a backup in `sources/backups/pages/` first, and won't overwrite a page that changed since you opened it.
- **New session** on This Session makes the next session page, with today's date and sections carried over from the last session.
- **Delete session** at the foot of a session page moves it to `sources/backups/deleted/` rather than deleting it.

Files: `hooks/page_editor.py`, `docs/javascripts/page-editor.js`, and the editor libraries in `docs/javascripts/vendor/` (EasyMDE and Toast UI Editor).

## Session dates

- **In the menu:** each session in the Sessions tab shows as "Session 4: The Lighthouse", with its date and time underneath.
- **On the page:** the date appears under the session's title.
- **The date** comes from the page's front matter: `date: 2026-10-12 19:30` (the time is optional).
- **`{{ session-log }}`** lists every session, newest first, with its date, place and the start of its recap.

File: `hooks/session_dates.py`.

## Settings

- **Hooks:** `mkdocs.yml` and `mkdocs-players.yml` list the engine's hooks plus the new ones. If a `codex update` adds a hook to `codex/site.yml` or `codex/site-players.yml`, add it here too.
- **Menu features:** `mkdocs.yml` turns off `navigation.sections` and `navigation.indexes`, so World regions are dropdowns.
- **Tab order:** Record & Transcribe is the last tab, and the theme moves it to the right.

## Credits

`CREDITS.md` lists the fonts (Cinzel and Alegreya Sans, SIL Open Font License, see `docs/fonts/OFL.txt`) and the editor libraries (EasyMDE and Toast UI Editor, MIT).
