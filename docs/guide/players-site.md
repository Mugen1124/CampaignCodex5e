# The players' site

A second site, built from the same files by `mkdocs-players.yml`, for your players: the session pages, the party, the people and places they've met, the items they've found, the maps you've shared, and a live initiative page. It never contains your prep, your secrets, or anything they haven't come across.

## What players see

A person, place, faction, or item shows on the players' site when **any** of these is true:

- it's `[[mentioned]]` in the **public part of a session page** (not inside a DM box or a hidden stretch),
- a character carries it (items with a `holder:`),
- it's listed under `reveal:` in `data/revealed.yml`,
- its own data says `revealed: true`.

And it's kept off, whatever the above says, if its data says `revealed: false` or it's under `hide:` in `data/revealed.yml`.

So the players' site **fills in by itself as you write up each session**. Their NPC entries show only the hook, appearance, and personality — never notes or secrets.

## What's always left out

- **Whole pages:** anything listed in `exclude_docs` in `mkdocs-players.yml` (This Session, the arcs, encounters, the guide, the Bestiary, the Style Guide) and any page with `dm_only: true` at the top.
- **Inside pages:** `!!! dm` and `??? dm` boxes, `warning` boxes, `<!-- players: hide -->` stretches, and every `<!-- comment -->`.
- **From data:** stat blocks, encounters, DM notes and secrets, DM-only maps (any map without `players: true`), and links to anything players can't see (they become plain text).

## When the players know something different

- `player_hook:` on an NPC replaces their hook on the players' site — for when the real hook gives the game away.
- `player_location: ""` hides where someone is (a captive, someone in hiding); or name the place the players believe.

## The leak check

`codex check` (and `publish`, before every upload) builds the players' site and searches it for anything from your DM boxes, secrets, notes, DM-only pages and maps, and players' emails. If it finds any, it lists them and **publish won't upload the players' site** until they're fixed. It also lists, for review, names of people the party hasn't met that still appear in page text — fine if you meant it (add them to `names_ok:` in `data/revealed.yml`), otherwise hide that text.

## Its menu

The players' site has its own `nav:` in `mkdocs-players.yml`. When you add a town, add its pages there too (without Events & Hooks).

## Looking at it

`codex players` builds the players' site and opens it in your browser, so you can see exactly what they'll see. `codex check` builds both sites and runs the leak check without opening anything.
