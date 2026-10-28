"""Regression tests for Debian bug #933622 (ampersand escaping).

A link with ``&`` in its URL made Gtk warn "Entity did not end with a
semicolon", because the hover label is Pango markup and the URL was
inserted unescaped.
"""

import contextlib
from types import SimpleNamespace

import gi
import pytest

gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
gi.require_version("Pango", "1.0")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from gi.repository import GLib, Pango  # noqa: E402

from formiko.browser import HoverTarget  # noqa: E402
from formiko.renderer import Renderer  # noqa: E402

URL = "https://wiki.debian.org/Page?action=diff&rev2=85&rev1=83"


class _FakeLabel:
    def __init__(self):
        self.markup = None

    def set_markup(self, markup):
        self.markup = markup

    def show(self):
        pass

    def is_visible(self):
        return False

    def hide(self):
        pass


def _hover(kind, uri):
    adapter = SimpleNamespace(label=_FakeLabel())
    Renderer._on_hover_changed(adapter, HoverTarget(kind, uri))
    return adapter.label.markup


@pytest.mark.parametrize("kind", ["link", "image", "media"])
def test_hover_label_with_ampersand_is_valid_pango(kind):
    """The hover label markup parses and shows the URL unchanged."""
    markup = _hover(kind, URL)

    _ok, _attrs, text, _accel = Pango.parse_markup(markup, -1, "\0")
    assert URL in text


def test_unescaped_markup_is_what_gtk_rejected():
    """Sanity check: the markup without escaping fails like the bug."""
    with pytest.raises(GLib.Error):
        Pango.parse_markup(f"<span> {URL} </span>", -1, "\0")


def test_hover_label_with_other_markup_characters():
    """'<', '>' and '"' in a URL must not break the hover label either."""
    uri = URL + '&q=<b>"x"'
    markup = _hover("link", uri)
    _ok, _attrs, text, _accel = Pango.parse_markup(markup, -1, "\0")
    assert uri in text


def _render(parser, src):
    """Run the real Renderer.render_output for *parser* on *src*."""
    renderer = Renderer(SimpleNamespace(running=False), parser=parser)
    renderer.src = src
    renderer.file_name = "doc.md"
    ok, html, _mime = renderer.render_output()
    assert ok, html
    return html


@pytest.mark.parametrize("parser", ["m2r", "mistune"])
def test_markdown_ampersand_in_link_is_escaped_in_html(parser):
    """The Markdown converters emit ``&amp;`` in the generated HTML."""
    if parser == "mistune":
        pytest.importorskip("mistune")
    html = _render(parser, f"[diff]({URL})\n\n<{URL}>\n")

    assert "&rev2" not in html
    assert "&amp;rev2=85" in html
