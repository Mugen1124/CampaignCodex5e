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


def update_test(proj: Path, tmp: Path):
    """A pretend release 9.9 - one engine file changed, one dropped - applied to a campaign whose
    mkdocs.yml is still the old single-file kind. Only the engine may change."""
    sys.path.insert(0, str(ROOT))
    from codex.update import MANIFEST, fingerprint, read_manifest
    manifest = read_manifest((ROOT / MANIFEST).read_text(encoding="utf-8"))
    # the campaign: an engine file the new release drops, and an old-style mkdocs.yml
    (proj / "tools" / "obsolete.py").write_text("# dropped in 9.9\n", encoding="utf-8")
    old_manifest = (proj / MANIFEST).read_text(encoding="utf-8") + f"{fingerprint(b'# dropped in 9.9' + bytes([10]))}  tools/obsolete.py\n"
    (proj / MANIFEST).write_text(old_manifest, encoding="utf-8")
    dm = (proj / "mkdocs.yml").read_text(encoding="utf-8")
    nav = dm[dm.index("\nnav:\n") + 1:]
    name = re.search(r"(?m)^site_name:.*$", dm).group(0)
    engine = (ROOT / "codex" / "site.yml").read_text(encoding="utf-8")
    (proj / "mkdocs.yml").write_text(name + "\n" + engine + "\n" + nav, encoding="utf-8")   # all in one file, as before 1.4
    mine = {p: (proj / p).read_bytes() for p in ("campaign.yml", "mkdocs-players.yml", "docs/index.md", "data/party.yml",
                                                  "docs/stylesheets/campaign.css", "CLAUDE.md", "README.md")}
    # the release
    rel = tmp / "release" / "Mugen1124-CampaignCodex5e-abc123"
    files = {p: (ROOT / p).read_bytes() for p in manifest}
    files["hooks/maps.py"] += b"\n# changed in 9.9\n"
    files["codex/version.txt"] = b"9.9\n"
    lines = ["# fake release"] + [f"{fingerprint(d)}  {p}" for p, d in sorted(files.items())]
    files[MANIFEST] = ("\n".join(lines) + "\n").encode()
    for p, d in files.items():
        (rel / p).parent.mkdir(parents=True, exist_ok=True)
        (rel / p).write_bytes(d)
    zpath = tmp / "release.zip"
    shutil.make_archive(str(zpath.with_suffix("")), "zip", rel.parent)
    r = run(proj, "-m", "codex", "update", "--zip", zpath, "--yes")
    out = r.stdout + r.stderr
    check("update runs, and the check after it passes", r.returncode == 0, out[-3000:])
    check("update: the changed engine file is replaced", (proj / "hooks" / "maps.py").read_text(encoding="utf-8").endswith("# changed in 9.9\n"))
    check("update: the engine file the release dropped is removed", not (proj / "tools" / "obsolete.py").exists())
    check("update: the version is 9.9", (proj / "codex" / "version.txt").read_text(encoding="utf-8").strip() == "9.9")
    untouched = [p for p, d in mine.items() if (proj / p).read_bytes() != d]
    check("update: your campaign's files aren't touched", not untouched, ", ".join(untouched))
    new_dm = (proj / "mkdocs.yml").read_text(encoding="utf-8")
    check("update: an old mkdocs.yml becomes name + menus, inheriting the engine",
          new_dm.startswith("#") and "INHERIT: codex/site.yml" in new_dm and nav.strip() in new_dm and name in new_dm
          and "markdown_extensions" not in new_dm and (proj / "mkdocs.yml.before-update").is_file(), new_dm[:800])
    check("update: a backup was made first", any((proj.parent / f"{proj.name}-backups").glob("*.zip")))
    r = run(proj, "-m", "codex", "update", "--zip", zpath, "--yes")
    check("update again: already up to date", "Already up to date" in r.stdout, r.stdout[-500:])


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "campaign"
        copy_project(proj)

        r = run(ROOT, "tools/engine_manifest.py", "--check")
        check("the engine manifest (codex/engine-files.txt) is up to date", r.returncode == 0, r.stdout)

        print("The demo:")
        out = build_both(proj, "demo")
        players = out / "players"
        check("demo: dm_only page left out", not (players / "cities" / "greywater" / "events.html").exists())
        check("demo: DM-only map left out", not any(players.rglob("bellwether-light*")))
        check("demo: guide left out", not (players / "guide").exists())
        dead = [p.relative_to(players).as_posix() for p in players.rglob("*.html")
                if re.search(r'href="[^"#]*\.md(#[^"]*)?"', p.read_text(encoding="utf-8"))]
        check("demo: no leftover links to pages the players' site doesn't have", not dead, ", ".join(dead[:5]))

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

        print("My Notes:")
        check("the players' site has a My Notes page, in its menu", (players / "players" / "notes.html").is_file()
              and 'href="players/notes.html"' in pl_home)
        check("the DM site doesn't", not (out / "dm" / "players" / "notes.html").exists())
        worker = (proj / "publish" / "players" / "worker.js").read_text(encoding="utf-8")
        check("the players' worker keeps each player's notes", '"/api/notes"' in worker and "class Notes" in worker)
        r = run(proj, "-c", "import json; from codex import publish; publish.write_configs({'online': "
                "{'dm_worker': 'dm', 'players_worker': 'pl'}, 'access_url': 'https://team.cloudflareaccess.com'}); "
                "t = open('publish/players/wrangler.jsonc', encoding='utf-8').read().split('\\n', 1)[1]; c = json.loads(t); "
                "print([b['class_name'] for b in c['durable_objects']['bindings']], [m['tag'] for m in c['migrations']])")
        check("publish sets up the notes store for Cloudflare", "'Notes'" in r.stdout and "'v3'" in r.stdout, r.stdout + r.stderr)

        print("The rules encyclopedia:")
        spells = (out / "dm" / "rules" / "spells.html").read_text(encoding="utf-8")
        check("every spell is on the Spells page", spells.count('class="rules-entry spell') == 319)
        rules_home = (out / "dm" / "rules" / "index.html").read_text(encoding="utf-8")
        check("the Rules page ends with the SRD credit, not an error box",
              "System Reference Document 5.1" in rules_home and "Missing rules section" not in rules_home)
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
        party_before = (proj / "data" / "party.yml").read_bytes()
        r = run(proj, "-m", "codex", "new", "--name", "Oops", "--town", "Nowhere", "--yes", "--no-backup")
        check("wizard: refuses to run again on a campaign of your own", r.returncode != 0
              and (proj / "data" / "party.yml").read_bytes() == party_before, r.stdout[-800:])
        after = build_both(proj, "after the wizard")
        about = (after / "players" / "index.html").read_text(encoding="utf-8")
        check("after the wizard: with no sessions yet, the players' site opens on About", bool(re.search(r"<h1[^>]*>About this site", about)))

        print("Builds outside the folder (output: local):")
        local = Path(tmp) / "local-cache"
        conf = proj / "campaign.yml"
        conf_text = conf.read_text(encoding="utf-8")
        conf.write_text(conf_text.replace("output: here", "output: local"), encoding="utf-8")
        shutil.rmtree(proj / ".map-cache", ignore_errors=True)
        for cache in list(proj.rglob("__pycache__")):   # left by this test's own direct mkdocs builds
            shutil.rmtree(cache, ignore_errors=True)
        # PYTHONDONTWRITEBYTECODE as the launchers set it, before Python starts
        env = {"LOCALAPPDATA": str(local), "XDG_CACHE_HOME": str(local), "HOME": str(Path(tmp) / "home"),
               "PYTHONDONTWRITEBYTECODE": "1"}
        local = Path(run(proj, "-c", "from codex.paths import local_dir; print(local_dir())", env=env).stdout.strip())
        r = run(proj, "-m", "codex", "build", env=env)
        built = list(local.rglob("site/index.html"))
        check("codex build puts the site outside the folder", r.returncode == 0 and bool(built) and not (proj / "site").exists(),
              r.stdout[-1500:] + r.stderr[-1500:])
        r = run(proj, "-c", "from codex import settings; s = settings.load(); print(s['map_cache']); print(s['publish_dir'])", env=env)
        check("...and the map cache and publish builds too", not (proj / ".map-cache").exists()
              and all(Path(p).is_relative_to(local) for p in r.stdout.split()), r.stdout + r.stderr)
        check("no __pycache__ in the folder", not any(p for p in proj.rglob("__pycache__")
                                                     if ".venv" not in p.parts))
        r = run(proj, "codex/paths.py", "venv", env=env)
        check("setup would put the Python packages outside the folder too", Path(r.stdout.strip()).is_relative_to(local),
              r.stdout + r.stderr)
        conf.write_text(conf_text, encoding="utf-8")

        print("codex update:")
        update_test(proj, Path(tmp))

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
