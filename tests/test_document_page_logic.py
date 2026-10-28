"""Display-less tests for :class:`formiko.document_page.DocumentPage`."""

import contextlib
import os
from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from formiko import document_page  # noqa: E402
from formiko.document_page import DocumentPage  # noqa: E402
from formiko.editor import EditorType  # noqa: E402


def _page(editor_type=EditorType.SOURCE, **kwargs):
    ns = SimpleNamespace(
        editor_type=editor_type,
        editor=Mock(),
        renderer=Mock(),
        preferences=SimpleNamespace(parser="rst", auto_scroll=True),
        _window=Mock(),
        _preview_file="",
        _last_changes=0,
        _words_count=0,
        _chars_count=0,
        running=True,
        emit=Mock(),
        _check_in_thread=Mock(),
        parser="rst",
        file_path="/a.rst",
    )
    for key, value in kwargs.items():
        setattr(ns, key, value)
    return ns


@pytest.fixture
def timers(monkeypatch):
    """Record GLib scheduling calls."""
    calls = SimpleNamespace(idle=[], timeout=[])
    monkeypatch.setattr(
        document_page.GLib, "idle_add",
        lambda func, *a: calls.idle.append((func, a)),
    )
    monkeypatch.setattr(
        document_page.GLib, "timeout_add",
        lambda ms, func, *_a: calls.timeout.append((ms, func)),
    )
    return calls


# --- properties ---------------------------------------------------------

def test_editor_backed_properties():
    """Source/Vim pages delegate path, name and modified to the editor."""
    page = _page()
    page.editor.file_path = "/d/a.rst"
    page.editor.file_name = "a.rst"
    page.editor.is_modified = True
    assert DocumentPage.file_path.fget(page) == "/d/a.rst"
    assert DocumentPage.file_name.fget(page) == "a.rst"
    assert DocumentPage.is_modified.fget(page) is True


def test_preview_page_properties():
    """Preview pages use the previewed file and are never modified."""
    page = _page(EditorType.PREVIEW, _preview_file="/d/b.md")
    assert DocumentPage.file_path.fget(page) == "/d/b.md"
    assert DocumentPage.file_name.fget(page) == "b.md"
    assert DocumentPage.is_modified.fget(page) is False


def test_preview_page_without_file_has_empty_name():
    """No previewed file gives an empty name."""
    page = _page(EditorType.PREVIEW)
    assert DocumentPage.file_name.fget(page) == ""


def test_counts_and_parser_properties():
    """Counters and parser are exposed read-only."""
    page = _page(_words_count=3, _chars_count=14)
    assert DocumentPage.words_count.fget(page) == 3
    assert DocumentPage.chars_count.fget(page) == 14
    assert DocumentPage.parser.fget(page) == "rst"


# --- scroll and file type -------------------------------------------------

@pytest.mark.parametrize("auto_scroll", [True, False])
def test_scroll_changed_follows_auto_scroll(auto_scroll):
    """The preview follows the editor only with auto-scroll on."""
    page = _page()
    page._window.preferences.auto_scroll = auto_scroll
    DocumentPage._on_scroll_changed(page, None, 0.5)
    if auto_scroll:
        page.renderer.scroll_to_position.assert_called_once_with(0.5)
    else:
        page.renderer.scroll_to_position.assert_not_called()
    page._window.wakatime.heartbeat.assert_called_once()


def test_scroll_changed_in_preview_skips_wakatime():
    """Preview-only pages do not send editor heartbeats."""
    page = _page(EditorType.PREVIEW)
    page._window.preferences.auto_scroll = True
    DocumentPage._on_scroll_changed(page, None, 0.1)
    page._window.wakatime.heartbeat.assert_not_called()


def test_file_type_enables_list_features_for_markup(monkeypatch):
    """List helpers are on for rst/markdown, off for other parsers."""
    monkeypatch.setattr(
        document_page, "resolve_ext_parser", lambda _e, _p: "json",
    )
    page = _page(fmt_actions=Mock())
    page.file_path = ""
    DocumentPage._on_file_type(page, None, ".json")
    page.editor.set_list_features_enabled.assert_called_once_with(False)
    page.editor.change_mime_type.assert_called_once_with("json")
    page.fmt_actions.set_parser.assert_called_once_with("json")
    page._window.on_active_tab_parser_changed.assert_called_once_with(
        page, "json",
    )
    page.emit.assert_called_once_with("doc-state-changed")
    page._window.wakatime.heartbeat.assert_called_once_with("", "json")


def test_file_type_updates_file_browser_directory(monkeypatch):
    """The sidebar follows the opened file's directory."""
    monkeypatch.setattr(
        document_page, "resolve_ext_parser", lambda _e, _p: "rst",
    )
    page = _page(fmt_actions=Mock())
    page.file_path = "/some/dir/a.rst"
    page._window = Mock(spec=["file_browser", "on_active_tab_parser_changed",
                              "wakatime"])
    DocumentPage._on_file_type(page, None, ".rst")
    page._window.file_browser.set_directory.assert_called_once_with(
        "/some/dir",
    )


# --- refresh loop ---------------------------------------------------------

def test_check_in_thread_stops_when_not_running(timers):
    """A stopped page schedules nothing."""
    page = _page(running=False)
    assert DocumentPage._check_in_thread(page) is False
    assert timers.idle == []


def test_check_in_thread_dispatches_by_editor_type(timers):
    """Each editor type uses its own refresh function."""
    page = _page(EditorType.SOURCE, _refresh_from_source=Mock(),
                 _refresh_from_file=Mock())
    DocumentPage._check_in_thread(page, True)
    assert timers.idle == [(page._refresh_from_source, (True,))]

    timers.idle.clear()
    page.editor_type = EditorType.PREVIEW
    DocumentPage._check_in_thread(page)
    assert timers.idle == [(page._refresh_from_file, (False,))]


def test_check_in_thread_starts_thread_for_vim(monkeypatch):
    """The vim refresh runs in a daemon thread."""
    started = []

    class _Thread:
        def __init__(self, target, args, daemon):
            started.append((target, args, daemon))

        def start(self):
            started.append("start")

    monkeypatch.setattr(document_page.threading, "Thread", _Thread)
    page = _page(EditorType.VIM, _refresh_from_vim=Mock())
    DocumentPage._check_in_thread(page, True)
    assert started == [(page._refresh_from_vim, (True,), True), "start"]


def test_refresh_from_source_renders_new_changes(timers):
    """New changes render the text and update the counters."""
    page = _page()
    page.editor.changes = 1
    page.editor.text = "two words\nok"
    page.editor.file_path = "/a.rst"
    page.editor.position = 0.3
    DocumentPage._refresh_from_source(page)

    page.renderer.render.assert_called_once_with(
        "two words\nok", "/a.rst", 0.3,
    )
    assert page._words_count == 3
    # Letters, spaces and basic punctuation count; newlines do not.
    assert page._chars_count == 11
    page.emit.assert_called_once_with("words-count-changed", 3, 11)
    page._window.wakatime.heartbeat.assert_called_once()
    assert timers.timeout[0][0] == 100


def test_refresh_from_source_skips_unchanged_unless_forced(timers):
    """Without changes nothing renders, but force overrides that."""
    page = _page()
    page.editor.changes = 0
    page.editor.text = "x"
    DocumentPage._refresh_from_source(page)
    page.renderer.render.assert_not_called()
    assert timers.timeout

    DocumentPage._refresh_from_source(page, force=True)
    page.renderer.render.assert_called_once()


@pytest.mark.usefixtures("timers")
def test_refresh_from_source_reports_errors(capsys):
    """Exceptions are printed and do not propagate."""
    page = _page()
    type(page.editor).changes = property(
        lambda _s: (_ for _ in ()).throw(RuntimeError("bad")),
    )
    DocumentPage._refresh_from_source(page)
    assert "RuntimeError" in capsys.readouterr().err


def test_refresh_from_file_renders_changed_file(tmp_path, timers):
    """A changed preview file is read and rendered."""
    path = tmp_path / "a.rst"
    path.write_text("hello", encoding="utf-8")
    page = _page(EditorType.PREVIEW, _preview_file=str(path))
    page.renderer.position = 0.2
    DocumentPage._refresh_from_file(page)

    page.renderer.render.assert_called_once_with("hello", str(path), 0.2)
    assert page._last_changes == os.stat(path).st_ctime
    assert timers.timeout[0][0] == 500

    page.renderer.render.reset_mock()
    DocumentPage._refresh_from_file(page)
    page.renderer.render.assert_not_called()


def test_refresh_from_file_survives_missing_file(tmp_path, timers, capsys):
    """A deleted file is reported and the loop keeps running."""
    page = _page(EditorType.PREVIEW, _preview_file=str(tmp_path / "gone"))
    DocumentPage._refresh_from_file(page)
    assert "FileNotFoundError" in capsys.readouterr().err
    assert timers.timeout[0][0] == 500


def test_refresh_from_vim_renders_changes(timers):
    """Vim content is pulled and rendered with the scroll position."""
    page = _page(EditorType.VIM, _vim_title="old")
    editor = page.editor
    editor.file_name = "new.rst"
    editor.file_path = "/new.rst"
    editor.get_vim_changes.return_value = 4
    editor.get_vim_lines.return_value = 10
    editor.get_vim_get_buffer.return_value = "text"
    editor.get_vim_scroll_pos.return_value = 0.5
    DocumentPage._refresh_from_vim(page)

    assert page._vim_title == "new.rst"
    assert page._last_changes == 4
    page.renderer.render.assert_called_once_with("text", "/new.rst", 0.5)
    assert any(f == page.emit for f, _ in timers.idle)
    assert timers.timeout[0][0] == 100


def test_refresh_from_vim_returns_when_stopped(timers):
    """A stopped page does no work."""
    page = _page(EditorType.VIM, _vim_title="x", running=False)
    DocumentPage._refresh_from_vim(page)
    page.renderer.render.assert_not_called()
    assert timers.timeout == []


def test_stop_ends_refresh_loop():
    """stop() flips the running flag."""
    page = _page()
    DocumentPage.stop(page)
    assert page.running is False
