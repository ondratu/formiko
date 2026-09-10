"""GTK integration tests for the file browser."""

import gi
import pytest

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from formiko.filebrowser import FileBrowser  # noqa: E402

pytestmark = pytest.mark.gtk_integration


def test_filebrowser_refresh_populates_real_gtk_rows(tmp_path, monkeypatch):
    """FileBrowser updates a real Gtk.ListBox from its model."""
    (tmp_path / "doc.md").write_text("hi")
    monkeypatch.setattr(
        "formiko.filebrowser.get_user_special_dir",
        lambda _directory: None,
    )
    browser = FileBrowser()
    browser.set_directory(str(tmp_path))
    browser.refresh()
    row = browser._list_box.get_first_child()
    assert isinstance(row, Gtk.ListBoxRow)
    assert row.get_child().get_label() == "doc.md"
