"""Tests for list continuation in the editor."""

import contextlib

import gi
import pytest

gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from formiko.sourceview import _list_continuation_marker  # noqa: E402


@pytest.mark.parametrize(
    ("line", "marker"),
    [
        ("1. first", "2. "),
        ("9. nine", "10. "),
        ("  3. nested", "  4. "),
        ("- item", "- "),
        ("* item", "* "),
        ("    - deep", "    - "),
        ("\t* tab", "\t* "),
    ],
)
def test_continuation_marker(line, marker):
    """The next item reuses the indentation and bumps numbers."""
    assert _list_continuation_marker(line) == marker


@pytest.mark.parametrize(
    "line",
    ["", "plain text", "- ", "1. ", "-no space", "1.no space", "a. letter"],
)
def test_no_continuation(line):
    """Empty items and non-list lines do not continue."""
    assert _list_continuation_marker(line) is None
