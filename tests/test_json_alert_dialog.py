"""Tests for the dialog shown on an invalid JSONPath expression."""

import gi
import pytest

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from formiko.json_preview import JSONPreview  # noqa: E402


@pytest.fixture
def shown(monkeypatch):
    """Record the dialogs shown instead of presenting them."""
    dialogs = []
    monkeypatch.setattr(
        Gtk.AlertDialog,
        "show",
        lambda dialog, parent: dialogs.append((dialog, parent)),
    )
    return dialogs


def test_invalid_jsonpath_is_reported_in_a_dialog(shown):
    """A bad filter expression shows its parser message to the user."""
    preview = JSONPreview()
    preview._win = object()

    preview._show_error_dialog("no such token")

    ((dialog, parent),) = shown
    assert dialog.get_message() == "Invalid JSONPath Expression"
    assert dialog.get_detail() == "no such token"
    assert parent is preview._win
