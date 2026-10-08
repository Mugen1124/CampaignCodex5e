"""
The player site (mkdocs-players.yml): the parts of the campaign the players may see.

Only used by the player build - mkdocs-players.yml lists it first among its hooks and sets
`extra: audience: players`, which the other hooks read too (campaign.py, maps.py, entities.py
each leave out their DM-only parts). This hook does the page-level work:

- The home page is the latest session page (docs/sessions/, newest first - see codex/sessions.py),
  or docs/players/about.md while there are no sessions yet, instead of the DM's This Session page.
- DM-only boxes are taken out of every page before it's built: ??? dm / !!! dm blocks, and
  "Needs decision" warnings. So are any stretches wrapped in
      <!-- players: hide -->  ...  <!-- players: end -->
  (invisible on the DM site). The other way round, text written as
      <!-- players: show
      Text only the players' site shows.
      -->
  is a hidden comment on the DM site and ordinary text on the player site.
- Every other <!-- comment --> in a page is removed too, so a note to yourself never ends up in
  the players' page source.
- Links to pages the player site doesn't have (arc prep, encounters...) become plain text.
- Images and PDFs no player page uses (arc handouts, prep art) are deleted from the built site;
  MkDocs copies every file in docs/ whether a page uses it or not.

Pages themselves are chosen two ways: exclude_docs in mkdocs-players.yml (whole folders, like
arcs/), and `dm_only: true` in a page's own front matter - either way the page is never built, so
it can't be found or searched. tools/leak_check.py checks the finished site.
"""

import logging
import posixpath
import re
from pathlib import Path

from mkdocs.plugins import event_priority

import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex import sessions as codex_sessions  # noqa: E402

log = logging.getLogger("mkdocs.hooks.players")

ABOUT = "players/about.md"
HOME = [ABOUT]   # set in on_files: the latest session, or the About page
DM_BOX = re.compile(r"^(\s*)(\?\?\?\+?|!!!)\s+(dm|warning)\b.*$")
HIDE = re.compile(r"<!--\s*players:\s*hide\s*-->.*?<!--\s*players:\s*end\s*-->", re.S)
SHOW = re.compile(r"<!--\s*players:\s*show[ \t]*\n(.*?)-->", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)
LINK = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+?\.md)(#[^)\s]*)?\)(\{[^}]*\})?")


def players(config) -> bool:
    return (config.get("extra") or {}).get("audience") == "players"


FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
DM_ONLY = re.compile(r"^dm_only:\s*(true|yes)\s*$", re.M | re.I)


def dm_only(path: str) -> bool:
    """A page that says `dm_only: true` in its front matter."""
    try:
        head = Path(path).read_text(encoding="utf-8")[:2000]
    except OSError:
        return False
    m = FRONT.match(head)
    return bool(m and DM_ONLY.search(m.group(1)))


def on_files(files, config, **kwargs):
    if not players(config):
        return files
    for f in list(files.documentation_pages()):
        if dm_only(f.abs_src_path):
            files.remove(f)
    HOME[0] = codex_sessions.latest(Path(config["docs_dir"])) or ABOUT
    home = files.get_file_from_path(HOME[0])
    dm_home = files.get_file_from_path("index.md")
    if dm_home:
        files.remove(dm_home)
    if home:
        home.dest_uri = "index.html"   # set before anything reads its url
    else:
        log.warning("Player site: %s is missing - the site has no home page", HOME[0])
    return files


def strip_dm(markdown: str) -> str:
    """Remove DM boxes (the marker line and everything indented under it) and hidden stretches;
    un-hide the players-only text."""
    markdown = SHOW.sub(lambda m: m.group(1), HIDE.sub("", markdown))
    markdown = COMMENT.sub("", markdown)   # anything else in <!-- --> was a note to the DM
    out, skipping, indent = [], False, ""
    for line in markdown.split("\n"):
        if skipping:
            if not line.strip() or (len(line) - len(line.lstrip())) > len(indent):
                continue            # still inside the box (blank or indented further)
            skipping = False
        m = DM_BOX.match(line)
        if m:
            skipping, indent = True, m.group(1)
            continue
        out.append(line)
    return "\n".join(out)


def unlink_missing(markdown: str, page, files) -> str:
    """[text](page.md#x) to a page the player site doesn't have -> just the text."""
    here = posixpath.dirname(page.file.src_uri)

    def fix(m):
        target = posixpath.normpath(posixpath.join(here, m.group(2)))
        f = files.get_file_from_path(target)
        if f and not f.inclusion.is_excluded():
            return m.group(0)
        if target == "index.md":   # the DM's Now page -> the players' home
            return m.group(0).replace(m.group(2), posixpath.relpath(HOME[0], here or "."))
        return m.group(1)
    return LINK.sub(fix, markdown)


@event_priority(100)   # first, before the other hooks add their own markdown
def on_page_markdown(markdown, page, config, files, **kwargs):
    if not players(config):
        return markdown
    return unlink_missing(strip_dm(markdown), page, files)


MEDIA = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".pdf")


def unused_media(site: Path) -> list:
    """Images and PDFs in the built site that no page, stylesheet or script refers to."""
    used = " ".join(p.read_text(encoding="utf-8", errors="ignore") for p in site.rglob("*")
                    if p.suffix.lower() in (".html", ".css", ".js", ".json", ".webmanifest"))
    return [p for p in site.rglob("*") if p.suffix.lower() in MEDIA and p.name not in used
            and "assets/images/favicon" not in p.as_posix()]


A_TAG = re.compile(r'<a\b([^>]*?)\bhref="([^"]*)"([^>]*)>(.*?)</a>', re.S)


def on_post_build(config, **kwargs):
    """Last pass over the finished player site: any link to a page that isn't there, or to a
    part of a page that isn't there (a hidden map, a district not come across yet), becomes
    plain text - so nothing points at what the players can't see."""
    if not players(config):
        return
    site = Path(config["site_dir"]).resolve()
    pages = {p.resolve(): p.read_text(encoding="utf-8") for p in site.rglob("*.html")}
    ids = {p: set(re.findall(r'\bid="([^"]+)"', text)) for p, text in pages.items()}
    fixed = 0
    for path, text in pages.items():
        def fix(m):
            nonlocal fixed
            href = m.group(2)
            if re.match(r"^([a-z]+:|//|mailto:|\.\./assets/|assets/)", href) or not href or href.startswith("javascript"):
                return m.group(0)
            target, _, anchor = href.partition("#")
            dest = path if not target else (path.parent / target).resolve()
            if target.endswith(".md"):   # a link the build couldn't resolve: its page isn't on this site (dm_only)
                fixed += 1
                return m.group(4)
            if target and not target.endswith(".html"):
                return m.group(0)   # downloads, images, the search index
            if dest not in ids or (anchor and anchor not in ids[dest]):
                fixed += 1
                return m.group(4)
            return m.group(0)
        new = A_TAG.sub(fix, text)
        if new != text:
            path.write_text(new, encoding="utf-8")
    if fixed:
        log.info("Player site: %d link(s) to pages or sections players don't have became plain text", fixed)
    unused = unused_media(site)
    for p in unused:
        p.unlink()
    if unused:
        log.info("Player site: %d image(s)/PDF(s) no player page uses were left out", len(unused))
