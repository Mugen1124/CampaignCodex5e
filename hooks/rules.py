"""
The rules encyclopedia's pages: replaces the rules markers with the SRD's text (see codex/rules.py).
Listed before entities.py in mkdocs.yml, so the condition [[mentions]] it adds become hover cards.
"""

import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codex import rules  # noqa: E402

log = logging.getLogger("mkdocs.hooks.rules")

MARKER = re.compile(r"^[ \t]*\{\{\s*(rules-credit|rules|conditions|spells|srd-magic-items)(?![\w-])\s*([^}]*?)\s*\}\}[ \t]*$",
                    re.MULTILINE)


def on_config(config, **kwargs):
    rules.load(Path(config.config_file_path).parent)
    if not rules.loaded():
        log.warning("No rules data (data/rules/srd.json) - run: python tools/import_rules.py")
    return config


LETTERS_ONLY = set()   # pages with every magic item: their contents list is just the A-Z letters


def on_page_markdown(markdown, page, config, files, **kwargs):
    if any(m.group(1) == "srd-magic-items" for m in MARKER.finditer(markdown)):
        LETTERS_ONLY.add(page.file.src_uri)
    def render(m):
        kind, arg = m.group(1), m.group(2).split()
        if kind == "rules":
            return rules.render_sections(arg)
        if kind == "conditions":
            return rules.render_conditions()
        if kind == "spells":
            return rules.render_spells()
        if kind == "srd-magic-items":
            return rules.render_items()
        return rules.credit()
    return MARKER.sub(render, markdown)


def on_page_content(html, page, config, files, **kwargs):
    # The rules above the list keep their headings on the page; only the letters go in the right-hand contents.
    # (The page's # title is the top of the contents; its ## headings are the entries under it.)
    if page.file.src_uri in LETTERS_ONLY:
        for top in page.toc.items:
            top.children = [a for a in top.children if a.id.startswith("items-")]
    return html
