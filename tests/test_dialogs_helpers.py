"""Tests for display-less helpers in :mod:`formiko.dialogs`."""

import contextlib
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from formiko import dialogs  # noqa: E402
from formiko.dialogs import (  # noqa: E402
    _apply_initial_name,
    _connect_filter_extension_updater,
    build_css_filters,
    build_export_filters,
    build_open_filters,
    build_save_filters,
    load_authors,
    make_filter_all,
    make_filter_markup_text,
)


def _names(store):
    return [store.get_item(i).get_name() for i in range(store.get_n_items())]


def test_load_authors_returns_sections():
    """The bundled AUTHORS file is parsed into named sections."""
    sections = load_authors()
    assert "developers" in sections
    assert "artists" in sections
    assert all(isinstance(v, list) for v in sections.values())
    assert any("@" in entry for entry in sections["developers"])


def test_load_authors_survives_missing_file(monkeypatch, capsys):
    """A read failure yields an empty dict instead of an exception."""

    def broken(_package):
        msg = "nope"
        raise FileNotFoundError(msg)

    monkeypatch.setattr(dialogs, "files", broken)
    assert load_authors() == {}
    assert "FileNotFoundError" in capsys.readouterr().err


def test_load_authors_ignores_lines_before_first_section(monkeypatch):
    """Entries outside a section are dropped; blank lines are skipped."""

    class _Res:
        def joinpath(self, _name):
            return self

        def read_text(self, encoding):
            return "orphan\n[a]\n\nOne\nTwo\n[b]\nThree\n"

    monkeypatch.setattr(dialogs, "files", lambda _package: _Res())
    assert load_authors() == {"a": ["One", "Two"], "b": ["Three"]}


def test_make_filter_all_and_markup_text_names():
    """The generic filters have stable names."""
    assert make_filter_all().get_name() == "All File Types"
    assert make_filter_markup_text().get_name() == "Markup & Text files"


def test_css_filters_default_is_first():
    """The CSS picker offers CSS first and everything second."""
    store, default = build_css_filters()
    assert _names(store) == ["Stylesheet file (*.css)", "All File Types"]
    assert store.get_item(0) is default


def test_open_filters_default_is_markup_and_all_is_last():
    """The open dialog defaults to markup and ends with all files."""
    store, default = build_open_filters()
    names = _names(store)
    assert names[0] == "Markup & Text files"
    assert names[-1] == "All File Types"
    assert "Plain text" in names
    assert default is store.get_item(0)


@pytest.mark.parametrize(
    ("lang_id", "suffix"),
    [
        ("rst", "rst"),
        ("markdown", "md"),
        ("html", "html"),
        ("json", "json"),
        ("text", "txt"),
        ("unknown", "rst"),
    ],
)
def test_save_filters_default_by_language(lang_id, suffix):
    """The default filter and suffix follow the language id."""
    store, default, got_suffix, mapping = build_save_filters(lang_id)
    assert got_suffix == suffix
    assert mapping[default.get_name()] == suffix
    assert _names(store)[-1] == "All File Types"
    assert set(mapping.values()) == {"rst", "md", "html", "json", "txt"}


def test_export_filters_for_json_and_others():
    """JSON exports as json, everything else as html."""
    store, default, suffix, mapping = build_export_filters("json")
    assert suffix == "json"
    assert mapping == {default.get_name(): "json"}
    assert _names(store)[-1] == "All File Types"

    _, _, suffix, mapping = build_export_filters("rst")
    assert suffix == "html"
    assert list(mapping.values()) == ["html"]


@pytest.mark.parametrize(
    ("name", "suffix", "expected"),
    [
        ("doc", "rst", "doc.rst"),
        ("doc.txt", "rst", "doc.txt"),
        ("doc", None, "doc"),
    ],
)
def test_apply_initial_name_sets_name(name, suffix, expected):
    """A suffix is appended only when the name has none."""
    dialog = Mock()
    _apply_initial_name(dialog, name, suffix)
    dialog.set_current_name.assert_called_once_with(expected)


def test_apply_initial_name_ignores_empty_name():
    """An empty name does not touch the dialog."""
    dialog = Mock()
    _apply_initial_name(dialog, "", "rst")
    dialog.set_current_name.assert_not_called()


def _updater(current, filter_name, suffixes):
    """Connect the updater to a fake dialog and fire notify::filter."""
    dialog = Mock()
    dialog.get_current_name.return_value = current
    dialog.get_filter.return_value = (
        None
        if filter_name is None
        else Mock(**{"get_name.return_value": filter_name})
    )
    _connect_filter_extension_updater(dialog, suffixes)
    signal, handler = dialog.connect.call_args.args
    assert signal == "notify::filter"
    handler(dialog, None)
    return dialog


def test_filter_change_replaces_extension():
    """Switching filter swaps the extension of the current name."""
    dialog = _updater("note.rst", "Markdown", {"Markdown": "md"})
    dialog.set_current_name.assert_called_once_with("note.md")


def test_filter_change_adds_extension_to_bare_name():
    """A name without extension gets the new one."""
    dialog = _updater("note", "Markdown", {"Markdown": "md"})
    dialog.set_current_name.assert_called_once_with("note.md")


def test_filter_without_suffix_strips_extension():
    """A filter without suffix (all files) removes the extension."""
    dialog = _updater("note.rst", "All", {})
    dialog.set_current_name.assert_called_once_with("note")


@pytest.mark.parametrize(
    ("current", "filter_name"),
    [("x.rst", None), ("", "A")],
)
def test_filter_change_noop_cases(current, filter_name):
    """No filter or empty name leaves the name alone."""
    dialog = _updater(current, filter_name, {"A": "md"})
    dialog.set_current_name.assert_not_called()
