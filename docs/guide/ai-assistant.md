# Working with Claude

**Optional.** Everything here can be done by hand. But a campaign here is plain text files with clear conventions, so an AI assistant that can read and edit files — such as [Claude Code](https://claude.com/claude-code) — can do a lot of the busywork for you: writing up sessions, adding towns and people, building encounters, importing monsters, even changing how the site looks. This page is about Claude; other assistants that can edit files work much the same way.

## Getting started

1. **Install Claude Code** — the desktop app, or the `claude` command in a terminal (see <https://claude.com/claude-code>).
2. **Open this folder** in it (the one with `campaign.yml`). Claude reads `CLAUDE.md` here automatically: the house rules for this project — where things live, how session pages are written, and what never to do (publish without asking, put secrets where players can see them).
3. **Start `CampaignCodex5e`** as usual. Pages reload as Claude saves files, so you can watch changes appear at <http://127.0.0.1:8000>.
4. **Have a way back.** Run `codex backup` (or use git) before big changes, so nothing is more than one step from undone.

## How to ask

- **Say what you want, and where.** "Add a tavern to Kell's Crossing" beats "add a tavern". Name the page or file if you know it.
- **Paste your notes.** Rough bullet points are fine — Claude turns them into the site's format and asks about anything missing.
- **Ask for a draft first** when it matters: *"Draft it and show me before changing anything."* Claude does this by default for write-ups and story changes.
- **Keep your words.** When moving prep around, Claude keeps your wording. If you want it rewritten, say so.
- **Ask it to check.** *"Run the check"* builds both sites and runs the leak check, so you know nothing secret reached the players' site.

## Write up a session

The whole path from the table to the players' site:

1. **Record** on the [Record & Transcribe](../recording.md) tab, with your table's OK (see [Recording sessions](recording.md)).
2. **Transcribe**: press **Transcribe** there, or ask:
    > *"Transcribe the newest recording."*
3. **Write it up**:
    > *"Write up the session from recordings/Session 2026-10-04 1900.transcript.txt."*

    You get a draft session page — a "Previously…" recap, what happened in order, a few lines from the table, and DM boxes for what the players don't know — plus a list of suggested updates: who died or moved, new people met, items that changed hands, a new **Now** section. Claude asks when the transcript is unclear (who took the sword? who read the scroll?) instead of guessing.
4. **Read the draft, then approve it:**
    > *"Looks good — but Mara kept the key, not Tomas. Go ahead and make the changes."*
5. **Tidy up:**
    > *"Move the played prep from This Session back into the arc, and set up Now for next session."*

    > *"Delete the recording and transcript."* — only once you're happy; they're raw table talk.

Along the way:

- *"Make the Previously… recap simpler — short sentences, in order."*
- *"Offer me five fun one-liners from the transcript for Heard at the table."*
- *"Which names in this session aren't in our data yet?"*

## Prep the next session

- *"Set up This Session for session 5: the party goes to the lighthouse. Use the scenes from the arc page, in this order: …"*
- *"Add a read-aloud for arriving at the lighthouse at dusk, about four sentences."*
- *"Put the stat blocks for this session's fights on This Session."*
- *"What open threads haven't come up in the last three sessions?"*

## Build your world

**Towns and places**

- *"Add a new town, Kell's Crossing: a river town with a ferry, a market, and a ruined watchtower. Make its pages and add it to the World menu on both sites."*
- *"Add these locations to Kell's Crossing:"* (paste a list)
- *"The party is in Kell's Crossing now — make it the focus town."*

**People**

- *"Add these NPCs from my notes:"* (paste them) — Claude puts them in the right town, links their locations and factions, and warns you about names that are easy to confuse at the table.
- *"Give Hester Vane a secret: she's paying the smugglers."* Secrets never reach the players' site.
- *"Mark Oren Hask as dead."*

**Factions and items**

- *"Add a faction, the Tidewardens: harbor guards on the take. Leader: Oren Hask."*
- *"Add a magic item, the Lantern of the Drowned, held by Kestra."*
- *"Who's carrying what? List the party's notable items."*

## The party

- *"Import Tam's new level from this file:"* (give the `.ccc5e` file from CCC5e) — Claude shows what changes first, and keeps the player, email, your note and anything marked private.
- *"Add a character for Sam: Pell, a level 3 gnome wizard, AC 12, 16 HP, with Fire Bolt and Magic Missile."* — no CCC5e needed; any field can be typed in.
- *"Mark Pell's backstory and his letter from home private."* — the other players won't see them; you still do.
- *"Add a DM note to Tam's card: she still owes Pip twenty gold."* — never on the players' site.
- *"Get the players' changes from the Party page."* — brings what players changed on their own cards online into `data/party.yml`. Claude does this before editing a card, so nobody's edit is lost.

## Monsters and encounters

- *"Import the Tome of Beasts monsters."* — an open book from Kobold Press; `import-monsters --list` shows the others.
- *"Make a stat block for a reef hag — CR 4, like a sea hag but tougher, with a drowning curse."*
- *"I own this book; add these creatures from my notes for my own table:"* (paste them) — they stay in your data, never copied onto public pages.
- *"Build a hard encounter for the party at the lighthouse: cultists and something from the sea."* — Claude checks the difficulty against the party's levels.
- *"Put that encounter on This Session."*

## The players' site

- *"What can the players see about Hester Vane?"*
- *"Reveal the Tidewardens to the players."* / *"Keep the cult hidden until I say."*
- *"Show me the players' site."* — builds it and opens it.
- *"Run the check."* — if the leak check finds DM material on the players' site, Claude shows you where and fixes it.

## Change the site itself

The site is yours to change, and Claude can do it in small, safe steps:

- *"Make the read-aloud boxes a darker blue."*
- *"Add a page for our homebrew crafting rules under Rules."*
- *"Add a new kind of box for weather, like the read-aloud box."*
- *"Rename the Arcs tab to Storylines."*
- *"Add a field for each NPC's voice notes, shown only on the DM site."*

Changes to colors, pages, and menus show up as soon as they're saved. Changes to the engine (`hooks/`) need `CampaignCodex5e` restarted — Claude will tell you.

## Keep things healthy

- *"Run the check and fix anything it finds."*
- *"Wrap all the names on my story pages in mentions."* — runs `add-mentions`.
- *"There's a warning when the site starts:"* (paste it) *"— what does it mean?"*
- *"Back everything up."*
- *"Publish."* — Claude only puts anything online when you ask, and stops if a site doesn't ask for a sign-in.

## Make CLAUDE.md yours

`CLAUDE.md` is plain text. Add your own preferences and Claude follows them from then on — for example:

- *"Write the Previously… recaps in the voice of an old ship's captain."*
- *"Call the gods 'the Bright Ones' in anything the players see."*
- *"Always ask before adding new NPCs."*
- *"Remind me on This Session when someone hasn't had a spotlight scene in a while."*

## Good habits

- **Review before it's installed.** Ask for a draft, read it, then let it make the change.
- **Keep the recap readable.** The "Previously…" box is read aloud and shown to players: short sentences, in order, no clever phrasing.
- **Check names.** Transcripts mishear names; make sure the write-up uses the ones in your data.
- **Watch what becomes public.** Anything mentioned in the public part of a session page appears on the players' site. Secrets go in DM boxes.
- **Keep recordings private,** and delete them once the write-up is done.
