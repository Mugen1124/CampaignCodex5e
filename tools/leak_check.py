r"""
Checks the built player site for DM material, before publish uploads it.

    python tools\leak_check.py                 checks publish\players\site
    python tools\leak_check.py <site folder>

Searches everything in the built site - page text, hover-card data, the search index - for:

  BLOCKING (exit code 1; publish won't upload):
    - any sentence of an NPC's notes or secret, a location's dm_notes or secret, a faction's
      details / structure / goals / secret, or a character card's DM note
    - any sentence of a DM box (??? dm, !!! dm, Needs decision) or a <!-- players: hide -->
      stretch on the pages the player site includes
    - DM maps or DM-only scripts among the files, or images/PDFs no player page uses
    - a player's email (data/party.yml) anywhere in the files

  REVIEW (reported, doesn't block):
    - the full name of an NPC the party hasn't come across yet, where it appears in page text
      (your own prose may mention them on purpose - check, and hide or reveal them; names_ok: in
      data/revealed.yml lists the ones you've checked and are happy to leave)
"""

import html
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

MIN_WORDS = 6   # sentences shorter than this are too generic to tell a leak from coincidence


def norm(text: str) -> str:
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", str(text))
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`>#]", " ", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(text.lower().split())


def sentences(text: str):
    for s in re.split(r"(?<=[.!?])\s+|\n\s*\n|\n\s*[-*]\s", str(text)):
        s = norm(s).strip(" .")
        if len(s.split()) >= MIN_WORDS:
            yield s


def corpus(site: Path) -> dict:
    """{file: normalized text} for everything a visitor could read."""
    out = {}
    for path in site.rglob("*"):
        if path.suffix.lower() not in (".html", ".json", ".js", ".txt", ".xml"):
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix.lower() == ".json":
            try:
                raw = json.dumps(json.loads(raw), ensure_ascii=False)
            except ValueError:
                pass
        raw = raw.replace("\\/", "/").replace('\\"', '"').replace("\\n", " ")
        text = re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(raw)))
        out[path] = norm(text)
    return out


class _Config(dict):
    """Just enough of MkDocs' config for the hooks' on_config."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.config_file_path = str(ROOT / "mkdocs-players.yml")


def dm_secrets():
    """(label, sentence) pairs that must never appear on the player site."""
    import entities
    config = _Config(docs_dir=str(ROOT / "docs"), extra={"audience": "players"})
    entities.on_config(config)
    found = []
    for n in entities.NPCS.values():
        for field in ("notes", "secret"):
            found += [(f"NPC {n['name']} ({field})", s) for s in sentences(n.get(field) or "")]
    for loc in entities.LOCATIONS.values():
        for field in ("dm_notes", "secret"):
            found += [(f"location {loc['name']} ({field})", s) for s in sentences(loc.get(field) or "")]
    for fac in entities.FACTIONS.values():
        for field in ("details", "structure", "goals", "secret"):
            found += [(f"faction {fac['name']} ({field})", s) for s in sentences(fac.get(field) or "")]
    party = yaml.safe_load((ROOT / "data" / "party.yml").read_text(encoding="utf-8")) or {}
    def texts(value):
        if isinstance(value, dict):
            return [t for v in value.values() for t in texts(v)]
        if isinstance(value, list):
            return [t for v in value for t in texts(v)]
        return [str(value)] if isinstance(value, str) else []

    for p in party.get("members") or []:
        if isinstance(p, dict):
            found += [(f"{p.get('character')}'s card (DM note)", s) for s in sentences(p.get("note") or "")]
            # What the player marked private: other players must never see it.
            for path in p.get("private") or []:
                head, _, sub = str(path).partition(".")
                value = (p.get(head) or {}).get(sub) if sub and isinstance(p.get(head), dict) else p.get(head)
                found += [(f"{p.get('character')}'s card (private: {path})", s) for t in texts(value) for s in sentences(t)]
            for item in p.get("inventory") or []:
                if isinstance(item, dict) and item.get("private"):
                    found += [(f"{p.get('character')}'s card (private item)", s) for s in sentences(str(item.get("name", "")))]
    # DM boxes and hidden stretches on the pages the player site includes
    players = yaml.safe_load(re.sub(r"^INHERIT:.*$", "", (ROOT / "mkdocs-players.yml").read_text(encoding="utf-8"), flags=re.M))
    excluded = [x.strip() for x in (players.get("exclude_docs") or "").splitlines() if x.strip()]
    docs = ROOT / "docs"
    for page in docs.rglob("*.md"):
        rel = "/" + page.relative_to(docs).as_posix()
        if any(rel == e or (e.endswith("/") and rel.startswith(e)) for e in excluded):
            continue
        text = page.read_text(encoding="utf-8")
        # A sentence the page also gives the players (<!-- players: show -->) isn't a leak.
        shown = {s for block in re.findall(r"<!--\s*players:\s*show[ \t]*\n(.*?)-->", text, re.S) for s in sentences(block)}
        for block in re.findall(r"<!--\s*players:\s*hide\s*-->(.*?)<!--\s*players:\s*end\s*-->", text, re.S):
            found += [(f"{rel} (players: hide)", s) for s in sentences(block) if s not in shown]
        lines, i = text.split("\n"), 0
        while i < len(lines):
            m = re.match(r"^(\s*)(\?\?\?\+?|!!!)\s+(dm|warning)\b", lines[i])
            if not m:
                i += 1
                continue
            indent, body, i = len(m.group(1)), [], i + 1
            while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
                body.append(lines[i])
                i += 1
            found += [(f"{rel} (DM box)", s) for s in sentences("\n".join(body))]
    return found, entities


def main() -> int:
    if len(sys.argv) > 1:
        site = Path(sys.argv[1])
    else:
        sys.path.insert(0, str(ROOT))
        from codex import settings as codex_settings
        site = codex_settings.load(ROOT)["publish_dir"] / "players" / "site"
    if not (site / "index.html").is_file():
        print(f"No built player site at {site}.")
        return 1
    texts = corpus(site)
    secrets, entities = dm_secrets()
    leaks = []
    for label, s in secrets:
        where = [p for p, t in texts.items() if s in t]
        if where:
            leaks.append((label, s, sorted({p.relative_to(site).as_posix() for p in where})))
    files = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file()}
    maps = yaml.safe_load((ROOT / "data" / "maps.yml").read_text(encoding="utf-8")) or {}
    dm_maps = {f"assets/maps/{m['id']}.jpg" for m in maps.get("maps", []) if m.get("players") is not True}
    stray = sorted(files & (dm_maps | {"javascripts/encounter-builder.js", "javascripts/recorder.js",
                                       "javascripts/items-editor.js"}))
    import players
    stray += sorted(p.relative_to(site).as_posix() for p in players.unused_media(site))
    # Players' emails (party.yml, for the card suggestions) are only ever in the worker's roster.
    party = yaml.safe_load((ROOT / "data" / "party.yml").read_text(encoding="utf-8")) or {}
    for m in party.get("members") or []:
        email = str((m or {}).get("email") or "").strip().lower() if isinstance(m, dict) else ""
        # searched in the files as they are (tags, comments and all), not just their visible text
        where = sorted({p.relative_to(site).as_posix() for p in site.rglob("*") if email and p.is_file()
                        and email in p.read_bytes().decode("utf-8", "ignore").lower()})
        if where:
            leaks.append((f"{m.get('character')}'s player's email", email, where))
    # Whereabouts: a captive's, missing or dead NPC's place must not show unless meant to.
    for n in entities.NPCS.values():
        if n.get("status", "alive") == "alive" or ("npc", n["id"]) not in entities.REVEALED:
            continue
        lid = entities._npc_location(n)
        if lid and ("location", lid) in entities.REVEALED:
            leaks.append((f"NPC {n['name']} ({n.get('status')})", f"whereabouts shown: {entities.LOCATIONS[lid]['name']} "
                          "(set player_location, empty if the party doesn't know)", ["people / locations pages"]))
    extra = yaml.safe_load((ROOT / "data" / "revealed.yml").read_text(encoding="utf-8"))         if (ROOT / "data" / "revealed.yml").is_file() else None
    names_ok = {entities._resolve(str(x)) for x in (extra or {}).get("names_ok") or []}
    review = []
    for n in entities.NPCS.values():
        if ("npc", n["id"]) in entities.REVEALED or ("npc", n["id"]) in names_ok or len(n["name"].split()) < 2:
            continue
        name = norm(n["name"])
        pages = sorted({p.relative_to(site).as_posix() for p, t in texts.items()
                        if p.suffix == ".html" and name in t})
        if pages:
            review.append((n["name"], pages))

    print(f"Leak check: {len(secrets)} DM sentences and {len(files)} files checked in {site}")
    if review:
        print(f"\nREVIEW - {len(review)} NPC name(s) the party hasn't come across appear in page text:")
        for name, pages in review:
            print(f"  {name}: {', '.join(pages)}")
        print("  (Fine if the page means to mention them; otherwise hide the text, or reveal them in data/revealed.yml.)")
    if leaks or stray:
        print("\nBLOCKED - DM material found on the player site:")
        for label, s, pages in leaks:
            print(f"  {label}: \"{s[:90]}{'...' if len(s) > 90 else ''}\"  in {', '.join(pages)}")
        for f in stray:
            print(f"  DM-only file: {f}")
        return 1
    print("\nOK - no DM material found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
