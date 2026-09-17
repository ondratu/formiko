"""Tests for the backend-independent part of the BrowserView interface."""

import logging
import sys
from types import ModuleType

import pytest

from formiko.browser import (
    EVENT_LOAD_FINISHED,
    BrowserView,
    create_browser_view,
)


class _Minimal(BrowserView):
    """Implements only the abstract members, with no behaviour."""

    widget = None

    def load(self, html, mime_type, base_uri): ...
    def set_background_color(self, hex_color): ...
    def set_foreground_color(self, hex_color): ...
    def set_fonts(self, *args): ...
    def get_scroll_fraction(self): return 0.0
    def scroll_to_fraction(self, fraction): ...
    def scroll_to_anchor(self, anchor): ...
    def find_next(self, text): return False
    def find_previous(self, text): return False
    def stop_search(self): ...
    def print_page(self, parent): ...


def test_handlers_run_in_registration_order_with_arguments():
    """Every handler of an event receives the emitted arguments."""
    view = _Minimal()
    calls = []
    view.connect("event", lambda *a: calls.append(("first", a)))
    view.connect("event", lambda *a: calls.append(("second", a)))

    view._emit("event", 1, "two")

    assert calls == [("first", (1, "two")), ("second", (1, "two"))]


def test_disconnect_removes_only_that_handler():
    """A disconnected handler is not called any more."""
    view = _Minimal()
    calls = []
    first = view.connect("event", lambda: calls.append("first"))
    view.connect("event", lambda: calls.append("second"))

    view.disconnect(first)
    view._emit("event")

    assert calls == ["second"]


def test_handler_may_disconnect_itself_while_emitting():
    """One-shot handlers (as used for JSON folding) can unregister."""
    view = _Minimal()
    calls = []

    def once():
        calls.append("once")
        view.disconnect(handler_id)

    handler_id = view.connect("event", once)
    view.connect("event", lambda: calls.append("other"))

    view._emit("event")
    view._emit("event")

    assert calls == ["once", "other", "other"]


def test_failing_handler_does_not_stop_the_others(caplog):
    """Like GObject signals, one broken handler must not starve the rest."""
    view = _Minimal()
    calls = []

    def broken():
        msg = "boom"
        raise RuntimeError(msg)

    view.connect(EVENT_LOAD_FINISHED, broken)
    view.connect(EVENT_LOAD_FINISHED, lambda: calls.append("second"))

    with caplog.at_level(logging.ERROR):
        view._emit(EVENT_LOAD_FINISHED)

    assert calls == ["second"]
    assert "boom" in caplog.text


def test_scripting_is_unsupported_by_default():
    """A backend without scripting says so and refuses to run scripts."""
    view = _Minimal()

    assert view.can_run_script() is False
    assert view.render_incremental("<p>x</p>") is False
    with pytest.raises(NotImplementedError):
        view.run_script("1")


def test_create_browser_view_returns_the_webkit_backend(monkeypatch):
    """WebKit is the only backend so far."""
    module = ModuleType("formiko.webkit_browser")
    module.WebKitBrowserView = lambda: "webkit"
    monkeypatch.setitem(sys.modules, "formiko.webkit_browser", module)

    assert create_browser_view() == "webkit"
