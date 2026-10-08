# Credits and licenses

## The code

campaign-codex is released under the [MIT License](LICENSE).

## The demo campaign

The demo campaign — *The Lantern Coast*: its pages in `docs/`, its data in `data/`, and its maps in `maps/` — was written for this project and is released under the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/). Use it, change it, share it.

## The System Reference Document

`data/monsters/srd.json` and `data/rules/srd.json` (the Rules tab: rules chapters, conditions, spells, and magic items) include material taken from the **System Reference Document 5.1** ("SRD 5.1") by Wizards of the Coast LLC, available at <https://dnd.wizards.com/resources/systems-reference-document>. The SRD 5.1 is licensed under the Creative Commons Attribution 4.0 International License, available at <https://creativecommons.org/licenses/by/4.0/legalcode>.

The data was retrieved through [Open5e](https://open5e.com/).

## Monsters you import

`import-monsters` can fetch creatures from other open sources through Open5e — for example Kobold Press's *Tome of Beasts* and *Creature Codex*, published under the Open Game License 1.0a. Those files are written into your own `data/monsters/` folder and carry their publishers' licenses; they're not part of this repository. Creatures you transcribe from books you own are for your own table.

## Built with

- [MkDocs](https://www.mkdocs.org/) (BSD-2-Clause)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) (MIT)
- [mkdocs-glightbox](https://github.com/blueswen/mkdocs-glightbox) (MIT)
- [Pillow](https://python-pillow.org/) (HPND)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT), optional
- [Cloudflare wrangler](https://github.com/cloudflare/workers-sdk) (MIT/Apache-2.0), optional, through npx

*Dungeons & Dragons* is a trademark of Wizards of the Coast LLC. campaign-codex is an independent project and isn't affiliated with or endorsed by Wizards of the Coast.
