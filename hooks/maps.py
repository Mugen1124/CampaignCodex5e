"""
Map pipeline for MkDocs.

Maps are listed in data/maps.yml, pointing at the original exports
(Wonderdraft, Dungeondraft, Inkarnate, a photo of a hand-drawn map...) in the
maps folder set in campaign.yml (maps: base:). Nothing is copied by hand.

On each build, any map whose source is new or has changed is resized to a
web-friendly JPG in .map-cache/ (or under output: local, on this computer; kept outside docs/ so it doesn't trigger a
live-reload loop). The cached copies are published as assets/maps/<id>.jpg.
Re-export a map and the site picks up the new version on the next rebuild.

Markers (each alone on its own line):
    {{ map greywater }}     one map, click to zoom
    {{ maps }}              every map, grouped, with anchors

The player site (mkdocs-players.yml) only has the maps marked `players: true` in maps.yml.
"""

import logging
import posixpath
import re
from pathlib import Path

import sys

import yaml
from mkdocs.structure.files import File

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex import settings as codex_settings  # noqa: E402

try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None  # large Wonderdraft exports are expected
except ImportError:  # pragma: no cover
    Image = None

log = logging.getLogger("mkdocs.hooks.maps")

MAPS = {}
CACHE_ROOT = None
PLAYERS = [False]   # the player site shows (and publishes) only maps marked `players: true`
ASSET_DIR = "assets/maps"

# Markers sit alone on their own line. They may be indented (inside a tab or a
# collapsible box); the rendered output is indented to match.
MARKER = re.compile(r"^([ \t]*)\{\{\s*(maps|map)\b\s*([A-Za-z0-9_-]*)\s*\}\}[ \t]*$", re.MULTILINE)


def _resize(src: Path, out: Path, max_width: int, quality: int) -> None:
    with Image.open(src) as im:
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            background = Image.new("RGB", im.size, (27, 23, 18))  # site's dark background
            background.paste(im, mask=im.split()[-1])
            im = background
        else:
            im = im.convert("RGB")
        if im.width > max_width:
            height = round(im.height * max_width / im.width)
            im = im.resize((max_width, height), Image.LANCZOS)
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)


def on_config(config, **kwargs):
    global CACHE_ROOT
    root = Path(config.config_file_path).parent
    CACHE_ROOT = codex_settings.load(root)["map_cache"]
    MAPS.clear()

    maps_file = root / "data" / "maps.yml"
    if not maps_file.is_file():
        return config
    data = yaml.safe_load(maps_file.read_text(encoding="utf-8")) or {}

    conf = codex_settings.load(root)["maps"]
    base = (root / data.get("base", conf["base"])).resolve()
    max_width = int(data.get("max_width", conf["max_width"]))
    quality = int(data.get("quality", conf["quality"]))

    if Image is None:
        log.warning("Pillow isn't installed - run setup again to enable maps.")

    PLAYERS[0] = (config.get("extra") or {}).get("audience") == "players"
    for entry in data.get("maps", []):
        if PLAYERS[0] and entry.get("players") is not True:
            continue   # DM maps never reach the player site - not even as a file
        mid = str(entry["id"])
        src = base / entry["source"]
        out = CACHE_ROOT / ASSET_DIR / f"{mid}.jpg"
        entry["id"] = mid
        entry["_src"] = src
        entry["_ok"] = False
        MAPS[mid] = entry

        if not src.is_file():
            log.warning("Map '%s': source not found: %s", mid, src)
            continue
        fresh = out.is_file() and out.stat().st_mtime >= src.stat().st_mtime
        if not fresh:
            if Image is None:
                continue
            log.info("Map '%s': resizing %s", mid, src.name)
            try:
                _resize(src, out, max_width, quality)
            except Exception as err:  # keep the build alive on a bad file
                log.warning("Map '%s': could not process %s: %s", mid, src.name, err)
                continue
        entry["_ok"] = True

    ready = sum(1 for m in MAPS.values() if m["_ok"])
    log.info("Maps: %d of %d ready", ready, len(MAPS))
    return config


def on_files(files, config, **kwargs):
    for m in MAPS.values():
        if m["_ok"]:
            files.append(File(
                f"{ASSET_DIR}/{m['id']}.jpg",
                src_dir=str(CACHE_ROOT),
                dest_dir=config["site_dir"],
                use_directory_urls=config["use_directory_urls"],
            ))
    return files


def _image(m: dict, page_src: str) -> str:
    if not m["_ok"]:
        return (f'!!! failure "Map unavailable: {m.get("title", m["id"])}"\n'
                f"    Source not found or unreadable: `{m.get('source')}`\n")
    start = posixpath.dirname(page_src) or "."
    rel = posixpath.relpath(f"{ASSET_DIR}/{m['id']}.jpg", start)
    lines = [f"![{m.get('title', m['id'])}]({rel})", ""]
    if m.get("caption"):
        lines += [f"*{m['caption']}*", ""]
    return "\n".join(lines)


def _gallery(page_src: str) -> str:
    groups = {}
    for m in MAPS.values():
        groups.setdefault(m.get("group", "Other"), []).append(m)
    order = [g for g in dict.fromkeys(m.get("group", "Other") for m in MAPS.values())]
    out = []
    for group in order:
        out += [f"## {group}", ""]
        for m in groups[group]:
            out += [f"### {m.get('title', m['id'])} {{ #{m['id']} }}", "", _image(m, page_src)]
    return "\n".join(out)


def on_page_markdown(markdown, page, config, files, **kwargs):
    src = page.file.src_uri

    def render(kind, key):
        if kind == "maps":
            return _gallery(src)
        m = MAPS.get(key)
        if not m and PLAYERS[0]:
            return ""   # not a player map
        if not m:
            log.warning("Unknown map id: %s", key)
            return f'!!! failure "Missing map"\n    No map with id `{key}` in `data/maps.yml`.\n'
        return _image(m, src)

    def replace(match):
        indent, kind, key = match.group(1), match.group(2), match.group(3)
        text = render(kind, key)
        return "\n".join(indent + line if line else line for line in text.split("\n"))

    return MARKER.sub(replace, markdown)
