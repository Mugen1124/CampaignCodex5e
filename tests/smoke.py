"""
End-to-end checks, on a throwaway copy of this folder (your files are never touched):

  1. the demo builds - both sites - with no warnings, and the leak check passes
  2. a secret pasted into public text is caught: the leak check fails
  3. a dm_only page and a DM-only map never reach the players' site
  4. the setup wizard (`new`) replaces the demo, and the result builds and passes too

    python tests/smoke.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
SKIP = {".git", ".venv", "site", "legacy", "__pycache__", ".map-cache", "sources", "recordings"}
FAILED = []


def copy_project(dest: Path):
    def ignore(d, names):
        rel = Path(d).relative_to(ROOT)
        out = {n for n in names if n in SKIP}
        if rel == Path("publish"):
            out |= {"site"}
        if rel == Path("publish/players"):
            out |= {"site", "roster.json"}
        return out
    shutil.copytree(ROOT, dest, ignore=ignore)


def run(cwd: Path, *args, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *map(str, args)], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=dict(os.environ, **(env or {})))


def build(cwd: Path, config: str, out: Path) -> list:
    r = run(cwd, "-m", "mkdocs", "build", "--clean", "-f", config, "--site-dir", out, env={"OFFLINE": "false"})
    if r.returncode != 0:
        FAILED.append(f"{config} build failed:\n{r.stdout}\n{r.stderr}")
    return [ln for ln in (r.stdout + r.stderr).splitlines() if "WARNING" in ln or "ERROR" in ln]


def check(name: str, ok: bool, detail: str = ""):
    print(("  ok    " if ok else "  FAIL  ") + name)
    if not ok:
        FAILED.append(name + (f"\n{detail}" if detail else ""))


def build_both(proj: Path, label: str) -> Path:
    out = proj / "_test_out"
    warn_dm = build(proj, "mkdocs.yml", out / "dm")
    warn_pl = build(proj, "mkdocs-players.yml", out / "players")
    check(f"{label}: DM site builds without warnings", not warn_dm, "\n".join(warn_dm))
    check(f"{label}: players' site builds without warnings", not warn_pl, "\n".join(warn_pl))
    r = run(proj, "tools/leak_check.py", out / "players")
    check(f"{label}: leak check passes", r.returncode == 0, r.stdout[-2000:])
    return out


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "campaign"
        copy_project(proj)

        print("The demo:")
        out = build_both(proj, "demo")
        players = out / "players"
        check("demo: dm_only page left out", not (players / "cities" / "greywater" / "events.html").exists())
        check("demo: DM-only map left out", not any(players.rglob("bellwether-light*")))
        check("demo: guide left out", not (players / "guide").exists())

        print("The Sessions tab:")
        dm_home = (out / "dm" / "index.html").read_text(encoding="utf-8")
        check("the DM site opens on This Session", bool(re.search(r"<h1[^>]*>This Session", dm_home)))
        world = (out / "dm" / "world" / "index.html").read_text(encoding="utf-8")
        sidebar = re.sub(r"\s+", " ", world[world.find("md-nav--primary"):world.find("md-nav--secondary")])
        check("This Session is first in the Sessions sidebar, then the sessions",
              0 < sidebar.find("This Session </span>") < sidebar.find("Greywater — Session 1"), sidebar[:1500])
        pl_home = (players / "index.html").read_text(encoding="utf-8")
        check("the players' site opens on the latest session", bool(re.search(r"<h1[^>]*>Greywater — Session 1: The Missing Bell", pl_home)))
        check("This Session isn't on the players' site", ">This Session<" not in pl_home and "Ambush on the quay" not in pl_home)

        print("The rules encyclopedia:")
        spells = (out / "dm" / "rules" / "spells.html").read_text(encoding="utf-8")
        check("every spell is on the Spells page", spells.count('class="rules-entry spell') == 319)
        check("the rules are on the players' site too", (players / "rules" / "dm-screen.html").is_file())
        bestiary = (out / "dm" / "reference" / "bestiary.html").read_text(encoding="utf-8")
        check("a condition in a stat block gets a hover card", 'data-ref="condition:' in bestiary)

        print("A banned word:")
        conf = proj / "campaign.yml"
        conf_text = conf.read_text(encoding="utf-8")
        conf.write_text(conf_text.replace("banned: []", "banned: [eel pie]"), encoding="utf-8")
        warnings = build(proj, "mkdocs.yml", out / "banned")
        check("the build warns about it", any("eel pie" in w for w in warnings), "\n".join(warnings))
        conf.write_text(conf_text, encoding="utf-8")

        print("A secret pasted into public text:")
        page = proj / "docs" / "world" / "index.md"
        original = page.read_text(encoding="utf-8")
        npcs = yaml.safe_load((proj / "data" / "npcs" / "greywater.yml").read_text(encoding="utf-8"))
        secret = " ".join(next(n for n in npcs if n["id"] == "corvin-sloane")["secret"].split())
        page.write_text(original + "\n" + secret + "\n", encoding="utf-8")
        build(proj, "mkdocs-players.yml", out / "leaky")
        r = run(proj, "tools/leak_check.py", out / "leaky")
        check("leak check catches it", r.returncode != 0, r.stdout[-2000:])
        page.write_text(original, encoding="utf-8")

        print("The setup wizard:")
        r = run(proj, "-m", "codex", "new", "--name", "Ashes of Varn", "--town", "Kell's Crossing", "--arc", "The Long Road",
                "--party", "Sam:Kestra:Elf:Ranger", "--party", "Ana:Brother Ott:Human:Cleric", "--level", "2",
                "--yes", "--no-backup")
        check("wizard runs", r.returncode == 0, r.stdout + r.stderr)
        check("wizard: demo removed", not (proj / "docs" / "cities" / "greywater").exists())
        check("wizard: new town pages", (proj / "docs" / "cities" / "kells-crossing" / "index.md").is_file())
        after = build_both(proj, "after the wizard")
        about = (after / "players" / "index.html").read_text(encoding="utf-8")
        check("after the wizard: with no sessions yet, the players' site opens on About", bool(re.search(r"<h1[^>]*>About this site", about)))

    print()
    if FAILED:
        print(f"{len(FAILED)} check(s) failed:\n")
        for f in FAILED:
            print(" - " + f + "\n")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
