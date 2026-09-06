"""Tests for :func:`formiko.renderer.resolve_ext_parser`.

Markdown files can be handled by more than one parser (m2r2, the default,
or mistune, rendered directly to HTML). Unlike every other extension in
``EXTS`` - which is a fixed 1:1 mapping - ``.md`` must respect the user's
currently preferred markdown parser, so switching to Mistune in
Preferences stays in effect across files.
"""

from formiko.renderer import EXTS, PARSERS, resolve_ext_parser
from formiko.utils import Undefined


def test_md_keeps_users_preferred_markdown_parser():
    """A preference for m2r2 or mistune is respected for .md files."""
    assert resolve_ext_parser(".md", "mistune") == "mistune"
    assert resolve_ext_parser(".md", "m2r") == "m2r"


def test_md_falls_back_to_default_for_non_markdown_preference():
    """A non-markdown preference falls back to the m2r2 default."""
    assert resolve_ext_parser(".md", "rst") == "m2r"


def test_other_extensions_are_unaffected_by_markdown_preference():
    """Extensions other than .md ignore the markdown-parser preference."""
    assert resolve_ext_parser(".rst", "mistune") == "rst"
    assert resolve_ext_parser(".html", "mistune") == "html"


def test_unknown_extension_falls_back_to_preferred():
    """An unmapped extension keeps whatever parser is already active."""
    assert resolve_ext_parser(".txt", "mistune") == "mistune"


def test_md_ignores_preferred_parser_when_unavailable(monkeypatch):
    """A preferred markdown parser that isn't installed is never picked.

    Otherwise a persisted preference for a parser that later became
    unavailable (package removed, config synced to another machine) would
    make every .md file fail to render instead of falling back to the
    default.
    """
    monkeypatch.setitem(
        PARSERS["mistune"], "class", type("Missing", (Undefined,), {}),
    )
    assert resolve_ext_parser(".md", "mistune") == EXTS[".md"]
