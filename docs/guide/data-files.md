# Data files

Everything that's a *thing* in your world — a person, a place, a creature — lives as data in `data/`, written in YAML. The site turns it into pages, hover cards, and the encounter builder's lists, so you write each thing once.

## Where everything lives

| File or folder | Holds | Template |
|---|---|---|
| `data/npcs/*.yml` | people, one file per town is tidy | `templates/npc.yml` |
| `data/locations/<town>.yml` | a town's districts and locations | `templates/location.yml` |
| `data/factions.yml` | factions | `templates/faction.yml` |
| `data/items/*.yml` | magic items and notable loot | `templates/item.yml` |
| `data/monsters/*.yml` | your own creatures | `templates/monster.yml` |
| `data/monsters/*.json` | imported creatures (the SRD and others) — made by `import-monsters`, don't edit | |
| `data/encounters/*.yml` | encounters (made in the encounter builder) | |
| `data/party.yml` | the party and their character cards | `templates/character.yml` |
| `data/maps.yml` | your maps | |
| `data/revealed.yml` | extra things the players know about | |
| `data/families.yml` | which creatures belong together, for the encounter generator | |
| `data/checks.yml` | similar names you're keeping on purpose | |
| `data/rules/srd.json` | the Rules tab: the SRD's rules, conditions, spells, and magic items — made by `codex import-rules`, don't edit | |

## YAML in two minutes

```yaml
- id: hester-vane             # a list entry starts with "- "
  name: Hester Vane           # key: value
  aliases: [Hester, the innkeeper]    # a short list
  hook: >                     # long text: ">" then indented lines (joined into one paragraph)
    Broad, freckled, and unshockable.
  text: |                     # "|" keeps line breaks as written
    First paragraph.

    Second paragraph.
```

- **Indentation is two spaces**, never tabs, and it matters.
- **Quote text that contains a colon followed by a space**, or starts with `*`, `[`, `{`, or `"`: `text: "*Melee Weapon Attack:* +5 to hit"`.
- If a file has a mistake, the `CampaignCodex5e` window says which file and roughly where.

## Ids

Every entry has an `id`: lowercase-with-dashes (`hester-vane`). It's how entries point at each other — an NPC's `location: gull-and-lantern`, a faction's `leader: oren-hask`, an NPC's `statblock: srd-veteran`. Leave it out and it's made from the name.

## Creatures

- **The SRD's 300-odd creatures** are already in (`data/monsters/srd.json`); their ids start with `srd-`.
- **Kobold Press's open books** (Tome of Beasts 1–3, Creature Codex) can be imported from Open5e: `codex.bat import-monsters tob` (Windows) or `./codex.sh import-monsters tob` (see `import-monsters --list`).
- **Your own creatures**: write them in `data/monsters/*.yml`, or use **New creature** in the encounter builder.
- **A batch from a book you own**: fill in `templates/monsters.json` (a sheet with instructions inside) and import it — drag it onto `import-monsters.bat`, or `./codex.sh import-monsters sheet.json`.
- **Duplicates** between sources (the same creature in two books) can be hidden from the builder with `import-monsters dedup`.

The encounter builder shows every creature's id; use it in `{{ statblock <id> }}`.

## The party

`data/party.yml` has the party's level and each member. Fill in character cards with **Edit** on the [Party](../party/index.md) page while `CampaignCodex5e` runs — it writes the file for you, and keeps a backup.

**From CCC5e** (Custom Character Creator 5e): export the character there (a `.ccc5e` file), then on the Party page press **Import from CCC5e** (a new character, or the one with that name) or **Import .ccc5e** on a card — or run `codex.bat import-character "the file.ccc5e" --player Sam` (`./codex.sh import-character ...` on Mac and Linux). It shows what will change and fills in the whole card - AC, HP, abilities, saves, skills, attacks, features with their text, spellcasting. Import it again after a level-up to update it; the player, email, your note and anything marked private are kept. Besides the stats, an import brings the character's spells, inventory and money, persona and backstory, and portrait.

**The Party page** shows the party table (click a row to jump to that character) and one card per character, with Actions, Features, Spellcasting, Inventory and Persona sections. **Private fields:** list them under `private:` (`persona.bond`, `persona.backstory`, `skills`...), or mark an inventory item `private: true` - the other players don't see them on their site; you still do, marked 🔒. The leak check makes sure none of it reaches the players' site. Every field is in `templates/character.yml`. A file from CCC5e before 1.0.21 brings in only the name, race, class and level.

A player's `email:` is only needed if you put the players' site online (it's how a player's sign-in is matched to their character); emails never appear on any page.
