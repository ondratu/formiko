"""Display-less tests for :class:`formiko.sourceview.SourceView` methods.

Methods are borrowed from ``SourceView`` and run against an adapter that
owns a real ``GtkSource.Buffer`` but no widget tree.
"""

import contextlib
from io import StringIO
from unittest.mock import Mock

import gi
import pytest

gi.require_version("GtkSource", "5")
gi.require_version("Adw", "1")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from gi.repository import GtkSource  # noqa: E402

from formiko import sourceview  # noqa: E402
from formiko.sourceview import LANG_BY_EXT, SourceView  # noqa: E402

GtkSource.init()


class _Adapter:
    """Minimal SourceView stand-in with a real buffer and search context."""

    _SV = SourceView
    do_next_match = _SV.do_next_match
    do_previous_match = _SV.do_previous_match
    get_selected_text = _SV.get_selected_text
    get_selection_offsets = _SV.get_selection_offsets
    do_file_type = _SV.do_file_type
    read_from_file = _SV.read_from_file
    save_to_file = _SV.save_to_file
    save = _SV.save
    save_as = _SV.save_as
    _after_save_dialog = _SV._after_save_dialog
    file_ext = _SV.file_ext
    file_name = _SV.file_name
    file_path = _SV.file_path
    text = _SV.text
    is_modified = _SV.is_modified
    period_save_thread = _SV.period_save_thread
    _on_file_changed_response = _SV._on_file_changed_response

    def __init__(self, text=""):
        self.text_buffer = GtkSource.Buffer()
        self.text_buffer.set_text(text)
        self.search_settings = GtkSource.SearchSettings(wrap_around=True)
        self.search_context = GtkSource.SearchContext.new(
            self.text_buffer, self.search_settings,
        )
        self.search_mark = None
        self.source_view = Mock()
        self._SourceView__file_name = ""
        self._SourceView__last_changes = 0
        self._SourceView__last_ctime = 0
        self._SourceView__pause_period = False
        self._SourceView__win = None
        self.emit = Mock()
        self.scroll_to_cursor = Mock()
        self.period_save = 0
        self.check_in_thread = Mock()
        self.read_calls = []

    def cursor_offset(self):
        mark = self.text_buffer.get_insert()
        return self.text_buffer.get_iter_at_mark(mark).get_offset()

    def select(self, start, end):
        self.text_buffer.select_range(
            self.text_buffer.get_iter_at_offset(start),
            self.text_buffer.get_iter_at_offset(end),
        )


# --- search -----------------------------------------------------------

def test_next_match_walks_through_matches_and_wraps():
    """Repeated searches move over each hit and wrap around."""
    sv = _Adapter("foo bar foo baz foo")
    positions = []
    for _ in range(4):
        assert sv.do_next_match("foo")
        positions.append(sv.cursor_offset())
    assert positions == [0, 8, 16, 0]


def test_next_match_without_hit_returns_false():
    """A missing word is reported and resets the search mark."""
    sv = _Adapter("alpha beta")
    assert sv.do_next_match("zzz") is False
    assert sv.search_mark is None
    assert sv.do_next_match("zzz") is False


def test_previous_match_finds_previous_hit():
    """Searching backwards from the end finds the last hit first."""
    sv = _Adapter("foo bar foo")
    sv.text_buffer.place_cursor(sv.text_buffer.get_end_iter())
    assert sv.do_previous_match("foo")
    assert sv.cursor_offset() == 8
    assert sv.do_previous_match("foo")
    assert sv.cursor_offset() == 0


def test_previous_match_without_hit_returns_false():
    """A missing word is reported and resets the search mark."""
    sv = _Adapter("alpha")
    assert sv.do_previous_match("zzz") is False
    assert sv.search_mark is None
    assert sv.do_previous_match("zzz") is False


# --- selection --------------------------------------------------------

def test_selected_text_empty_without_selection():
    """No selection yields an empty string."""
    assert _Adapter("hello").get_selected_text() == ""


def test_selected_text_and_offsets():
    """Selection text and offsets agree."""
    sv = _Adapter("hello world")
    sv.select(6, 11)
    assert sv.get_selected_text() == "world"
    assert sv.get_selection_offsets() == (6, 11)


def test_selection_offsets_without_selection_use_cursor():
    """Without selection both offsets are the cursor offset."""
    sv = _Adapter("hello")
    sv.text_buffer.place_cursor(sv.text_buffer.get_iter_at_offset(3))
    assert sv.get_selection_offsets() == (3, 3)


# --- file type --------------------------------------------------------

def test_do_file_type_sets_language():
    """A known extension changes the highlighting language."""
    sv = _Adapter()
    sv.do_file_type(".json")
    assert sv.text_buffer.get_language() == LANG_BY_EXT[".json"]


def test_do_file_type_unknown_extension_falls_back_to_rst():
    """Unknown extensions use reStructuredText highlighting."""
    sv = _Adapter()
    sv.do_file_type(".unknown")
    assert sv.text_buffer.get_language() == LANG_BY_EXT[".rst"]


def test_do_file_type_empty_extension_is_ignored():
    """An empty extension keeps the current language."""
    sv = _Adapter()
    sv.do_file_type("")
    assert sv.text_buffer.get_language() is None


# --- file properties --------------------------------------------------

def test_file_properties():
    """Name, path and extension derive from the stored file name."""
    sv = _Adapter()
    sv._SourceView__file_name = "/dir/note.md"
    assert sv.file_name == "note.md"
    assert sv.file_path == "/dir/note.md"
    assert sv.file_ext == ".md"


# --- reading and saving ------------------------------------------------

@pytest.fixture
def idle(monkeypatch):
    """Record idle_add calls instead of scheduling them."""
    calls = []
    monkeypatch.setattr(
        sourceview, "idle_add", lambda func, *args: calls.append((func, args)),
    )
    return calls


def test_read_from_file_loads_text_and_resets_modified(tmp_path, idle):
    """The file content is loaded and the buffer is clean."""
    path = tmp_path / "a.rst"
    path.write_text("Žluťoučký kůň\n", encoding="utf-8")
    sv = _Adapter("old")
    sv.read_from_file(str(path))

    assert sv.text == "Žluťoučký kůň\n"
    assert not sv.is_modified
    assert sv._SourceView__last_changes == 1
    assert sv._SourceView__last_ctime == path.stat().st_ctime
    sv.emit.assert_called_once_with("file_type", ".rst")
    assert idle


@pytest.mark.usefixtures("idle")
def test_read_from_file_places_cursor_at_offset(tmp_path):
    """The cursor is restored to the requested offset."""
    path = tmp_path / "a.rst"
    path.write_text("0123456789", encoding="utf-8")
    sv = _Adapter()
    sv.read_from_file(str(path), 4)
    assert sv.cursor_offset() == 4


def test_read_from_file_negative_offset_keeps_cursor_idle_free(tmp_path, idle):
    """A negative offset skips cursor restoration."""
    path = tmp_path / "a.rst"
    path.write_text("abc", encoding="utf-8")
    sv = _Adapter()
    sv.read_from_file(str(path), -1)
    assert idle == []


@pytest.mark.usefixtures("idle")
def test_read_from_missing_file_keeps_buffer(tmp_path):
    """A new (not yet existing) file leaves the buffer empty and clean."""
    sv = _Adapter()
    sv.read_from_file(str(tmp_path / "new.rst"))
    assert sv.text == ""
    assert not sv.is_modified


def test_save_to_file_writes_text_and_backup(tmp_path):
    """Saving writes the text and keeps the previous file as ``~``."""
    path = tmp_path / "a.rst"
    path.write_text("old", encoding="utf-8")
    sv = _Adapter("new text ě")
    sv._SourceView__file_name = str(path)
    sv.text_buffer.set_modified(True)
    sv.save_to_file()

    assert path.read_text(encoding="utf-8") == "new text ě"
    assert (tmp_path / "a.rst~").read_text(encoding="utf-8") == "old"
    assert not sv.is_modified
    sv.emit.assert_called_once_with("file-saved")


def test_save_to_file_creates_new_file_without_backup(tmp_path):
    """No backup is created when the file did not exist."""
    path = tmp_path / "fresh.rst"
    sv = _Adapter("x")
    sv._SourceView__file_name = str(path)
    sv.save_to_file()
    assert path.read_text(encoding="utf-8") == "x"
    assert not (tmp_path / "fresh.rst~").exists()


def test_save_to_file_failure_shows_traceback_dialog(
    tmp_path, monkeypatch,
):
    """A write error is reported in a dialog and on stderr."""
    shown = []
    err = StringIO()
    monkeypatch.setattr(sourceview, "stderr", err)
    monkeypatch.setattr(
        sourceview, "TraceBackDialog", lambda error: ("dialog", error),
    )
    monkeypatch.setattr(
        sourceview,
        "run_alert_dialog",
        lambda dlg, win: shown.append((dlg, win)),
    )
    sv = _Adapter("x")
    sv._SourceView__file_name = str(tmp_path / "missing" / "a.rst")
    sv._SourceView__win = "window"
    sv.save_to_file()

    assert shown
    assert shown[0][1] == "window"
    assert "FileNotFoundError" in err.getvalue()
    sv.emit.assert_not_called()


def test_save_without_name_opens_save_dialog():
    """An unnamed document asks where to save."""
    sv = _Adapter()
    sv._open_save_dialog = Mock()
    sv.save()
    sv._open_save_dialog.assert_called_once_with(sv._after_save_dialog)


def test_save_with_name_saves_directly():
    """A named document is saved without a dialog."""
    sv = _Adapter()
    sv._SourceView__file_name = "x.rst"
    sv.save_to_file = Mock()
    sv._open_save_dialog = Mock()
    sv.save()
    sv.save_to_file.assert_called_once_with()
    sv._open_save_dialog.assert_not_called()


def test_save_as_always_opens_dialog():
    """Save As always asks for a name."""
    sv = _Adapter()
    sv._SourceView__file_name = "x.rst"
    sv._open_save_dialog = Mock()
    sv.save_as()
    sv._open_save_dialog.assert_called_once_with(sv._after_save_dialog)


# --- periodic save and external change ----------------------------------

def test_period_save_thread_schedules_save_when_modified(monkeypatch):
    """A modified named document is saved and the timer re-armed."""
    idle_calls, timers = [], []
    monkeypatch.setattr(
        sourceview, "idle_add", lambda func, *_a: idle_calls.append(func),
    )
    monkeypatch.setattr(
        sourceview, "timeout_add_seconds",
        lambda secs, func: timers.append((secs, func)),
    )
    sv = _Adapter("x")
    sv.period_save = 5
    sv._SourceView__file_name = "a.rst"
    sv.text_buffer.set_modified(True)
    sv.period_save_thread()
    assert idle_calls == [sv.save_to_file]
    assert timers == [(5, sv.period_save_thread)]


@pytest.mark.parametrize(
    ("name", "modified", "paused"),
    [("", True, False), ("a.rst", False, False), ("a.rst", True, True)],
)
def test_period_save_thread_skips_when_nothing_to_save(
    monkeypatch, name, modified, paused,
):
    """No save without a file name, changes, or while paused."""
    idle_calls = []
    monkeypatch.setattr(
        sourceview, "idle_add", lambda func, *_a: idle_calls.append(func),
    )
    monkeypatch.setattr(sourceview, "timeout_add_seconds", lambda *_a: None)
    sv = _Adapter("x")
    sv.period_save = 5
    sv._SourceView__file_name = name
    sv._SourceView__pause_period = paused
    sv.text_buffer.set_modified(modified)
    sv.period_save_thread()
    assert idle_calls == []


def test_period_save_disabled_does_not_rearm(monkeypatch):
    """With period 0 the timer is not re-armed."""
    timers = []
    monkeypatch.setattr(
        sourceview, "timeout_add_seconds", lambda *a: timers.append(a),
    )
    sv = _Adapter()
    sv.period_save = 0
    sv.period_save_thread()
    assert timers == []


def test_external_change_reload_keeps_cursor(monkeypatch):
    """Answering "yes" reloads the file at the current cursor offset."""
    monkeypatch.setattr(sourceview, "timeout_add", lambda *_a: None)
    sv = _Adapter("abcdef")
    sv.text_buffer.place_cursor(sv.text_buffer.get_iter_at_offset(3))
    sv._SourceView__file_name = "a.rst"
    sv._SourceView__pause_period = True
    sv.read_from_file = Mock()
    sv._on_file_changed_response(None, "yes", 99)
    sv.read_from_file.assert_called_once_with("a.rst", 3)
    assert sv._SourceView__pause_period is False


def test_external_change_ignore_remembers_ctime(monkeypatch):
    """Any other answer keeps the buffer and remembers the new ctime."""
    timers = []
    monkeypatch.setattr(sourceview, "timeout_add", lambda *a: timers.append(a))
    sv = _Adapter("abc")
    sv._SourceView__pause_period = True
    sv.read_from_file = Mock()
    sv._on_file_changed_response(None, "no", 99)
    sv.read_from_file.assert_not_called()
    assert sv._SourceView__last_ctime == 99
    assert sv._SourceView__pause_period is False
    assert timers
