"""Tests for :meth:`AppWindow._sync_file_browser` / sidebar toggling.

``_sync_file_browser`` only points the file browser at the active
document's directory (cheap, no I/O). Loading and clearing the displayed
rows is entirely up to whoever shows/hides the sidebar - see
:mod:`tests.test_filebrowser` for ``refresh()``/``clear()`` themselves.
"""

from unittest.mock import Mock

import gi

gi.require_version("GLib", "2.0")

from gi.repository import GLib  # noqa: E402

from formiko.window import AppWindow  # noqa: E402


def _make_fake_window(directory: str | None) -> Mock:
    """Build a duck-typed stand-in for ``AppWindow``."""
    win = Mock()
    win.file_browser = Mock()
    win.active_page = Mock()
    win.active_page.file_path = f"{directory}/doc.md" if directory else ""
    # _on_toggle_sidebar calls self._sync_file_browser(): wire it to the
    # real bound method instead of an unrelated auto-mocked attribute.
    win._sync_file_browser = (
        lambda *a, **kw: AppWindow._sync_file_browser(win, *a, **kw)
    )
    return win


def test_sync_file_browser_only_sets_directory():
    """Syncing never loads or clears rows, just records the directory."""
    win = _make_fake_window("/project")

    AppWindow._sync_file_browser(win)

    win.file_browser.set_directory.assert_called_once_with("/project")
    win.file_browser.refresh.assert_not_called()
    win.file_browser.clear.assert_not_called()


def test_toggle_sidebar_syncs_and_loads_when_showing():
    """Showing the sidebar points it at the active doc and loads it."""
    win = _make_fake_window("/project")
    action = Mock()
    action.get_state.return_value = GLib.Variant("b", False)

    AppWindow._on_toggle_sidebar(win, action)

    win.file_browser.set_directory.assert_called_once_with("/project")
    win.file_browser.refresh.assert_called_once_with()
    win.file_browser.clear.assert_not_called()
    win.overlay_split.set_show_sidebar.assert_called_once_with(True)


def test_toggle_sidebar_clears_when_hiding():
    """Hiding the sidebar just empties it, without touching the directory."""
    win = _make_fake_window("/project")
    action = Mock()
    action.get_state.return_value = GLib.Variant("b", True)

    AppWindow._on_toggle_sidebar(win, action)

    win.file_browser.set_directory.assert_not_called()
    win.file_browser.refresh.assert_not_called()
    win.file_browser.clear.assert_called_once_with()
    win.overlay_split.set_show_sidebar.assert_called_once_with(False)
