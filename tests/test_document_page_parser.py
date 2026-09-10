"""Regression test for GH issue #59: automatic parser selection by file type.

In Formiko <= 1.5.0, ``Window.on_file_type()`` only updated the
preferences-menu display (``self.pref_menu.set_parser(parser)``) but never
told the renderer about the new parser, and never persisted it to
``self.preferences.parser``.  As a result, once the ``parser`` config
value was set to something other than the file's own extension (e.g.
after ``parser = rst`` was stored while a ``.md`` file was open), opening
a new file with a different extension kept using the stale parser instead
of switching automatically based on the file's extension.

This was fixed in the ``DocumentPage._on_file_type`` rewrite (part of the
2.0.0 tab-support refactor): it now calls ``self.renderer.set_parser(...)``
and updates ``self.preferences.parser`` for every file-type change.
"""

import contextlib
from unittest.mock import Mock

import gi
import pytest

gi.require_version("GtkSource", "5")
gi.require_version("Adw", "1")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from formiko.document_page import DocumentPage  # noqa: E402
from formiko.editor import EditorType  # noqa: E402
from formiko.renderer import EXTS  # noqa: E402


def _make_fake_page(initial_parser: str) -> Mock:
    """Build a duck-typed stand-in for ``DocumentPage``.

    Only the attributes touched by ``_on_file_type`` are provided, so the
    method under test can run without building a real GTK widget tree.
    """
    page = Mock()
    page.editor_type = EditorType.SOURCE
    page.preferences = Mock()
    page.preferences.parser = initial_parser
    page.file_path = ""
    page._window = Mock(spec=["on_active_tab_parser_changed", "wakatime"])
    return page


def test_exts_maps_known_extensions_to_dedicated_parsers():
    """Known extensions map to their dedicated parsers."""
    assert EXTS[".rst"] == "rst"
    assert EXTS[".html"] == "html"
    assert EXTS[".htm"] == "html"
    assert EXTS[".json"] == "json"
    # Present only when m2r2 or mistune is installed.
    assert EXTS.get(".md") in ("md", "m2r", "mistune", None)


def test_on_file_type_switches_renderer_parser_for_known_extension():
    """Opening a .md file selects its parser regardless of stale settings.

    The configured parser starts as ``rst``, mirroring the reported bug.
    """
    if ".md" not in EXTS:
        pytest.skip("no Markdown parser is installed")
    page = _make_fake_page(initial_parser="rst")

    DocumentPage._on_file_type(page, None, ".md")

    expected_parser = EXTS[".md"]
    page.renderer.set_parser.assert_called_once_with(expected_parser)
    assert page.preferences.parser == expected_parser


def test_on_file_type_switches_back_for_rst_extension():
    """Opening an .rst file switches back from a Markdown parser.

    The configured parser starts as the installed Markdown parser.
    """
    if ".md" not in EXTS:
        pytest.skip("no Markdown parser is installed")
    page = _make_fake_page(initial_parser=EXTS[".md"])

    DocumentPage._on_file_type(page, None, ".rst")

    page.renderer.set_parser.assert_called_once_with("rst")
    assert page.preferences.parser == "rst"


def test_on_file_type_keeps_current_parser_for_unknown_extension():
    """Unknown extensions keep the configured parser instead of crashing."""
    page = _make_fake_page(initial_parser="rst")

    DocumentPage._on_file_type(page, None, ".txt")

    page.renderer.set_parser.assert_called_once_with("rst")
    assert page.preferences.parser == "rst"
