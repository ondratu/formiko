"""Tests for the litehtml backend that do not need a display server."""

from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

pytest.importorskip("litehtmlpy", reason="needs the litehtmlpy package")

from formiko.litehtml_browser import LitehtmlBrowserView  # noqa: E402


def test_print_page_tells_that_printing_is_not_implemented(monkeypatch):
    """Printing is not supported yet, so the user gets a message."""
    shown = []
    monkeypatch.setattr(
        Gtk.AlertDialog,
        "show",
        lambda dialog, parent: shown.append((dialog.get_message(), parent)),
    )
    parent = Mock()

    LitehtmlBrowserView.print_page(Mock(), parent)

    assert shown == [
        ("Printing isn't implemented yet for the litehtml backend.", parent),
    ]
