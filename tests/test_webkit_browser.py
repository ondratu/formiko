"""Tests for the WebKit backend that do not need a display server.

The ``WebView`` is replaced by a fake, so only formiko's own glue is run.
"""

import gi
import pytest

try:
    gi.require_version("WebKit", "6.0")
except ValueError:
    pytest.skip("WebKit typelib is not installed", allow_module_level=True)

from formiko import webkit_browser
from formiko.webkit_browser import WebKitBrowserView


class _FakeContext:
    """Main context that delivers queued events on ``iteration()``.

    ``iteration(False)`` returns at once whether or not anything was
    dispatched, so waiting with it burns CPU until the answer arrives;
    only a blocking iteration sleeps until an event is ready.
    """

    def __init__(self):
        self.queue = []
        self.blocking = []

    def iteration(self, may_block):
        self.blocking.append(may_block)
        if len(self.blocking) > 1000:
            msg = "still waiting after 1000 iterations"
            raise AssertionError(msg)
        if not self.queue:
            if may_block:
                msg = "the main loop would sleep forever"
                raise AssertionError(msg)
            return False
        if may_block or len(self.blocking) > 5:
            self.queue.pop(0)()
        return True


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def to_double(self):
        return self.value


class _FakeView:
    """The bits of ``WebKit.WebView`` used by the calls under test."""

    def __init__(self, context, position=0.25):
        self.context = context
        self.position = position
        self.scripts = []
        self.controller = _FakeFindController(context)

    def evaluate_javascript(self, script, _length, _w, _s, _c, callback):
        self.scripts.append(script)
        if callback is not None:
            self.context.queue.append(lambda: callback(self, None))

    def evaluate_javascript_finish(self, _result):
        return _FakeResult(self.position)

    def get_find_controller(self):
        return self.controller


class _FakeFindController:
    def __init__(self, context):
        self.context = context
        self.text = None
        self.view = None

    def get_search_text(self):
        return self.text

    def search(self, text, _options, _max_matches):
        self.text = text
        self.context.queue.append(self.view._on_found_text)

    def search_next(self):
        pass


@pytest.fixture
def browser_view(monkeypatch):
    """Return a ``WebKitBrowserView`` on a fake view and main context."""
    context = _FakeContext()
    monkeypatch.setattr(
        webkit_browser.MainContext, "default", staticmethod(lambda: context),
    )
    view = WebKitBrowserView.__new__(WebKitBrowserView)
    view._view = _FakeView(context)
    view._view.controller.view = view
    view._search_done = None
    view._position = None
    view._fgcolor = None
    view._context = context
    return view


def test_scroll_fraction_waits_without_spinning_the_cpu(browser_view):
    """Waiting for the script result must sleep in the main loop."""
    assert browser_view.get_scroll_fraction() == 0.25
    assert all(browser_view._context.blocking)


def test_scroll_fraction_accepts_a_negative_position(browser_view):
    """A negative answer is a value, not "no answer yet"."""
    browser_view._view.position = -0.5

    assert browser_view.get_scroll_fraction() == -0.5


def test_search_waits_without_spinning_the_cpu(browser_view):
    """Searching for new text sleeps in the main loop until answered."""
    assert browser_view.find_next("needle") is True
    assert all(browser_view._context.blocking)
