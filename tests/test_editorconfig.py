"""Tests for formiko.editorconfig."""

import pytest

from formiko import editorconfig
from formiko.editorconfig import (
    INDENT_SIZE_TAB,
    EditorConfigSettings,
    resolve,
)


def _write(directory, text):
    (directory / ".editorconfig").write_text(text, encoding="utf-8")


def test_no_path_gives_empty_settings():
    """No path gives empty settings."""
    assert resolve(None) == EditorConfigSettings()
    assert resolve("") == EditorConfigSettings()


def test_no_editorconfig_gives_empty_settings(tmp_path):
    """No editorconfig gives empty settings."""
    # root = true stops the search from reaching the real parent directories
    _write(tmp_path, "root = true\n")
    assert resolve(str(tmp_path / "a.rst")) == EditorConfigSettings()


def test_all_properties(tmp_path):
    """All properties."""
    _write(
        tmp_path,
        "root = true\n"
        "[*.rst]\n"
        "indent_style = space\n"
        "indent_size = 3\n"
        "tab_width = 8\n"
        "end_of_line = CRLF\n"
        "charset = utf-8-bom\n"
        "trim_trailing_whitespace = true\n"
        "insert_final_newline = false\n"
        "max_line_length = 79\n",
    )
    assert resolve(str(tmp_path / "doc.rst")) == EditorConfigSettings(
        indent_style="space",
        indent_size=3,
        tab_width=8,
        end_of_line="crlf",
        charset="utf-8-bom",
        trim_trailing_whitespace=True,
        insert_final_newline=False,
        max_line_length=79,
    )


def test_sections_match_by_glob(tmp_path):
    """Sections match by glob."""
    _write(
        tmp_path,
        "root = true\n"
        "[*.{rst,md}]\nindent_size = 2\n"
        "[*.json]\nindent_size = 4\n",
    )
    assert resolve(str(tmp_path / "a.md")).indent_size == 2
    assert resolve(str(tmp_path / "a.json")).indent_size == 4
    assert resolve(str(tmp_path / "a.txt")).indent_size is None


def test_indent_size_tab_follows_tab_width(tmp_path):
    """Indent size tab follows tab width."""
    _write(tmp_path, "root = true\n[*]\nindent_style = tab\n")
    settings = resolve(str(tmp_path / "a.rst"))
    assert settings.indent_style == "tab"
    assert settings.indent_size == INDENT_SIZE_TAB
    assert settings.tab_width is None

    _write(tmp_path, "root = true\n[*]\nindent_size = tab\ntab_width = 4\n")
    settings = resolve(str(tmp_path / "a.rst"))
    assert settings.indent_size == 4
    assert settings.tab_width == 4


def test_tab_width_defaults_to_indent_size(tmp_path):
    """Tab width defaults to indent size."""
    _write(tmp_path, "root = true\n[*]\nindent_size = 2\n")
    assert resolve(str(tmp_path / "a.rst")).tab_width == 2


def test_closer_file_wins_and_unset_removes(tmp_path):
    """Closer file wins and unset removes."""
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(tmp_path, "root = true\n[*]\nindent_size = 4\ncharset = utf-8\n")
    _write(sub, "[*]\nindent_size = 2\ncharset = unset\n")
    settings = resolve(str(sub / "a.rst"))
    assert settings.indent_size == 2
    assert settings.charset is None
    assert resolve(str(tmp_path / "a.rst")).charset == "utf-8"


def test_root_stops_the_search(tmp_path):
    """Root stops the search."""
    sub = tmp_path / "sub"
    sub.mkdir()
    _write(tmp_path, "root = true\n[*]\nindent_size = 4\n")
    _write(sub, "root = true\n[*]\ncharset = latin1\n")
    settings = resolve(str(sub / "a.rst"))
    assert settings.indent_size is None
    assert settings.charset == "latin1"


@pytest.mark.parametrize(
    "line",
    [
        "indent_style = mixed",
        "indent_size = big",
        "indent_size = 0",
        "indent_size = -2",
        "tab_width = x",
        "end_of_line = nl",
        "charset = koi8",
        "trim_trailing_whitespace = maybe",
        "insert_final_newline = 1",
        "max_line_length = off",
    ],
)
def test_invalid_values_are_ignored(tmp_path, line):
    """Invalid values are ignored."""
    _write(tmp_path, f"root = true\n[*]\n{line}\n")
    settings = resolve(str(tmp_path / "a.rst"))
    name = line.split("=")[0].strip()
    # indent_size = tab / tab_width are derived from each other by the library
    assert getattr(settings, name) is None


def test_unparsable_editorconfig_gives_empty_settings(tmp_path):
    """Unparsable editorconfig gives empty settings."""
    _write(tmp_path, "root = true\n[*\nindent_size = 4\n[unterminated\n")
    # whatever the library does with it, resolve must not raise
    assert isinstance(
        resolve(str(tmp_path / "a.rst")),
        EditorConfigSettings,
    )


def test_library_errors_are_swallowed(tmp_path, monkeypatch, caplog):
    """Library errors are swallowed."""

    def broken(_path):
        msg = "boom"
        raise editorconfig.EditorConfigError(msg)

    monkeypatch.setattr(editorconfig, "get_properties", broken)
    assert resolve(str(tmp_path / "a.rst")) == EditorConfigSettings()
    assert "boom" in caplog.text
