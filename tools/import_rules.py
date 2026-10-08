r"""
Fetches the rules encyclopedia - the 5e System Reference Document 5.1 - into data/rules/srd.json:
the rules chapters (combat, adventuring, spellcasting, equipment...), the conditions, every spell,
and every magic item. The Rules tab and the [[Prone]] / [[Fireball]] hover cards are built from it.

    python tools/import_rules.py

It comes with the site already; run this only to refresh it. The data comes from Open5e
(https://open5e.com). The SRD 5.1 is by Wizards of the Coast LLC, licensed under CC BY 4.0
(see CREDITS.md).
"""

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "rules" / "srd.json"
API = "https://api.open5e.com/v1"
DOC = "wotc-srd"
SKIP_SECTIONS = {"legal-information"}   # the old OGL notice; the CC BY attribution is in CREDITS.md


def fetch(endpoint: str) -> list:
    url = f"{API}/{endpoint}/?document__slug={DOC}&limit=500"
    out = []
    while url:
        req = urllib.request.Request(url, headers={"User-Agent": "campaign-codex"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        out += data.get("results", [])
        url = data.get("next")
    return out


def text(s) -> str:
    return str(s or "").replace("\r\n", "\n").strip()


def main() -> int:
    print("Fetching the SRD 5.1 from Open5e...")
    sections = [{"slug": s["slug"], "name": s["name"], "parent": s.get("parent", ""), "text": text(s["desc"])}
                for s in fetch("sections") if s["slug"] not in SKIP_SECTIONS]
    conditions = [{"slug": c["slug"], "name": c["name"], "text": text(c["desc"])} for c in fetch("conditions")]
    spells = []
    for s in fetch("spells"):
        spells.append({
            "slug": s["slug"], "name": s["name"], "level": int(s.get("level_int") or 0),
            "school": s.get("school", ""), "casting_time": s.get("casting_time", ""), "range": s.get("range", ""),
            "components": s.get("components", ""), "material": s.get("material", ""),
            "duration": s.get("duration", ""),
            "concentration": str(s.get("concentration", "")).lower() == "yes" or s.get("requires_concentration") is True,
            "ritual": str(s.get("ritual", "")).lower() == "yes" or s.get("can_be_cast_as_ritual") is True,
            "classes": sorted(c.capitalize() for c in (s.get("spell_lists") or [])),
            "text": text(s.get("desc")), "higher_level": text(s.get("higher_level")),
        })
    items = [{"slug": i["slug"], "name": i["name"], "type": i.get("type", ""), "rarity": i.get("rarity", ""),
              "attunement": text(i.get("requires_attunement")), "text": text(i["desc"])}
             for i in fetch("magicitems")]
    data = {
        "source": "srd",
        "title": "System Reference Document 5.1",
        "credit": ("Includes material from the System Reference Document 5.1 by Wizards of the Coast LLC, "
                   "licensed under CC BY 4.0. Retrieved through Open5e."),
        "sections": sorted(sections, key=lambda x: x["name"]),
        "conditions": sorted(conditions, key=lambda x: x["name"]),
        "spells": sorted(spells, key=lambda x: (x["level"], x["name"])),
        "magic_items": sorted(items, key=lambda x: x["name"]),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(sections)} rules sections, {len(conditions)} conditions, "
          f"{len(spells)} spells, {len(items)} magic items.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
