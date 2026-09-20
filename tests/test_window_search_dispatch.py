"""Tests for choosing whether search acts on the editor or the preview."""

from unittest.mock import Mock

import gi

gi.require_version("GLib", "2.0")

from formiko.editor import EditorType  # noqa: E402
from formiko.window import AppWindow, GtkSourceView  # noqa: E402


def _pane(*, visible=True, owns_focus=False):
    """Return a fake editor/renderer pane."""
    pane = Mock()
    pane.props.visible = visible
    pane.owns_focus_widget.return_value = owns_focus
    return pane


def _window(focused=None, *, page=None, search_mode=True):
    """Build a duck-typed ``AppWindow`` whose search helpers are real."""
    win = Mock()
    win.focused = focused
    win.active_page = page
    win.search.get_search_mode.return_value = search_mode
    win.search_entry.get_text.return_value = "needle"
    win._search_target = lambda *a: AppWindow._search_target(win, *a)
    win._dispatch_find = lambda *a: AppWindow._dispatch_find(win, *a)
    return win


def _page(editor, renderer, editor_type=EditorType.SOURCE):
    page = Mock()
    page.editor = editor
    page.renderer = renderer
    page.editor_type = editor_type
    return page


def test_focused_source_view_takes_the_search():
    """Search follows keyboard focus into the editor."""
    editor, renderer = _pane(), _pane()
    win = _window(Mock(spec=GtkSourceView))

    page = _page(editor, renderer)

    target = AppWindow._search_target(win, page, editor, renderer)

    assert target is editor


def test_focused_preview_takes_the_search():
    """Search follows keyboard focus into the preview."""
    editor, renderer = _pane(), _pane(owns_focus=True)
    win = _window(Mock())

    page = _page(editor, renderer)

    target = AppWindow._search_target(win, page, editor, renderer)

    assert target is renderer


def test_visible_editor_is_searched_without_focus():
    """Nothing focused: the source editor wins if it is shown."""
    editor, renderer = _pane(), _pane()
    win = _window()

    page = _page(editor, renderer)

    target = AppWindow._search_target(win, page, editor, renderer)

    assert target is editor


def test_preview_is_searched_when_the_editor_is_hidden():
    """Nothing focused and no editor shown: fall back to the preview."""
    editor, renderer = _pane(visible=False), _pane()
    win = _window()

    page = _page(editor, renderer)

    target = AppWindow._search_target(win, page, editor, renderer)

    assert target is renderer


def test_nothing_is_searched_without_a_page():
    """There is nothing to search in when no document is open."""
    assert AppWindow._search_target(_window(), None, None, None) is None


def test_find_next_asks_the_target_for_the_search_text():
    """The result of the target's search is handed back to the caller."""
    editor, renderer = _pane(), _pane(owns_focus=True)
    renderer.do_next_match.return_value = True
    win = _window(Mock(), page=_page(editor, renderer))

    assert AppWindow._dispatch_find(win, "do_next_match") is True
    renderer.do_next_match.assert_called_once_with("needle")
    editor.do_next_match.assert_not_called()


def test_find_previous_uses_the_previous_match_method():
    """Backwards search calls the target's previous-match method."""
    editor, renderer = _pane(), _pane()
    editor.do_previous_match.return_value = True
    win = _window(page=_page(editor, renderer))

    assert AppWindow._dispatch_find(win, "do_previous_match") is True
    editor.do_previous_match.assert_called_once_with("needle")


def test_find_does_nothing_outside_search_mode():
    """Without an open search bar no pane is searched."""
    editor, renderer = _pane(), _pane()
    win = _window(page=_page(editor, renderer), search_mode=False)

    assert AppWindow._dispatch_find(win, "do_next_match") is False
    editor.do_next_match.assert_not_called()


def test_find_does_nothing_without_a_document():
    """No page, no search."""
    assert AppWindow._dispatch_find(_window(), "do_next_match") is False
