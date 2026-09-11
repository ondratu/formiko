"""Tests for desktop file open modes."""

from unittest.mock import Mock

from formiko.application import Application
from formiko.editor import EditorType
from formiko.window import AppWindow


def test_open_files_in_new_window_puts_all_files_in_one_window(monkeypatch):
    """The new-window action uses one window and multiple tabs."""
    window = Mock()
    monkeypatch.setattr(
        "formiko.application.AppWindow",
        Mock(return_value=window),
    )
    app = Application()
    app.add_window = Mock()

    result = app.open_files_in_new_window(
        EditorType.SOURCE,
        ["one.md", "two.md"],
    )

    assert result is window
    window.new_tab.assert_called_once_with("two.md")
    window.present.assert_called_once_with()


def test_open_files_in_new_tab_falls_back_to_new_window():
    """The new-tab action creates a window when none is active."""
    app = Application()
    app.get_active_window = Mock(return_value=None)
    app.open_files_in_new_window = Mock(return_value="window")

    result = app.open_files_in_new_tab(
        EditorType.SOURCE,
        ["one.md"],
    )

    assert result == "window"
    app.open_files_in_new_window.assert_called_once_with(
        EditorType.SOURCE,
        ["one.md"],
    )


def test_open_files_in_new_tab_uses_active_window():
    """The new-tab action delegates each file to the active window."""
    window = Mock(spec=AppWindow)
    app = Application()
    app.get_active_window = Mock(return_value=window)

    result = app.open_files_in_new_tab(
        EditorType.SOURCE,
        ["one.md", "two.md"],
    )

    assert result is window
    assert window.open_document.call_count == 2
    window.open_document.assert_any_call("one.md")
    window.open_document.assert_any_call("two.md")


def test_open_files_in_new_tab_creates_empty_tab_without_files():
    """The new-tab action creates a blank tab when no files are supplied."""
    window = Mock(spec=AppWindow)
    app = Application()
    app.get_active_window = Mock(return_value=window)

    result = app.open_files_in_new_tab(EditorType.SOURCE, [])

    assert result is window
    window.new_tab.assert_called_once_with()
    window.present.assert_called_once_with()


def test_missing_dependency_does_not_quit_existing_window(monkeypatch):
    """A dependency error from a second invocation keeps the main window."""
    class ExistingWindow:
        pass

    monkeypatch.setattr("formiko.application.AppWindow", ExistingWindow)
    app = Application()
    app.get_windows = Mock(return_value=[ExistingWindow()])
    app.quit = Mock()
    error_window = Mock()

    app._close_missing_dependency_window(error_window)

    error_window.close.assert_called_once_with()
    app.quit.assert_not_called()


def test_missing_dependency_quits_without_existing_window(monkeypatch):
    """A standalone dependency error closes its application."""
    class ExistingWindow:
        pass

    monkeypatch.setattr("formiko.application.AppWindow", ExistingWindow)
    app = Application()
    app.get_windows = Mock(return_value=[])
    app.quit = Mock()
    error_window = Mock()

    app._close_missing_dependency_window(error_window)

    error_window.close.assert_called_once_with()
    app.quit.assert_called_once_with()
