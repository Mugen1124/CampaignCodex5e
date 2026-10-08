# Writing pages

Pages are Markdown files in `docs/`. Open them in any text editor (VS Code, Notepad++, TextEdit in plain-text mode); with `serve` running, the site updates the moment you save. The [Style Guide](../reference/style-guide.md) shows every element live — this page explains how to write them.

## The basics

```markdown
# The Page Title

A paragraph. *Italics* for dialogue and asides, **bold** for labels.

## A section

- a bullet
- another

| A | table |
|---|---|
| goes | here |
```

## Boxes

```markdown
!!! read-aloud "The town gate"
    Indented four spaces under the line. Shown in its own box, ready to read.

!!! dm "Tactics"
    A note for you, visible while you run the scene.

??? dm "DM only — the secret"
    Folded away until clicked.
```

Both `dm` boxes, and `warning` boxes, are removed from the players' site.

## Markers

A marker, alone on its own line, is replaced with something built from your data:

| Marker | Shows |
|---|---|
| `{{ statblock bog-lurker }}` | one creature's stat block |
| `{{ encounter dock-ambush }}` | an encounter's roster and difficulty |
| `{{ party-cards }}` / `{{ party-card kestrel }}` | character cards |
| `{{ locations greywater }}` | a town's locations, with who's found where |
| `{{ npc-list greywater }}` | a town's people |
| `{{ npc-index }}` | everyone, in full |
| `{{ factions }}` / `{{ factions greywater }}` | factions, all or one town's |
| `{{ items }}` | every item |
| `{{ bestiary }}` | every creature |
| `{{ map greywater }}` / `{{ maps }}` | one map / all of them |
| `{{ encounter-builder }}` | the encounter builder (the Encounters page) |
| `{{ rules cover attacking }}` | SRD rules chapters, by name (see the Rules pages for the rest) |
| `{{ conditions }}` / `{{ spells }}` / `{{ srd-magic-items }}` | the SRD's conditions, spells, magic items |

## Mentions

`[[Hester Vane]]` links to Hester with a hover card. `[[Hester Vane|Hester]]` shows "Hester". Anything in your data works: people, places, factions, items, creatures — and the rules: conditions (`[[Prone]]`), spells (`[[Fireball]]`), and the SRD's magic items (`[[Bag of Holding]]`). Your own data wins when a name matches. Only the first mention in each `##` section becomes a link, so busy paragraphs stay readable. A name the site doesn't know gets a red wavy underline and a warning in the `serve` window.

## Hiding text from the players

Most pages appear on both sites. Inside a page:

```markdown
<!-- players: hide -->
Only on your site.
<!-- players: end -->

<!-- players: show
Only on the players' site.
-->
```

A whole page that's only for you gets this at the very top:

```markdown
---
dm_only: true
---
```

Any `<!-- comment -->` is also removed from the players' site, so notes to yourself never leak into the page source. See [The players' site](players-site.md).

## Page settings

The block between `---` lines at the very top of a page:

| Setting | Does |
|---|---|
| `dm_only: true` | never on the players' site |
| `toc_depth: 2` | the right-hand contents lists only `##` headings |
| `regions: [Greywater]` | `add-mentions` matches one-word names ("Hester") only from these places |
| `hide: [toc]` | no right-hand contents at all |

## Adding a page to the menu

New pages appear in the menus once they're in `nav:` at the bottom of `mkdocs.yml` (and `mkdocs-players.yml`, if players should have them). Copy a line next to it and change the title and path. Mind the indentation: two spaces per level.
