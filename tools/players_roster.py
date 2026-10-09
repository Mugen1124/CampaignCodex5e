r"""
Writes roster.json next to the players' build (publish\players\, or under output: local) - which email plays which character, and each character's card as
it stands - for the players' site's worker (publish\players\worker.js), which builds it in. That's how
the players' site knows whose card a signed-in player may change, and the live Party page gets the
cards as party.yml has them.

    python tools\players_roster.py

publish runs it before uploading the players' site. The emails come from data\party.yml (each
character's "email:", set with Edit on the Party page). roster.json is never one of the site's files;
the DM note isn't copied into it.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codex import settings as codex_settings  # noqa: E402

OUT = codex_settings.load(ROOT)["publish_dir"] / "players" / "roster.json"
# Never online: the DM's note, the player's email, and party.yml's own bookkeeping.
OFFLINE = ("note", "email", "rev")


def card_id(name: str) -> str:
    """The card's anchor on the Party page (hooks/campaign.py _pc_id): pc-tamsin-tam-underbough."""
    return "pc-" + re.sub(r"[^a-z0-9]+", "-", str(name).lower().replace("'", "")).strip("-")


def online_card(m: dict) -> dict:
    """A party.yml card as the players' site keeps it live (publish/players/party.mjs)."""
    card = {k: v for k, v in m.items() if k not in OFFLINE}
    if card.get("portrait"):
        card["portrait"] = "/" + str(card["portrait"]).lstrip("/")   # a file on the players' site
    return card


def roster() -> dict:
    party = yaml.safe_load((ROOT / "data" / "party.yml").read_text(encoding="utf-8")) or {}
    members = []
    for i, m in enumerate(p for p in party.get("members") or [] if isinstance(p, dict)):
        card = online_card(m)
        members.append({"index": i, "character": str(m.get("character", "")), "id": card_id(m.get("character", "")),
                        "email": str(m.get("email") or "").strip().lower(), "card": card,
                        # base: the card's version online when the DM last got players' changes (tools/site_helper.py);
                        # hash: this party.yml card, so the live Party page can tell when it's been changed.
                        "base": int(m.get("rev") or 0),
                        "hash": hashlib.sha256(json.dumps(card, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]})
    # Items found but not yet anybody's (holder: Unclaimed): the ones players may claim.
    grabs = []
    for path in sorted((ROOT / "data" / "items").glob("*.yml")):
        for item in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            if isinstance(item, dict) and str(item.get("holder") or "").strip().lower() == "unclaimed" \
                    and item.get("revealed") is not False:
                iid = item.get("id") or re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", str(item.get("name", "")).lower()
                                                                     .replace("'", "").replace("’", ""))).strip("-")
                grabs.append({"id": str(iid), "name": str(item.get("name", ""))})
    version = hashlib.sha256(json.dumps([[m["id"], m["hash"], m["base"]] for m in members]).encode()).hexdigest()[:16]
    return {"level": party.get("level"), "version": version, "members": members, "grabs": grabs}


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
