r"""
Session recordings -> transcripts, on this computer (nothing is uploaded anywhere).

    python tools\transcribe.py                      newest recording in the recordings folder
    python tools\transcribe.py "path\to\file.m4a"   a particular recording
    python tools\transcribe.py --vocab-only         just show the campaign names given to Whisper

Recordings live in the campaign's recordings/ folder (recording: in campaign.yml), which is never
built, published, or committed. The transcript is written next to the recording as <name>.transcript.txt,
one line per stretch of speech with its time: "[01:23:45] ...". Lines where someone seems to take
one of the campaign's items ("Tam grabs the Tidewalker Boots") are listed in <name>.items.json;
the Items page shows them for you to assign or dismiss - nothing is assigned by itself.

Speech-to-text is faster-whisper (an open-source Whisper) running on the CPU. It's given the
campaign's own names - party, the current city's NPCs and places, factions, items - so it spells
your characters' and places' names instead of guessing. Writing the session's page from the transcript is a
separate step (ask Claude: "write up the session from <transcript>").
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from codex import settings as codex_settings  # noqa: E402

CAMPAIGN = codex_settings.load(ROOT)
DATA = ROOT / "data"
RECORDINGS = CAMPAIGN["recordings_dir"]
AUDIO = (".m4a", ".mp3", ".wav", ".flac", ".ogg", ".webm", ".aac", ".wma")
MODEL = CAMPAIGN["transcribe"]["model"]
FOCUS = CAMPAIGN["focus"]  # campaign.yml: the city the party is in - its NPCs and places come first
HINT_CHARS = 700           # Whisper only reads a short hint; the most useful names go first


# ---------------------------------------------------------------- campaign vocabulary

def _names(node) -> list:
    """Every name and alias in a YAML tree, in file order."""
    out = []
    if isinstance(node, dict):
        for key in ("name", "character"):
            if isinstance(node.get(key), str):
                out.append(node[key])
        aliases = node.get("aliases")
        out += [a for a in (aliases if isinstance(aliases, list) else [aliases]) if isinstance(a, str)]
        for key, value in node.items():
            if key not in ("name", "character", "aliases"):
                out += _names(value)
    elif isinstance(node, list):
        for item in node:
            out += _names(item)
    return out


def _load(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None


def vocabulary(focus: str = FOCUS) -> list:
    """Campaign names, most useful first: the party, the focus city's people and places,
    factions, items, the campaign's own creatures, then everywhere else."""
    groups = [
        [DATA / "party.yml"],
        [DATA / "npcs" / f"{focus}.yml", DATA / "locations" / f"{focus}.yml"],
        [DATA / "factions.yml"],
        sorted((DATA / "items").glob("*.yml")),
        sorted(p for p in (DATA / "monsters").glob("*.yml")),
        sorted(p for p in list((DATA / "npcs").glob("*.yml")) + list((DATA / "locations").glob("*.yml"))
               if p.stem != focus),
    ]
    seen, names = set(), []
    for n, group in enumerate(groups):
        found = [_names(_load(path)) for path in group]
        if n == 1:   # the focus city: alternate its people and its places, so both make the hint
            people, places = found
            found = [[x for pair in zip(people, places) for x in pair] + people[len(places):] + places[len(people):]]
        for listed in found:
            for name in listed:
                name = " ".join(name.split())
                if len(name) < 3 or name.lower() in seen or not re.search(r"[A-Z]", name):
                    continue
                seen.add(name.lower())
                names.append(name)
    return names


# Words Whisper already spells right - titles and everyday words inside names ("Lady", "Old Town").
COMMON = set("""the a an of and in on at to for by with from lady lord sir dame master mistress captain sergeant
watchman governor chancellor king queen prince princess duke count baron house guild temple order inn tavern
old new town city castle hall tower bridge market row street gate gate's harbor harbour dock docks wharf
north south east west upper lower great little high low black white red blue green gold silver iron stone
sea storm river lake hill wood forest mountain bay cove landing district ward quarter square keep
brother sister father mother aunt uncle salt shadow night dark light blade council seven""".split())


def hint(names: list) -> str:
    """The short text Whisper is given. Only the distinctive words of each name, most useful
    first, so as much of the campaign as possible fits."""
    words, seen = [], set()
    for name in names:
        for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", name):
            w = w.strip("'")
            if len(w) < 3 or w.lower() in COMMON or w.lower() in seen:
                continue
            seen.add(w.lower())
            words.append(w)
    text = CAMPAIGN["transcribe"]["intro"].strip() + " "   # campaign.yml: what the recording is, then the names
    for w in words:
        if len(text) + len(w) + 2 > HINT_CHARS:
            break
        text += w + ", "
    return text.rstrip(", ") + "."


# ---------------------------------------------------------------- recording length

def _tool(name: str):
    """ffmpeg / ffprobe: on the PATH - including the user PATH as saved in Windows, which a window
    opened before ffmpeg was installed doesn't have yet - or where winget puts its shortcuts."""
    found = shutil.which(name)
    if found:
        return found
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            user_path = os.path.expandvars(winreg.QueryValueEx(key, "Path")[0])
        found = shutil.which(name, path=user_path)
        if found:
            return found
    except (ImportError, OSError):
        pass
    links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"
    return str(links) if links.is_file() else None


def _duration(probe: str, path: Path):
    out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def fix_length(audio: Path) -> None:
    """Browser recordings (.webm) are written a piece at a time, so they never record their total
    length - media players then can't show it or jump around. Copy the audio (unchanged, no
    re-encoding) into a file that has it, check that copy, and only then put it in place."""
    if audio.suffix.lower() != ".webm":
        return
    ffmpeg, ffprobe = _tool("ffmpeg"), _tool("ffprobe")
    if not ffmpeg or not ffprobe:
        print("(ffmpeg not found - the recording's length isn't added for media players; transcribing anyway.)")
        return
    if _duration(ffprobe, audio):
        return   # already has it
    fixed = audio.with_name(audio.stem + ".fixing.webm")
    result = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(audio), "-c", "copy", str(fixed)],
                            capture_output=True, text=True)
    length = _duration(ffprobe, fixed) if fixed.is_file() else None
    if result.returncode != 0 or not length or fixed.stat().st_size < audio.stat().st_size * 0.9:
        fixed.unlink(missing_ok=True)
        print("(Couldn't add the recording's length for media players - transcribing it as it is.)")
        return
    os.replace(fixed, audio)
    print(f"Added the recording's length ({_stamp(length)}) so media players can show it and skip around.")


# ---------------------------------------------------------------- transcription

def _stamp(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _echoes_hint(text: str, prompt: str) -> bool:
    """True if a line is just a piece of the name hint said back (a known Whisper habit in near
    silence), not speech: three or more words that are, in order, a stretch of the hint. (A name on
    its own - "Hester." - is left alone: people say those.)"""
    simple = lambda s: " ".join(re.sub(r"[^a-z0-9' ]", " ", s.lower()).split())
    words = simple(text)
    return len(words.split()) >= 3 and words in simple(prompt)


def merge_turns(audio: Path, lines: list):
    """(lines, count): the transcript's lines with the initiative tracker's turn log
    (<recording>.turns.txt, written during the session) woven in by time, marked ⚔."""
    log = audio.with_name(audio.stem + ".turns.txt")
    if not log.is_file():
        return lines, 0
    def seconds(line):
        m = re.match(r"^\[(\d\d):(\d\d):(\d\d)\]", line)
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None
    events = []
    for raw in log.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\[(\d\d:\d\d:\d\d)\] (.+)$", raw.strip())
        if m:
            events.append(f"[{m.group(1)}] ⚔ {m.group(2)}")
    tagged = [(seconds(ln), 1, n, ln) for n, ln in enumerate(lines)] + \
             [(seconds(ev), 0, n, ev) for n, ev in enumerate(events)]   # at the same second, the turn goes first
    tagged.sort(key=lambda t: (t[0] if t[0] is not None else 0, t[1], t[2]))
    return [t[3] for t in tagged], len(events)


# ---------------------------------------------------------------- item pickups

PICKUP = re.compile(r"\b(take|takes|took|taking|grab|grabs|grabbed|pick(?:s|ed)? (?:it )?up|pocket(?:s|ed)?|keep(?:s)?|kept|"
                    r"loot(?:s|ed)?|equip(?:s|ped)?|attune(?:s|d)?|put(?:s)? (?:it )?on|wear(?:s|ing)?|claim(?:s|ed)?|"
                    r"give(?:s)?|gave|hand(?:s|ed)?|mine|I'?ll have)\b", re.I)


def item_pickups(lines: list) -> list:
    """[{time, item_id, item, holder, line}] - a known item named near a taking word, in one line.
    The holder is a guess (a character or player named in that line), or empty for the DM to pick."""
    items = []
    for path in sorted((DATA / "items").glob("*.yml")):
        for it in _load(path) or []:
            if isinstance(it, dict) and it.get("name"):
                iid = str(it.get("id") or re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", str(it["name"]).lower()
                                                                     .replace("'", "").replace("’", ""))).strip("-"))
                for n in [it["name"]] + list(it.get("aliases") or []):
                    items.append((re.compile(r"\b" + re.escape(str(n)) + r"\b", re.I), iid, str(it["name"])))
    party = _load(DATA / "party.yml") or {}
    who = []
    for p in party.get("members") or []:
        if isinstance(p, dict) and p.get("character"):
            char = str(p["character"])
            for n in {char, char.split()[0].rstrip("-"), str(p.get("player") or "")} - {""}:
                who.append((re.compile(r"\b" + re.escape(n) + r"\b", re.I), char))
    found, seen = [], set()
    for line in lines:
        m = re.match(r"^\[(\d\d:\d\d:\d\d)\] (.*)$", line)
        if not m or "⚔" in line or not PICKUP.search(m.group(2)):   # not the tracker's turn log
            continue
        for rx, iid, name in items:
            if rx.search(m.group(2)):
                holder = next((char for wrx, char in who if wrx.search(m.group(2))), "")
                if (iid, holder) not in seen:
                    seen.add((iid, holder))
                    found.append({"time": m.group(1), "item_id": iid, "item": name, "holder": holder,
                                  "line": m.group(2)[:300]})
    return found


def newest_recording():
    files = [p for p in RECORDINGS.glob("*") if p.suffix.lower() in AUDIO] if RECORDINGS.is_dir() else []
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def transcribe(audio: Path, model_name: str, prompt: str) -> Path:
    from faster_whisper import WhisperModel   # imported here so --vocab-only works without it

    out = audio.with_name(audio.stem + ".transcript.txt")
    print(f"Loading the {model_name} speech model (the first time, this downloads about 1.6 GB)...")
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    started = time.time()
    segments, info = model.transcribe(
        str(audio), language="en", vad_filter=True, beam_size=5,
        # The names are offered for every stretch of the recording, and each stretch isn't fed
        # the previous one's text - that keeps a long session from drifting into repeated lines.
        hotwords=prompt, condition_on_previous_text=False,
    )
    total = info.duration or 1
    print(f"Recording: {audio.name}, {_stamp(total)} long. Transcribing...")
    lines, last, echoes = [], 0.0, 0
    for seg in segments:
        text = seg.text.strip()
        if text and _echoes_hint(text, prompt):
            echoes += 1   # Whisper sometimes "hears" its own name hint in a quiet stretch - not real speech
        elif text:
            lines.append(f"[{_stamp(seg.start)}] {text}")
        if time.time() - last > 15:   # progress, about every 15 seconds
            last = time.time()
            done = seg.end / total
            spent = last - started
            left = spent / done - spent if done > 0.01 else 0
            print(f"  {done:5.1%}  at {_stamp(seg.end)} of the recording - about {_stamp(left)} to go", flush=True)
    took = time.time() - started
    lines, turns = merge_turns(audio, lines)
    header = [f"# Transcript of {audio.name}",
              f"# Length {_stamp(total)} - transcribed in {_stamp(took)} with {model_name} on this computer.",
              "# Raw speech-to-text: names and table talk are as heard. Not for publishing."]
    if turns:
        header.append(f"# Lines marked ⚔ are the initiative tracker's turn log ({turns} entries), at the same clock.")
    if echoes:
        header.append(f"# {echoes} line(s) left out: the speech model repeated its own name list during quiet stretches.")
    pickups = item_pickups(lines)
    if pickups:
        import json
        audio.with_name(audio.stem + ".items.json").write_text(
            json.dumps(pickups, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
        header.append(f"# {len(pickups)} possible item pickup(s) - see the Items page on the site to assign or dismiss them.")
    header.append("")
    out.write_text("\n".join(header + lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Done in {_stamp(took)}: {out}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe a session recording.")
    ap.add_argument("audio", nargs="?", help="recording to transcribe (default: newest in the recordings folder)")
    ap.add_argument("--model", default=MODEL, help=f"speech model (default {MODEL})")
    ap.add_argument("--focus", default=FOCUS, help=f"city whose names come first (default {FOCUS})")
    ap.add_argument("--vocab-only", action="store_true", help="just show the names given to Whisper")
    args = ap.parse_args()

    names = vocabulary(args.focus)
    prompt = hint(names)
    if args.vocab_only:
        print(f"{len(names)} campaign names found; the hint Whisper gets ({len(prompt)} characters):\n\n{prompt}")
        return 0
    audio = Path(args.audio) if args.audio else newest_recording()
    if not audio or not audio.is_file():
        print(f"No recording found. Put it in {RECORDINGS} or give its path.")
        return 1
    fix_length(audio)
    transcribe(audio, args.model, prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
