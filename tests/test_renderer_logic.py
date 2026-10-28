"""Display-less tests for pure logic in :class:`formiko.renderer.Renderer`.

Methods are borrowed from ``Renderer`` and run against duck-typed
adapters, so no GTK widget tree is created.
"""

import contextlib
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
gi.require_version("Pango", "1.0")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from docutils.parsers.rst import Parser  # noqa: E402

from formiko import renderer  # noqa: E402
from formiko.browser import HoverTarget  # noqa: E402
from formiko.directives import HtmlPreview  # noqa: E402
from formiko.renderer import PARSERS, WRITERS, Renderer  # noqa: E402
from formiko.utils import Undefined  # noqa: E402


def _adapter(parser="rst", writer="html4", **kwargs):
    """Adapter with just what ``render_output`` and friends touch."""
    ns = SimpleNamespace(
        src="Title\n=====\n\ntext\n",
        file_name="/tmp/x.rst",  # noqa: S108
        tab_width=8,
        style="",
        parser_instance=PARSERS[parser]["class"](),
        writer_instance=WRITERS[writer]["class"](),
        _embed_stylesheet=Renderer._embed_stylesheet,
    )
    ns._Renderer__parser = PARSERS[parser]
    ns._Renderer__writer = WRITERS[writer]
    for key, value in kwargs.items():
        setattr(ns, key, value)
    return ns


def test_rgba_to_hex():
    """Colour floats are converted to a #rrggbb string."""
    rgba = SimpleNamespace(red=1.0, green=0.5, blue=0.0)
    assert Renderer._rgba_to_hex(rgba) == "#ff8000"
    assert Renderer._rgba_to_hex(SimpleNamespace(red=0, green=0, blue=0)) == (
        "#000000"
    )


def test_render_output_without_source():
    """No source yet means nothing to render."""
    ns = _adapter(src=None)
    assert Renderer.render_output(ns) == (False, "", "text/plain")


def test_render_output_rst():
    """ReStructuredText is rendered to an HTML document."""
    ok, html, mime = Renderer.render_output(_adapter())
    assert ok
    assert mime == "text/html"
    assert "<h1" in html
    assert "Title" in html


@pytest.mark.xfail(
    strict=True,
    reason="render_output() builds the NOT_FOUND page but then falls "
    "through and returns the raw source instead",
)
def test_render_output_missing_parser():
    """A missing parser renders the "not found" page."""
    ns = _adapter()
    ns._Renderer__parser = {"class": None, "title": "Foo", "url": "http://u"}
    ok, html, mime = Renderer.render_output(ns)
    assert not ok
    assert "Component Foo Not Found" in html
    assert mime == "text/html"


@pytest.mark.xfail(
    strict=True,
    reason="render_output() builds the NOT_FOUND page but then falls "
    "through and returns the raw source instead",
)
def test_render_output_missing_writer():
    """A missing writer renders the "not found" page."""
    ns = _adapter()
    ns._Renderer__writer = {"class": None, "title": "Bar", "url": "http://u"}
    ok, html, _ = Renderer.render_output(ns)
    assert not ok
    assert "Component Bar Not Found" in html


def test_render_output_html_parser_returns_source():
    """The HTML parser passes the source through unchanged."""
    ns = _adapter(parser="html", src="<p>hi</p>")
    assert Renderer.render_output(ns) == (False, "<p>hi</p>", "text/html")


def test_render_output_json():
    """JSON is rendered by JSONPreview."""
    ns = _adapter(parser="json", src='{"a": 1}')
    ok, html, mime = Renderer.render_output(ns)
    assert ok
    assert mime == "text/html"
    assert "jnum" in html


def test_render_output_invalid_json_shows_data_error():
    """Invalid JSON is reported as a data error page."""
    ns = _adapter(parser="json", src="{nope")
    ok, html, _ = Renderer.render_output(ns)
    assert not ok
    assert "JSON Error!" in html


@pytest.mark.skipif(
    issubclass(PARSERS["mistune"]["class"], Undefined),
    reason="Mistune is an optional dependency",
)
def test_render_output_mistune_embeds_stylesheet(tmp_path):
    """Mistune output gets the chosen stylesheet inlined."""
    css = tmp_path / "s.css"
    css.write_text("p{color:red}")
    ns = _adapter(parser="mistune", src="# hi\n", style=str(css))
    ok, html, _ = Renderer.render_output(ns)
    assert ok
    assert "<style>p{color:red}</style>" in html


def test_render_output_pep_writer_uses_pep_reader():
    """The PEP writer switches to the PEP reader and drops the parser."""
    captured = {}

    def fake_publish(**kwargs):
        captured.update(kwargs)
        return b"<html>pep</html>"

    ns = _adapter(writer="pep")
    original = renderer.publish_string
    renderer.publish_string = fake_publish
    try:
        ok, html, _ = Renderer.render_output(ns)
    finally:
        renderer.publish_string = original
    assert ok
    assert html == "<html>pep</html>"
    assert captured["reader_name"] == "pep"
    assert "parser" not in captured


@pytest.mark.parametrize(
    ("error", "marker"),
    [
        (renderer.DataError("bad data"), "Data Error!"),
        (NotImplementedError("nope"), "Library Error"),
        (RuntimeError("boom"), "RuntimeError"),
    ],
)
def test_render_output_errors_become_pages(monkeypatch, error, marker):
    """Exceptions during publishing are shown as error pages."""

    def explode(**_kwargs):
        raise error

    monkeypatch.setattr(renderer, "publish_string", explode)
    ok, html, mime = Renderer.render_output(_adapter())
    assert not ok
    assert marker in html
    assert mime == "text/html"


def test_render_output_passes_settings_to_docutils(monkeypatch):
    """Tab width, file name and style are forwarded to docutils."""
    captured = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return b""

    monkeypatch.setattr(renderer, "publish_string", fake)
    Renderer.render_output(_adapter(tab_width=3, style="/s.css"))
    settings = captured["settings_overrides"]
    assert settings["tab_width"] == 3
    assert settings["stylesheet"] == "/s.css"
    assert captured["source_path"] == "/tmp/x.rst"  # noqa: S108
    assert isinstance(captured["parser"], Parser)


def test_html_preview_is_an_html_parser():
    """Sanity check of the class the HTML branch relies on."""
    assert issubclass(PARSERS["html"]["class"], HtmlPreview)


def _font_adapter():
    return SimpleNamespace(
        font_family="Sans",
        font_size_px=16,
        mono_family="Mono",
        mono_size_px=14,
        _apply_system_font=Mock(),
    )


class _Settings:
    def __init__(self, values):
        self.values = values

    def get_string(self, key):
        return self.values[key]


def test_read_system_font_uses_desktop_settings(monkeypatch):
    """Family and pixel size come from GNOME settings."""
    values = {
        "document-font-name": "Cantarell 12",
        "monospace-font-name": "Courier 10",
    }
    monkeypatch.setattr(
        renderer.Gio, "Settings", lambda **_kw: _Settings(values),
    )
    ns = _font_adapter()
    Renderer._read_system_font(ns)
    assert ns.font_family == "Cantarell"
    assert ns.font_size_px == 16  # 12pt * 96/72
    assert ns.mono_family == "Courier"
    assert ns.mono_size_px == round(10 * 96 / 72)


def test_read_system_font_keeps_defaults_without_schema(monkeypatch):
    """Without the GNOME schema nothing is changed."""

    def missing(schema_id):
        raise RuntimeError(schema_id)

    monkeypatch.setattr(renderer.Gio, "Settings", missing)
    ns = _font_adapter()
    Renderer._read_system_font(ns)
    assert (ns.font_family, ns.font_size_px) == ("Sans", 16)
    assert (ns.mono_family, ns.mono_size_px) == ("Mono", 14)


def test_read_system_font_with_empty_names(monkeypatch):
    """Empty font names are ignored."""
    values = {"document-font-name": "", "monospace-font-name": ""}
    monkeypatch.setattr(
        renderer.Gio, "Settings", lambda **_kw: _Settings(values),
    )
    ns = _font_adapter()
    Renderer._read_system_font(ns)
    assert ns.font_family == "Sans"


def _hover_adapter(visible=True):
    return SimpleNamespace(
        label=Mock(**{"is_visible.return_value": visible}),
        link_uri="old",
    )


@pytest.mark.parametrize(
    ("kind", "prefix"),
    [("link", "link: "), ("image", "image:"), ("media", "media: ")],
)
def test_hover_label_prefix_by_kind(kind, prefix):
    """Each hover kind has its own label prefix."""
    ns = _hover_adapter()
    Renderer._on_hover_changed(ns, HoverTarget(kind, "http://x"))
    markup = ns.label.set_markup.call_args.args[0]
    assert prefix + "http://x" in markup
    assert ns.link_uri == "http://x"
    ns.label.show.assert_called_once()


def test_hover_leave_hides_visible_label():
    """Leaving a link hides the label and clears the URI."""
    ns = _hover_adapter(visible=True)
    Renderer._on_hover_changed(ns, None)
    ns.label.hide.assert_called_once()
    assert ns.link_uri is None


def test_hover_leave_with_hidden_label_does_nothing():
    """A label that is already hidden is left alone."""
    ns = _hover_adapter(visible=False)
    Renderer._on_hover_changed(ns, None)
    ns.label.hide.assert_not_called()
