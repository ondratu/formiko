"""Tests for the file browser directory selection and refresh behavior."""

from unittest.mock import Mock

from formiko.filebrowser import FileBrowser


def _make_browser(default_directory="/documents"):
    """Build a lightweight stand-in for :class:`FileBrowser`."""
    browser = FileBrowser.__new__(FileBrowser)
    browser._directory = ""
    browser._default_directory = default_directory
    browser._refresh = Mock()
    return browser


def test_set_directory_refreshes_when_directory_is_unchanged():
    """The current directory is reloaded instead of using stale rows."""
    browser = _make_browser()
    browser._directory = "/documents"

    browser.set_directory("/documents")

    assert browser._directory == "/documents"
    browser._refresh.assert_called_once_with()


def test_set_directory_uses_default_for_empty_directory():
    """An empty document tab switches the browser to its default directory."""
    browser = _make_browser()

    browser.set_directory("")

    assert browser._directory == "/documents"
    browser._refresh.assert_called_once_with()


def test_set_directory_does_nothing_without_a_directory():
    """The browser remains empty when neither directory has been configured."""
    browser = _make_browser(default_directory="")

    browser.set_directory("")

    assert browser._directory == ""
    browser._refresh.assert_not_called()
