r"""
A character from CCC5e (Custom Character Creator 5e) onto the Party page: its card in data/party.yml.

    codex import-character "Tam - Halfling Rogue 3.ccc5e"                 add or update that character
    codex import-character "Tam - Halfling Rogue 3.ccc5e" --player Sam    ...and say who plays it
    codex import-character FILE --yes                                     don't ask before saving

In CCC5e, Export writes a .ccc5e file. One from CCC5e 1.0.21 or later carries the finished sheet
("Sheet"), and all of it comes in: AC, HP, speed, abilities, saves, skills, senses, languages,
resistances, attacks, features (with their text), spellcasting, inventory, money, persona and the
portrait (saved as docs/party/portraits/<character>.jpg). An older file has only the basics - name,
race, class, level - and says so.

A character already in the party (the same name) gets its card replaced; its player, email, DM note
and private marks are kept. Anyone else is added. party.yml is backed up first (sources/backups/party/).
The Party page's Import button (on the site at home) does the same through tools/site_helper.py.
"""

import base64
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

ABBR = {"str": "Str", "dex": "Dex", "con": "Con", "int": "Int", "wis": "Wis", "cha": "Cha"}
ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}
PORTRAITS = ROOT / "docs" / "party" / "portraits"
PORTRAIT_SIZE = 320            # pixels, the longer side
KEEP = ("player", "email", "note", "private", "rev")   # what an import never replaces


def signed(n) -> str:
    n = int(n)
    return f"+{n}" if n >= 0 else f"−{-n}"


def ordinal(n: int) -> str:
    return ORDINAL.get(n, f"{n}th")


def feet(s: str) -> str:
    """CCC5e's '25ft.' -> '25 ft.'"""
    s = str(s or "").strip()
    return re.sub(r"(\d)\s*ft\.", r"\1 ft.", s)


def text(s) -> str:
    return " ".join(str(s or "").split())


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower().replace("'", "")).strip("-") or "character"


def join_race(race, subrace) -> str:
    """'Halfling' + 'Lightfoot Halfling' -> 'Lightfoot Halfling'; 'Elf' + 'High' -> 'High Elf'."""
    race, subrace = str(race or "").strip(), str(subrace or "").strip()
    if not subrace or subrace.lower() in race.lower():
        return race
    if race.lower() in subrace.lower():
        return subrace
    return f"{subrace} {race}"


def load_text(raw: str, name: str = "the file") -> dict:
    try:
        data = json.loads(raw)
    except ValueError as err:
        raise ValueError(f"{name} isn't a CCC5e character ({err}).")
    if not isinstance(data, dict) or not (data.get("Name") or data.get("Sheet")):
        raise ValueError(f"{name} isn't a CCC5e character (.ccc5e).")
    return data


def load(path: Path) -> dict:
    try:
        return load_text(Path(path).read_text(encoding="utf-8-sig"), Path(path).name)
    except OSError as err:
        raise SystemExit(f"Couldn't read {path}: {err}")
    except ValueError as err:
        raise SystemExit(str(err))


def card(data: dict) -> dict:
    """The party.yml card for a CCC5e export (portrait aside - see save_portrait)."""
    s = data.get("Sheet")
    if not isinstance(s, dict):
        return basics(data)
    classes = s.get("classes") or []
    if len(classes) > 1:
        cls = " / ".join(f"{c['name']} {c['level']}" + (f" ({c['subclass']})" if c.get("subclass") else "") for c in classes)
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
        return {"name": f["name"] + (f" ({f['usage']})" if f.get("usage") else ""), "text": text(f.get("text"))}

    features, actions, bonus, reactions = [], [], [], []
    for a in s.get("attacks") or []:
        bits = [f"{a.get('toHit')} to hit" if a.get("toHit") else "", f"range {a['range']}" if a.get("range") else ""]
        line = ", ".join(b for b in bits if b)
        line = (f"*Attack:* {line}. " if line else "") + (f"*Hit:* {a['damage']}." if a.get("damage") else "")
        if a.get("notes"):
            line += f" {a['notes']}"
        actions.append({"name": a["name"], "text": line.strip()})
    for f in s.get("features") or []:
        {"Action": actions, "Bonus Action": bonus, "Reaction": reactions}.get(f.get("action") or "", features).append(entry(f))
    if s.get("backgroundFeature"):
        features.append({"name": s["backgroundFeature"], "text": text(s.get("backgroundFeatureText"))})

    by_class = {sp["class"]: sp for sp in s.get("spells") or []}
    casting = []
    for c in s.get("spellcasting") or []:
        lists = by_class.get(c.get("name")) or {}
        entry_ = {"name": c.get("name"), "ability": c.get("ability"), "save_dc": c.get("saveDc"),
                  "attack": c.get("attackBonus"),
                  "slots": {lvl: n for lvl, n in enumerate(c.get("slots") or []) if lvl and n},
                  "cantrips": [x["name"] for x in lists.get("cantrips") or []],
                  "spells": [{"name": x["name"], "level": x["level"],
                              **({"prepared": True} if x.get("prepared") or x.get("alwaysPrepared") else {})}
                             for x in sorted(lists.get("spells") or [], key=lambda x: (x["level"], x["name"]))]}
        if c.get("pact") and c.get("pactSlotCount"):
            entry_["slots"] = {c["pactSlotLevel"]: c["pactSlotCount"]}
            entry_["pact"] = True
        casting.append({k: v for k, v in entry_.items() if v not in (None, "", [], {})})
    for g in s.get("innateSpells") or []:
        casting.append({k: v for k, v in {
            "name": f"Innate ({g.get('sources')})", "ability": g.get("ability"), "save_dc": g.get("saveDc"),
            "attack": g.get("attackBonus"), "spells": [{"name": x["name"], "level": x["level"]} for x in g.get("spells") or []],
        }.items() if v not in (None, "", [])})

    inventory = []
    for i in s.get("equipment") or []:
        item = {"name": i["name"]}
        if (i.get("quantity") or 1) != 1:
            item["qty"] = i["quantity"]
        for flag in ("equipped", "attuned", "magic"):
            if i.get(flag):
                item[flag] = True
        inventory.append(item)
    money = {k: v for k, v in (s.get("currency") or {}).items() if v}

    p = s.get("persona") or {}
    looks = [f"{p['age']} years" if p.get("age") else "", p.get("gender"), p.get("height"), p.get("weight"),
             f"{p['eyes']} eyes" if p.get("eyes") else "", f"{p['skin']} skin" if p.get("skin") else "",
             f"{p['hair']} hair" if p.get("hair") else ""]
    persona = {
        "traits": [text(t) for t in p.get("traits") or [] if text(t)],
        "ideal": text(p.get("ideal")), "bond": text(p.get("bond")), "flaw": text(p.get("flaw")),
        "appearance": ", ".join(x for x in looks if x), "backstory": str(p.get("backstory") or "").strip(),
        "allies": text(p.get("allies")), "deity": text(p.get("deity")),
        "alignment": text(s.get("alignment")),
    }
    hp = s.get("hp") or {}
    out = {
        "character": s.get("name") or data.get("Name"),
        "race": join_race(s.get("race"), s.get("subrace")), "class": cls, "background": s.get("background"),
        "level": s.get("level"),
        "ac": s.get("ac"), "ac_note": armor.lower() if armor else "",
        "hp": hp.get("max"), "hp_formula": hp.get("hitDice"),
        "speed": ", ".join(x for x in speeds if x),
        "initiative": s.get("initiative"), "passive_perception": s.get("passivePerception"),
        "abilities": {k: v["score"] for k, v in abilities.items() if k in ABBR},
        "saves": saves, "skills": skills,
        "resistances": s.get("resistances") or "", "senses": s.get("senses") or "",
        "languages": (s.get("proficiencies") or {}).get("languages") or "",
        "proficiencies": {k: v for k, v in (s.get("proficiencies") or {}).items() if v and k != "languages"},
        "features": features, "actions": actions, "bonus_actions": bonus, "reactions": reactions,
        "spellcasting": casting, "inventory": inventory, "currency": money,
        "persona": {k: v for k, v in persona.items() if v},
        "source": {"from": "CCC5e", "imported": date.today().isoformat()},
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
    out = {"character": data.get("Name"), "race": race, "class": cls, "background": data.get("BackgroundDisplayName"),
           "level": data.get("Level"), "source": {"from": "CCC5e", "imported": date.today().isoformat()}}
    return {k: v for k, v in out.items() if v not in (None, "")}


def portrait_bytes(data: dict):
    """(bytes, extension) of the portrait the Sheet carries, shrunk to PORTRAIT_SIZE, or None."""
    uri = (data.get("Sheet") or {}).get("portrait")
    m = re.match(r"^data:image/[\w.+-]+;base64,(.+)$", str(uri or ""), re.S)
    if not m:
        return None
    try:
        raw = base64.b64decode(m.group(1), validate=False)
        from PIL import Image
        im = Image.open(io.BytesIO(raw))
        im.thumbnail((PORTRAIT_SIZE, PORTRAIT_SIZE))
        if im.mode not in ("RGB", "L"):
            background = Image.new("RGB", im.size, (22, 22, 22))
            background.paste(im, mask=im.convert("RGBA").split()[-1])
            im = background
        out = io.BytesIO()
        im.save(out, "JPEG", quality=85, optimize=True)
        return out.getvalue(), ".jpg"
    except Exception:
        return None


def save_portrait(data: dict, name: str):
    """Writes the portrait to docs/party/portraits/; returns its path for the card (from docs/), or None."""
    got = portrait_bytes(data)
    if not got:
        return None
    PORTRAITS.mkdir(parents=True, exist_ok=True)
    path = PORTRAITS / (slug(name) + got[1])
    path.write_bytes(got[0])
    return f"party/portraits/{path.name}"


def merge(old: dict, new: dict) -> dict:
    """The imported card, keeping what an import never replaces."""
    out = dict(new)
    for k in KEEP:
        if old.get(k):
            out[k] = old[k]
    return out


def changes(old: dict, new: dict) -> list:
    """What an import would change, for the preview: [(field, before, after)]."""
    out = []
    for key in ("race", "class", "background", "level", "ac", "hp", "speed", "initiative", "passive_perception",
                "saves", "skills", "senses", "languages", "resistances"):
        if str(old.get(key, "")) != str(new.get(key, "")):
            out.append((key, old.get(key, ""), new.get(key, "")))
    if old.get("abilities") != new.get("abilities"):
        ab = lambda a: ", ".join(f"{k.upper()} {v}" for k, v in (a or {}).items())
        out.append(("abilities", ab(old.get("abilities")), ab(new.get("abilities"))))
    for key in ("features", "actions", "bonus_actions", "reactions", "inventory"):
        before = {e["name"] for e in old.get(key) or []}
        after = {e["name"] for e in new.get(key) or []}
        if after - before:
            out.append((key, "", "+ " + ", ".join(sorted(after - before))))
        if before - after:
            out.append((key, "- " + ", ".join(sorted(before - after)), ""))
    sp = lambda c: {x["name"] for e in c or [] for x in e.get("spells") or []} | {n for e in c or [] for n in e.get("cantrips") or []}
    if sp(new.get("spellcasting")) - sp(old.get("spellcasting")):
        out.append(("spells", "", "+ " + ", ".join(sorted(sp(new.get("spellcasting")) - sp(old.get("spellcasting"))))))
    if sp(old.get("spellcasting")) - sp(new.get("spellcasting")):
        out.append(("spells", "- " + ", ".join(sorted(sp(old.get("spellcasting")) - sp(new.get("spellcasting")))), ""))
    for key in ("currency", "persona"):
        if old.get(key) != new.get(key):
            out.append((key, "changed" if old.get(key) else "", "updated" if new.get(key) else "(none)"))
    return out


def find(members: list, name: str):
    return next((i for i, m in enumerate(members)
                 if str(m.get("character", "")).strip().lower() == str(name).strip().lower()), None)


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
    idx = find(members, new["character"])
    old = members[idx] if idx is not None else {}
    merged = merge(old, new)
    if args.player:
        merged["player"] = args.player
    if old.get("portrait"):
        merged["portrait"] = old["portrait"]
    merged, error = helper.clean_member(merged)
    if error:
        raise SystemExit(error)

    if idx is None:
        print(f"Adding {merged['character']} ({merged.get('race', '')} {merged.get('class', '')}, level {merged.get('level', '?')}) to the party.")
    else:
        diff = changes(old, merged)
        print(f"Updating {merged['character']}: " + ("no changes." if not diff else f"{len(diff)} change(s)."))
        for field, before, after in diff:
            print(f"  {field.replace('_', ' ')}: {before or '-'}  ->  {after or '-'}")
        if not diff and not portrait_bytes(data):
            return 0
    if not args.yes:
        try:
            answer = input('Type "yes" to save: ')
        except EOFError:
            answer = ""
        if answer.strip().lower() != "yes":
            print("Nothing was changed.")
            return 1
    portrait = save_portrait(data, merged["character"])
    if portrait:
        merged["portrait"] = portrait
    helper.backup_party()
    if idx is None:
        members.append(merged)
    else:
        members[idx] = merged
    helper.write_party(members, size=len(members) if idx is None else None)
    print(f"Saved to data/party.yml{' - the party is now ' + str(len(members)) if idx is None else ''}."
          + (f" Portrait: docs/{portrait}." if portrait else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
