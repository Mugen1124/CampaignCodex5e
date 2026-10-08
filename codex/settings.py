"""
Campaign settings: everything that makes this site *your* campaign rather than the engine.

They live in campaign.yml at the top of the project. Every hook and tool reads them through
load(), so nothing in hooks/ or tools/ needs editing to run a different campaign. Anything
missing from campaign.yml falls back to the defaults below.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "campaign.yml"

DEFAULTS = {
    "name": "My Campaign",
    "tagline": "",
    # Factions with no region: are grouped under this heading on the Factions page.
    "default_region": "The World",
    # The city the party is in right now. Transcription gives its people and places first.
    "focus": "",
    # Words that should never appear outside the house rules page (e.g. a feat you've banned).
    # The build warns when a page mentions one.
    "banned": [],
    # Names add_mentions.py should never mark automatically (standard rulebook items, say).
    "skip_mentions": [],
    "maps": {
        # Where map exports live, relative to this folder. data/maps.yml paths start here.
        "base": "maps",
        "max_width": 4000,
        "quality": 85,
    },
    "recordings": "recordings",   # relative to this folder, or an absolute path
    "transcribe": {
        "model": "large-v3-turbo",
        # One sentence that tells the speech model what it's listening to.
        "intro": "A Dungeons & Dragons session.",
    },
    # Going online is optional - see "Going online" in the site's guide.
    "online": {
        "enabled": False,
        "dm_worker": "",          # the Cloudflare Worker for your DM site, e.g. my-campaign
        "players_worker": "",     # the Worker for the players' site, e.g. my-campaign-players
        "subdomain": "",          # your workers.dev subdomain: https://<worker>.<subdomain>.workers.dev
        "access_team": "",        # your Cloudflare Access team name: https://<team>.cloudflareaccess.com
        "players_site": True,     # also publish the players' site
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(base.get(k), dict) and isinstance(v, dict) else v
    return out


def load(root: Path = None) -> dict:
    """campaign.yml merged over the defaults, plus a few derived values."""
    root = Path(root) if root else ROOT
    path = root / "campaign.yml"
    raw = {}
    if path.is_file():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    s = _merge(DEFAULTS, raw)
    s["slug"] = slug(s["name"]) or "campaign"
    on = s["online"]
    sub = (on.get("subdomain") or "").strip()
    s["dm_url"] = f"https://{on['dm_worker']}.{sub}.workers.dev/" if on.get("dm_worker") and sub else ""
    s["players_url"] = f"https://{on['players_worker']}.{sub}.workers.dev/" if on.get("players_worker") and sub else ""
    s["access_url"] = f"https://{on['access_team']}.cloudflareaccess.com" if on.get("access_team") else ""
    rec = Path(s["recordings"])
    s["recordings_dir"] = rec if rec.is_absolute() else root / rec
    s["maps_dir"] = (root / s["maps"]["base"]).resolve()
    return s


def slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", str(text).lower().replace("’", "").replace("'", ""))
    return re.sub(r"[\s_]+", "-", s).strip("-")
