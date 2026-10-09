r"""
A character from CCC5e (Custom Character Creator 5e) onto the Party page: its card in data/party.yml.

    codex import-character "Tam - Halfling Rogue 3.ccc5e"                 add or update that character
    codex import-character "Tam - Halfling Rogue 3.ccc5e" --player Sam    ...and say who plays it
    codex import-character FILE --yes                                     don't ask before saving

In CCC5e, Export writes a .ccc5e file. One from CCC5e 1.0.21 or later carries the finished sheet
("Sheet"), and all of it comes in: AC, HP, speed, abilities, saves, skills, senses, languages,
resistances, attacks, features (with their text), spellcasting. An older file has only the basics -
name, race, class, level - and says so.

A character already in the party (the same name) gets its card replaced; its player, email and DM
note are kept. Anyone else is added. The old party.yml is backed up first (sources/backups/party/).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

ABBR = {"str": "Str", "dex": "Dex", "con": "Con", "int": "Int", "wis": "Wis", "cha": "Cha"}
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}


def signed(n) -> str:
    n = int(n)
    return f"+{n}" if n >= 0 else f"−{-n}"


def ordinal(n: int) -> str:
    return ORDINAL.get(n, f"{n}th")


def feet(s: str) -> str:
    """CCC5e's '25ft.' -> '25 ft.'"""
    s = str(s or "").strip()
    return s.replace("ft.", " ft.").replace("  ", " ") if s and "ft." in s and " ft." not in s else s


def join_race(race, subrace) -> str:
    """'Halfling' + 'Lightfoot Halfling' -> 'Lightfoot Halfling'; 'Elf' + 'High' -> 'High Elf'."""
    race, subrace = str(race or "").strip(), str(subrace or "").strip()
    if not subrace or subrace.lower() in race.lower():
        return race
    if race.lower() in subrace.lower():
        return subrace
    return f"{subrace} {race}"


def load(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as err:
        raise SystemExit(f"Couldn't read {path}: {err}")
    if not isinstance(data, dict) or not (data.get("Name") or data.get("Sheet")):
        raise SystemExit(f"{path} isn't a CCC5e character (.ccc5e).")
    return data


def card(data: dict) -> dict:
    """The party.yml card fields for a CCC5e export."""
    s = data.get("Sheet")
    if not isinstance(s, dict):
        return basics(data)
    race = join_race(s.get("race"), s.get("subrace"))
    classes = s.get("classes") or []
    if len(classes) > 1:
        cls = " / ".join(f"{c['name']} {c['level']}" for c in classes)
    else:
        cls = s.get("class") or ""
        if s.get("subclass"):
            cls = f"{cls} ({s['subclass']})"
    armor = ", ".join(x for x in (s.get("armor"), s.get("shield")) if x)
    speed = s.get("speed") or {}
    speeds = [feet(speed.get("walk"))] + [f"{k} {feet(speed[k])}" for k in ("fly", "swim", "climb") if speed.get(k)]
    abilities = s.get("abilities") or {}
    saves = ", ".join(f"{ABBR[k]} {signed(v['save'])}" for k, v in abilities.items() if v.get("saveProf") and k in ABBR)
    skills = ", ".join(f"{x['name']} {signed(x['total'])}" for x in sorted(s.get("skills") or [], key=lambda x: x["name"])
                       if x.get("prof") or x.get("expert"))

    def entry(f):
        name = f["name"] + (f" ({f['usage']})" if f.get("usage") else "")
        return {"name": name, "text": " ".join(str(f.get("text") or "").split())}

    features, actions, bonus, reactions = [], [], [], []
    for a in s.get("attacks") or []:
        bits = [f"{a.get('toHit')} to hit" if a.get("toHit") else "", f"range {a['range']}" if a.get("range") else ""]
        text = ", ".join(b for b in bits if b)
        text = (f"*Attack:* {text}. " if text else "") + (f"*Hit:* {a['damage']}." if a.get("damage") else "")
        if a.get("notes"):
            text += f" {a['notes']}"
        actions.append({"name": a["name"], "text": text.strip()})
    for f in s.get("features") or []:
        {"Action": actions, "Bonus Action": bonus, "Reaction": reactions}.get(f.get("action") or "", features).append(entry(f))
    if s.get("backgroundFeature"):
        features.append({"name": s["backgroundFeature"], "text": " ".join(str(s.get("backgroundFeatureText") or "").split())})

    # Spellcasting: one entry per casting class, plus innate spells.
    by_class = {sp["class"]: sp for sp in s.get("spells") or []}
    for c in s.get("spellcasting") or []:
        slots = c.get("slots") or []
        slot_text = ", ".join(f"{ordinal(lvl)} ×{n}" for lvl, n in enumerate(slots) if lvl and n)
        if c.get("pact") and c.get("pactSlotCount"):
            slot_text = f"{c['pactSlotCount']} × {ordinal(c['pactSlotLevel'])}-level (pact)"
        lists = by_class.get(c.get("name")) or {}
        cantrips = ", ".join(x["name"] for x in lists.get("cantrips") or [])
        known = ", ".join(x["name"] + ("*" if x.get("prepared") or x.get("alwaysPrepared") else "")
                          for x in sorted(lists.get("spells") or [], key=lambda x: (x["level"], x["name"])))
        parts = [f"{c.get('ability')}; spell save DC {c.get('saveDc')}, {signed(c.get('attackBonus', 0))} to hit with spell attacks."]
        if slot_text:
            parts.append(f"Slots: {slot_text}.")
        if cantrips:
            parts.append(f"Cantrips: {cantrips}.")
        if known:
            parts.append(f"Spells: {known}." + (" (* prepared)" if "*" in known else ""))
        features.append({"name": f"Spellcasting ({c.get('name')})", "text": " ".join(parts)})
    for g in s.get("innateSpells") or []:
        names = ", ".join(x["name"] for x in g.get("spells") or [])
        features.append({"name": f"Innate spellcasting ({g.get('sources')})",
                         "text": f"{g.get('ability')}; spell save DC {g.get('saveDc')}. {names}."})

    hp = s.get("hp") or {}
    out = {
        "character": s.get("name") or data.get("Name"),
        "race": race, "class": cls, "level": s.get("level"),
        "ac": s.get("ac"), "ac_note": armor.lower() if armor else "",
        "hp": hp.get("max"), "hp_formula": hp.get("hitDice"),
        "speed": ", ".join(x for x in speeds if x),
        "initiative": s.get("initiative"), "passive_perception": s.get("passivePerception"),
        "abilities": {k: v["score"] for k, v in abilities.items() if k in ABBR},
        "saves": saves, "skills": skills,
        "resistances": s.get("resistances") or "", "senses": s.get("senses") or "",
        "languages": (s.get("proficiencies") or {}).get("languages") or "",
        "features": features, "actions": actions, "bonus_actions": bonus, "reactions": reactions,
    }
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def basics(data: dict) -> dict:
    """An export without a Sheet (CCC5e before 1.0.21): just who the character is."""
    race = join_race(data.get("RaceDisplayName"), data.get("SubraceDisplayName"))
    cls = data.get("ClassDisplayName") or ""
    if data.get("SubclassDisplayName"):
        cls = f"{cls} ({data['SubclassDisplayName']})"
    multi = data.get("MulticlassEntries") or []
    if multi:
        main = (data.get("Level") or 0) - sum(m.get("Level") or 0 for m in multi)
        cls = " / ".join([f"{data.get('ClassDisplayName')} {main}"] + [f"{m.get('ClassDisplayName')} {m.get('Level')}" for m in multi])
    out = {"character": data.get("Name"), "race": race, "class": cls, "level": data.get("Level")}
    return {k: v for k, v in out.items() if v not in (None, "")}


def changes(old: dict, new: dict) -> list:
    """What an import would change, for the preview: [(field, before, after)]."""
    out = []
    for key in ("race", "class", "level", "ac", "hp", "speed", "initiative", "passive_perception", "saves", "skills",
                "senses", "languages", "resistances"):
        if str(old.get(key, "")) != str(new.get(key, "")):
            out.append((key, old.get(key, ""), new.get(key, "")))
    if old.get("abilities") != new.get("abilities"):
        out.append(("abilities", old.get("abilities", ""), new.get("abilities", "")))
    for key in ("features", "actions", "bonus_actions", "reactions"):
        before = {e["name"] for e in old.get(key) or []}
        after = {e["name"] for e in new.get(key) or []}
        if after - before:
            out.append((key, "", "+ " + ", ".join(sorted(after - before))))
        if before - after:
            out.append((key, "- " + ", ".join(sorted(before - after)), ""))
    return out


def main(argv=None) -> int:
    import argparse
    import yaml
    import site_helper as helper   # party.yml's reader and writer (keeps everyone else's lines as written)

    ap = argparse.ArgumentParser(description="Add or update a character from a CCC5e export (.ccc5e).")
    ap.add_argument("file")
    ap.add_argument("--player", help="who plays the character (kept as it is if they're already in the party)")
    ap.add_argument("--yes", action="store_true", help="don't ask before saving")
    args = ap.parse_args(argv)

    data = load(Path(args.file))
    new = card(data)
    if "Sheet" not in data:
        print("This file has no computed sheet (CCC5e before 1.0.21): only the name, race, class and level come in.")
        print("Export it again from CCC5e 1.0.21 or later for AC, HP, skills, attacks and features.\n")

    party = yaml.safe_load(helper.PARTY.read_text(encoding="utf-8")) or {}
    members = party.get("members") or []
    idx = next((i for i, m in enumerate(members)
                if str(m.get("character", "")).strip().lower() == str(new["character"]).strip().lower()), None)
    old = members[idx] if idx is not None else {}
    keep = {k: old[k] for k in ("player", "email", "note") if old.get(k)}
    if args.player:
        keep["player"] = args.player
    merged, error = helper.clean_member({**keep, **new}, keep=old)
    if error:
        raise SystemExit(error)

    if idx is None:
        print(f"Adding {merged['character']} ({merged.get('race', '')} {merged.get('class', '')}, level {merged.get('level', '?')}) to the party.")
    else:
        diff = changes(old, merged)
        print(f"Updating {merged['character']}: " + ("no changes." if not diff else f"{len(diff)} change(s)."))
        for field, before, after in diff:
            print(f"  {field.replace('_', ' ')}: {before or '-'}  ->  {after or '-'}")
        if not diff:
            return 0
    if not args.yes:
        try:
            answer = input('Type "yes" to save: ')
        except EOFError:
            answer = ""
        if answer.strip().lower() != "yes":
            print("Nothing was changed.")
            return 1
    helper.backup_party()
    if idx is None:
        members.append(merged)
    else:
        members[idx] = merged
    helper.write_party(members, size=len(members) if idx is None else None)
    print(f"Saved to data/party.yml{' - the party is now ' + str(len(members)) if idx is None else ''}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
