"""Tests for the file browser: directory tracking vs. loading/clearing.

``set_directory`` only records which directory to browse - it never
touches the displayed rows. Loading them from disk is ``refresh()``,
emptying them is ``clear()``; callers (the sidebar show/hide handler)
decide when each happens.
"""

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from formiko.filebrowser import FileBrowser  # noqa: E402


def _make_browser(default_directory="/documents"):
    """Build a lightweight :class:`FileBrowser` (no window needed)."""
    browser = FileBrowser.__new__(FileBrowser)
    browser._directory = ""
    browser._default_directory = default_directory
    browser._dir_label = Gtk.Label()
    browser._list_box = Gtk.ListBox()
    return browser


def _row_labels(browser):
    labels = []
    row = browser._list_box.get_first_child()
    while row is not None:
        labels.append(row.get_child().get_label())
        row = row.get_next_sibling()
    return labels


def test_set_directory_only_records_the_directory():
    """set_directory() never loads rows or clears existing ones."""
    browser = _make_browser()
    dummy_row = Gtk.ListBoxRow()
    browser._list_box.append(dummy_row)

    browser.set_directory("/project")

    assert browser._directory == "/project"
    assert browser._list_box.get_first_child() is dummy_row


def test_set_directory_falls_back_to_default_for_empty_directory():
    """An empty directory (e.g. an unsaved tab) uses the default one."""
    browser = _make_browser()

    browser.set_directory("")

    assert browser._directory == "/documents"


def test_refresh_lists_known_files_only(tmp_path):
    """refresh() loads known files from the current directory."""
    (tmp_path / "doc.md").write_text("hi")
    (tmp_path / "notes.bin").write_bytes(b"\x00")
    browser = _make_browser()
    browser.set_directory(str(tmp_path))

    browser.refresh()

    assert _row_labels(browser) == ["doc.md"]


def test_refresh_clears_previous_rows_first(tmp_path):
    """A second refresh() replaces stale rows instead of appending."""
    (tmp_path / "a.md").write_text("a")
    browser = _make_browser()
    browser.set_directory(str(tmp_path))
    browser.refresh()

    (tmp_path / "a.md").unlink()
    (tmp_path / "b.md").write_text("b")
    browser.refresh()

    assert _row_labels(browser) == ["b.md"]


def test_refresh_does_nothing_without_a_directory():
    """refresh() is a no-op (beyond clearing) before any directory is set."""
    browser = _make_browser(default_directory="")

    browser.refresh()

    assert browser._list_box.get_first_child() is None


def test_clear_empties_the_list_without_touching_the_directory(tmp_path):
    """clear() removes rows but keeps tracking the current directory."""
    (tmp_path / "a.md").write_text("a")
    browser = _make_browser()
    browser.set_directory(str(tmp_path))
    browser.refresh()

    browser.clear()

    assert browser._list_box.get_first_child() is None
    assert browser._directory == str(tmp_path)
