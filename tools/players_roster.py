r"""
Writes publish\players\roster.json - which email plays which character, and each character's card as
it stands - for the players' site's worker (publish\players\worker.js), which builds it in. That's how
the players' site knows whose card a signed-in player may suggest changes to.

    python tools\players_roster.py

publish runs it before uploading the players' site. The emails come from data\party.yml (each
character's "email:", set with Edit on the Party page). roster.json is never one of the site's files;
the DM note isn't copied into it.
"""

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "publish" / "players" / "roster.json"
# The card as players may suggest changes to it (templates\character.yml, less player, email, and note).
CARD = ("race", "class", "level", "ac", "ac_note", "hp", "hp_formula", "speed", "initiative", "passive_perception",
        "abilities", "saves", "skills", "resistances", "immunities", "condition_immunities", "senses", "languages",
        "features", "actions", "bonus_actions", "reactions")


def roster() -> dict:
    party = yaml.safe_load((ROOT / "data" / "party.yml").read_text(encoding="utf-8")) or {}
    members = []
    for i, m in enumerate(p for p in party.get("members") or [] if isinstance(p, dict)):
        members.append({"index": i, "character": str(m.get("character", "")),
                        "email": str(m.get("email") or "").strip().lower(),
                        "card": {k: m[k] for k in CARD if k in m}})
    # Items found but not yet anybody's (holder: Unclaimed): the ones players may claim.
    grabs = []
    for path in sorted((ROOT / "data" / "items").glob("*.yml")):
        for item in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            if isinstance(item, dict) and str(item.get("holder") or "").strip().lower() == "unclaimed" \
                    and item.get("revealed") is not False:
                iid = item.get("id") or re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", str(item.get("name", "")).lower()
                                                                     .replace("'", "").replace("’", ""))).strip("-")
                grabs.append({"id": str(iid), "name": str(item.get("name", ""))})
    return {"level": party.get("level"), "members": members, "grabs": grabs}


def main() -> int:
    data = roster()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    linked = [m["character"] for m in data["members"] if m["email"]]
    print(f"Players' roster: {len(linked)} of {len(data['members'])} characters linked to an email"
          + (f" ({', '.join(linked)})" if linked else " - add them with Edit on the Party page") + "."
          + (f" {len(data['grabs'])} item(s) up for grabs." if data["grabs"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
