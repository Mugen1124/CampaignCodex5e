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

MARKER = re.compile(r"^[ \t]*\{\{\s*(rules|conditions|spells|srd-magic-items|rules-credit)\b\s*([^}]*?)\s*\}\}[ \t]*$",
                    re.MULTILINE)


def on_config(config, **kwargs):
    rules.load(Path(config.config_file_path).parent)
    if not rules.loaded():
        log.warning("No rules data (data/rules/srd.json) - run: python tools/import_rules.py")
    return config


def on_page_markdown(markdown, page, config, files, **kwargs):
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
