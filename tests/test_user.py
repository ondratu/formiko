"""Tests for user settings and cache persistence."""

import contextlib

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from formiko import user  # noqa: E402
from formiko.user import (  # noqa: E402
    EditorPreferences,
    SmartParser,
    UserCache,
    UserPreferences,
    View,
    smart_bool,
)


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """Point config and cache directories into *tmp_path*."""
    config = tmp_path / "config"
    cache = tmp_path / "cache"
    config.mkdir()
    cache.mkdir()
    monkeypatch.setattr(user, "get_user_config_dir", lambda: str(config))
    monkeypatch.setattr(user, "get_user_cache_dir", lambda: str(cache))
    return config, cache


@pytest.fixture(autouse=True)
def _restore_editor_preferences():
    """``UserPreferences.editor`` is shared at class level; restore it."""
    editor = UserPreferences.editor
    saved = dict(vars(editor))
    yield
    vars(editor).clear()
    vars(editor).update(saved)


@pytest.mark.parametrize(
    "value",
    ["1", "true", "TRUE", "Yes", "on", "Enable"],
)
def test_smart_bool_true_values(value):
    """Human forms of truth are accepted in any letter case."""
    assert smart_bool(value) is True


@pytest.mark.parametrize(
    "value",
    ["0", "false", "FALSE", "No", "off", "Disable"],
)
def test_smart_bool_false_values(value):
    """Human forms of falsehood are accepted in any letter case."""
    assert smart_bool(value) is False


def test_smart_bool_rejects_unknown_value():
    """Anything else raises ValueError mentioning the value."""
    with pytest.raises(ValueError, match="maybe is not boolean"):
        smart_bool("maybe")


@pytest.mark.parametrize("value", [1, 2, 3, "2"])
def test_view_accepts_valid_values(value):
    """View accepts numbers 1-3 as int or string."""
    assert View(value) == int(value)


@pytest.mark.parametrize("value", [0, 4, -1])
def test_view_rejects_out_of_range(value):
    """Numbers outside 1-3 are refused."""
    with pytest.raises(AssertionError):
        View(value)


def test_view_rejects_non_number():
    """A non-numeric string is refused."""
    with pytest.raises(ValueError, match="invalid literal"):
        View("abc")


class _Target:
    value = "default"


def _parser(text=""):
    cp = SmartParser()
    cp.read_string(text)
    return cp


def test_smart_get_sets_converted_value():
    """The value is converted and stored on the object."""
    target = _Target()
    _parser("[main]\nvalue = 42\n").smart_get(target, "value", int)
    assert target.value == 42


def test_smart_get_ignores_missing_section_and_option():
    """Missing section or option keeps the default."""
    target = _Target()
    cp = _parser("[main]\nother = 1\n")
    cp.smart_get(target, "value")
    cp.smart_get(target, "value", sec="nosection")
    assert target.value == "default"


def test_smart_get_survives_bad_conversion(capsys):
    """A failing conversion is reported but keeps the default."""
    target = _Target()
    _parser("[main]\nvalue = x\n").smart_get(target, "value", int)
    assert target.value == "default"
    assert "ValueError" in capsys.readouterr().err


def test_smart_set_stores_string():
    """smart_set writes str() of the attribute."""
    cp = _parser("[main]\n")
    target = _Target()
    target.value = 7
    cp.smart_set(target, "value")
    assert cp.get("main", "value") == "7"


def test_preferences_defaults_without_file():
    """Without a config file the defaults stay."""
    prefs = UserPreferences()
    assert prefs.parser == "rst"
    assert prefs.color_scheme == "default"


def test_preferences_round_trip(isolated_dirs):
    """Saved preferences are read back by a new instance."""
    config, _ = isolated_dirs
    prefs = UserPreferences()
    prefs.auto_scroll = False
    prefs.color_scheme = "dark"
    prefs.style = "/some/style.css"
    prefs.custom_style = True
    prefs.wakatime_enabled = True
    prefs.wakatime_api_key = "key"
    prefs.editor.tab_width = 3
    prefs.editor.line_numbers = False
    prefs.editor.spell_lang = "cs"
    prefs.save()
    assert (config / "formiko.ini").exists()

    prefs.auto_scroll = True
    prefs.color_scheme = "default"
    prefs.editor.tab_width = 8
    loaded = UserPreferences()
    assert loaded.auto_scroll is False
    assert loaded.color_scheme == "dark"
    assert loaded.style == "/some/style.css"
    assert loaded.custom_style is True
    assert loaded.wakatime_enabled is True
    assert loaded.wakatime_api_key == "key"
    assert loaded.editor.tab_width == 3
    assert loaded.editor.line_numbers is False
    assert loaded.editor.spell_lang == "cs"


def test_save_creates_missing_config_directory(isolated_dirs, monkeypatch):
    """The config directory is created on save."""
    config, _ = isolated_dirs
    target = config / "nested" / "dir"
    monkeypatch.setattr(user, "get_user_config_dir", lambda: str(target))
    UserPreferences().save()
    assert (target / "formiko.ini").exists()


def test_invalid_color_scheme_falls_back(isolated_dirs):
    """Unknown colour scheme is replaced by the default."""
    config, _ = isolated_dirs
    (config / "formiko.ini").write_text("[main]\ncolor_scheme = purple\n")
    assert UserPreferences().color_scheme == "default"


def test_unknown_parser_and_writer_fall_back(isolated_dirs):
    """Unknown parser and writer are replaced by defaults."""
    config, _ = isolated_dirs
    (config / "formiko.ini").write_text(
        "[main]\nparser = nonsense\nwriter = nonsense\n",
    )
    prefs = UserPreferences()
    assert prefs.parser == "rst"
    assert prefs.writer == "html4"


def test_editor_preferences_defaults():
    """EditorPreferences exposes its documented defaults."""
    editor = EditorPreferences()
    assert editor.tab_width == 8
    assert editor.right_margin_value == 80


def test_cache_defaults_without_file():
    """Without a cache file the class defaults are used."""
    cache = UserCache()
    assert (cache.width, cache.height) == (800, 600)
    assert cache.view == View.BOTH


def test_cache_round_trip(isolated_dirs):
    """Saved window geometry is read back."""
    _, cache_dir = isolated_dirs
    cache = UserCache()
    cache.width, cache.height, cache.paned = 1000, 700, 250
    cache.is_maximized = True
    cache.view = View.EDITOR
    cache.save()
    assert (cache_dir / "formiko" / "window.ini").exists()

    loaded = UserCache()
    assert (loaded.width, loaded.height, loaded.paned) == (1000, 700, 250)
    assert loaded.is_maximized is True
    assert loaded.view == View.EDITOR


def test_cache_ignores_invalid_view(isolated_dirs):
    """An out-of-range view in the cache file keeps the default."""
    _, cache_dir = isolated_dirs
    (cache_dir / "formiko").mkdir()
    (cache_dir / "formiko" / "window.ini").write_text(
        "[main]\nview = 9\nwidth = 900\n",
    )
    loaded = UserCache()
    assert loaded.width == 900
    assert loaded.view == View.BOTH
