"""Tests for the mistune < 2 task list renderer.

The installed mistune is usually new, so a minimal stand-in for the old
``mistune.Renderer`` API is injected and the module is loaded privately.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

SOURCE = Path(__file__).parent.parent / "formiko" / "mistune_preview.py"


class _Renderer:
    def __init__(self, escape=True):
        self.escape = escape

    def list_item(self, text):
        return f"<li>{text}</li>\n"


class _Markdown:
    def __init__(self, renderer):
        self.renderer = renderer

    def __call__(self, text):
        return f"<p>{text}</p>"


@pytest.fixture
def legacy(monkeypatch):
    """Load mistune_preview against a fake pre-2.0 mistune."""
    fake = types.ModuleType("mistune")
    fake.Renderer = _Renderer
    fake.Markdown = _Markdown
    monkeypatch.setitem(sys.modules, "mistune", fake)
    spec = importlib.util.spec_from_file_location(
        "formiko_mistune_legacy", SOURCE,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unchecked_task_gets_checkbox(legacy):
    """An open task becomes a disabled, unchecked checkbox."""
    html = legacy._TaskListRenderer().list_item("[ ] todo")
    assert html == '<li><input type="checkbox" disabled> todo</li>\n'


@pytest.mark.parametrize("mark", ["x", "X"])
def test_checked_task_gets_checked_checkbox(legacy, mark):
    """Both x and X mark a finished task."""
    html = legacy._TaskListRenderer().list_item(f"[{mark}] done")
    assert html == '<li><input type="checkbox" disabled checked> done</li>\n'


def test_plain_item_uses_default_rendering(legacy):
    """Items without a marker are left to the base renderer."""
    assert legacy._TaskListRenderer().list_item("plain") == "<li>plain</li>\n"


def test_marker_must_be_followed_by_space(legacy):
    """``[x]text`` is not a task."""
    html = legacy._TaskListRenderer().list_item("[x]text")
    assert "checkbox" not in html


def test_preview_expands_tabs_and_wraps_document(legacy):
    """The legacy preview builds a full HTML document."""
    html = legacy.MistunePreview().to_html("a\tb", tab_width=4)
    assert html.startswith("<html>")
    assert "<p>a   b</p>" in html
