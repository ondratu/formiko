"""Tests for :meth:`formiko.renderer.Renderer._embed_stylesheet`.

MistunePreview renders straight to HTML without going through docutils'
``publish_string``, so it never benefits from docutils' own
``embed_stylesheet`` setting. ``_embed_stylesheet`` mirrors that behaviour
by hand, inlining a user-selected ``.css`` file's content into the
generated ``<head>``.
"""

import gi

gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
gi.require_version("WebKit", "6.0")

from formiko.renderer import Renderer  # noqa: E402

_HTML = "<html><head><meta charset='utf-8'></head><body>hi</body></html>"


def test_embed_stylesheet_inlines_css_file_content(tmp_path):
    """CSS file content is inlined as a <style> tag inside <head>."""
    css_file = tmp_path / "custom.css"
    css_file.write_text("body { color: red; }")

    html = Renderer._embed_stylesheet(_HTML, str(css_file))

    assert "<style>body { color: red; }</style>" in html
    assert html.index("<style>") < html.index("</head>")


def test_embed_stylesheet_is_noop_without_style_path():
    """An empty style path leaves the HTML untouched."""
    assert Renderer._embed_stylesheet(_HTML, "") == _HTML


def test_embed_stylesheet_ignores_missing_file():
    """A style path that can't be read leaves the HTML untouched."""
    html = Renderer._embed_stylesheet(_HTML, "/no/such/file.css")
    assert html == _HTML
