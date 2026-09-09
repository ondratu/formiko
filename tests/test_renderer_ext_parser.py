"""Tests for :func:`formiko.renderer.resolve_ext_parser`.

Markdown files can be handled by more than one parser (m2r2, the default,
or mistune, rendered directly to HTML). Unlike every other extension in
``EXTS`` - which is a fixed 1:1 mapping - ``.md`` must respect the user's
currently preferred markdown parser, so switching to Mistune in
Preferences stays in effect across files.
"""

import pytest

from formiko.renderer import (
    EXTS,
    PARSERS,
    WRITERS,
    component_available,
    resolve_ext_parser,
)
from formiko.utils import Undefined

MISTUNE_AVAILABLE = not issubclass(PARSERS["mistune"]["class"], Undefined)
M2R_AVAILABLE = not issubclass(PARSERS["m2r"]["class"], Undefined)


def test_unavailable_components_are_detected():
    """Undefined parser and writer classes are not selectable."""
    assert component_available(PARSERS["rst"])
    assert component_available(WRITERS["html4"])
    assert not component_available(
        {"class": type("Missing", (Undefined,), {})},
    )


def test_md_keeps_users_preferred_markdown_parser():
    """A preference for m2r2 or mistune is respected for .md files."""
    if MISTUNE_AVAILABLE:
        assert resolve_ext_parser(".md", "mistune") == "mistune"
    if M2R_AVAILABLE:
        assert resolve_ext_parser(".md", "m2r") == "m2r"
    if not MISTUNE_AVAILABLE and not M2R_AVAILABLE:
        pytest.skip("no Markdown parser is installed")


def test_md_falls_back_to_default_for_non_markdown_preference():
    """A non-markdown preference falls back to the m2r2 default."""
    assert resolve_ext_parser(".md", "rst") == EXTS.get(".md", "rst")


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
    if ".md" not in EXTS:
        pytest.skip("no Markdown parser is installed")
    monkeypatch.setitem(
        PARSERS["mistune"], "class", type("Missing", (Undefined,), {}),
    )
    assert resolve_ext_parser(".md", "mistune") == EXTS[".md"]
