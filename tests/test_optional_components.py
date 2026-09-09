"""Tests for optional parser, writer, and syntax-highlighting dependencies."""

from docutils.core import publish_parts
from docutils.parsers.rst import Parser

from formiko import renderer
from formiko.renderer import PARSERS, WRITERS, component_available
from formiko.user import UserPreferences
from formiko.utils import Undefined


def test_missing_parser_is_reported_as_unavailable():
    """A parser represented by ``Undefined`` is unavailable."""
    parser = dict(PARSERS["mistune"])
    parser["class"] = type("Missing", (Undefined,), {})

    assert not component_available(parser)


def test_missing_writer_is_reported_as_unavailable():
    """A writer represented by ``Undefined`` is unavailable."""
    writer = dict(WRITERS["tiny"])
    writer["class"] = type("Missing", (Undefined,), {})

    assert not component_available(writer)


def test_preferences_fall_back_when_components_are_missing(
    monkeypatch, tmp_path,
):
    """Missing configured components are replaced by available defaults."""
    (tmp_path / "formiko.ini").write_text(
        "[main]\nparser = mistune\nwriter = tiny\n",
    )
    missing = type("Missing", (Undefined,), {})
    monkeypatch.setattr("formiko.user.get_user_config_dir", lambda: tmp_path)
    monkeypatch.setitem(PARSERS["mistune"], "class", missing)
    monkeypatch.setitem(WRITERS["tiny"], "class", missing)

    preferences = UserPreferences()

    assert preferences.parser == "rst"
    assert preferences.writer == "html4"


def test_renderer_disables_highlighting_without_pygments(monkeypatch):
    """Renderer settings avoid Docutils' missing-Pygments warning."""
    monkeypatch.setattr(renderer, "_PYGMENTS_AVAILABLE", False)
    source = ".. code-block:: python\n\n   print('hello')\n"
    settings = renderer._docutils_settings(8, None, "")
    warning_stream = settings["warning_stream"]

    parts = publish_parts(
        source,
        parser=Parser(),
        writer_name="html5",
        settings_overrides=settings,
    )

    assert warning_stream.getvalue() == ""
    assert "system-message" not in parts["body"]
    assert '<pre class="code python literal-block">' in parts["body"]
    assert "print" in parts["body"]
    assert "highlight" not in parts["body"]
