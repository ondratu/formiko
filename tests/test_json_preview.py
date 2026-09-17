"""Tests for the JSON preview HTML and its folding script."""

import sys
from json import loads

from formiko.browser import EVENT_LOAD_FINISHED
from formiko.json_preview import JSONPreview

from .test_browser_view import _Minimal


class _ScriptingBrowser(_Minimal):
    """Browser stand-in that supports scripting and records it."""

    def __init__(self):
        super().__init__()
        self.scripts = []
        self.loads = 0

    def can_run_script(self):
        return True

    def run_script(self, script):
        self.scripts.append(script)

    def load(self, html, mime_type, base_uri):
        self.loads += 1

    def finish_load(self):
        self._emit(EVENT_LOAD_FINISHED)


def test_nested_json_can_be_rendered_as_deep_as_it_can_be_parsed():
    """Rendering must not use up the stack sooner than parsing does."""
    depth = int(sys.getrecursionlimit() * 0.7)
    data = loads("[" * depth + "]" * depth)

    html = JSONPreview()._generate_html(data)

    assert html.count('class="jblock"') == depth


def _preview_with_browser():
    preview = JSONPreview()
    browser = _ScriptingBrowser()
    preview.webview = browser
    return preview, browser


def test_fold_script_is_injected_once_after_a_load():
    """Repeated renders before a load leave a single pending injection."""
    preview, browser = _preview_with_browser()

    preview.to_html('{"a": 1}')
    preview.to_html('{"a": 2}')
    browser.finish_load()

    assert len(browser.scripts) == 1


def test_filter_render_and_edit_share_one_injection():
    """Editing, then filtering, before the load finishes injects once."""
    preview, browser = _preview_with_browser()
    preview.to_html('{"a": 1}')

    preview._render({"a": 1}, ["a"], {"", "a"}, "$.a", 1)
    browser.finish_load()

    assert browser.loads == 1
    assert len(browser.scripts) == 1


def test_fold_script_is_not_injected_by_later_loads():
    """The injection is one-shot: a load nobody asked for adds nothing."""
    preview, browser = _preview_with_browser()
    preview.to_html('{"a": 1}')
    browser.finish_load()

    browser.finish_load()

    assert len(browser.scripts) == 1
