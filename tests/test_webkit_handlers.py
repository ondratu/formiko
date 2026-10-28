"""Tests for WebKit signal handlers that run without a display."""

from types import SimpleNamespace
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
try:
    gi.require_version("WebKit", "6.0")
except ValueError:
    pytest.skip("WebKit typelib is not installed", allow_module_level=True)

from formiko import webkit_browser  # noqa: E402
from formiko.browser import (  # noqa: E402
    EVENT_HOVER_CHANGED,
    EVENT_LINK_CLICKED,
    EVENT_LOAD_FINISHED,
    EVENT_USER_SCROLLED,
    HoverTarget,
)
from formiko.webkit_browser import WebKitBrowserView as View  # noqa: E402


def _adapter(**kwargs):
    return SimpleNamespace(_emit=Mock(), **kwargs)


def _hit(link=None, image=None, media=None):
    return Mock(
        **{
            "context_is_link.return_value": link is not None,
            "context_is_image.return_value": image is not None,
            "context_is_media.return_value": media is not None,
            "get_link_uri.return_value": link,
            "get_image_uri.return_value": image,
            "get_media_uri.return_value": media,
        },
    )


@pytest.mark.parametrize(
    ("hit", "expected"),
    [
        (_hit(link="http://l"), HoverTarget("link", "http://l")),
        (_hit(image="http://i"), HoverTarget("image", "http://i")),
        (_hit(media="http://m"), HoverTarget("media", "http://m")),
        (_hit(), None),
    ],
)
def test_mouse_target_changed(hit, expected):
    """The hover target kind follows the WebKit hit test result."""
    ns = _adapter()
    View._on_mouse_target_changed(ns, None, hit, 0)
    ns._emit.assert_called_once_with(EVENT_HOVER_CHANGED, expected)


def test_link_wins_over_image():
    """A linked image reports the link."""
    hit = _hit(link="http://l", image="http://i")
    ns = _adapter()
    View._on_mouse_target_changed(ns, None, hit, 0)
    ns._emit.assert_called_once_with(
        EVENT_HOVER_CHANGED, HoverTarget("link", "http://l"),
    )


def test_load_changed_ignores_unfinished_events():
    """Only the FINISHED event triggers script injection."""
    ns = _adapter(_view=Mock(), _apply_foreground_color=Mock())
    View._on_load_changed(ns, None, webkit_browser.LoadEvent.STARTED)
    ns._emit.assert_not_called()
    ns._view.evaluate_javascript.assert_not_called()


def test_load_finished_injects_listeners_and_emits():
    """A finished load installs both JS listeners and notifies."""
    ns = _adapter(_view=Mock(), _apply_foreground_color=Mock())
    View._on_load_changed(ns, None, webkit_browser.LoadEvent.FINISHED)
    ns._apply_foreground_color.assert_called_once_with()
    scripts = [c.args[0] for c in ns._view.evaluate_javascript.call_args_list]
    assert scripts == [
        webkit_browser.JS_SCROLL_LISTENER,
        webkit_browser.JS_LINK_LISTENER,
    ]
    ns._emit.assert_called_once_with(EVENT_LOAD_FINISHED)


class _FakeDecision:
    def __init__(self, nav_type, uri):
        self.ignore = Mock()
        self.action = Mock(
            **{
                "get_navigation_type.return_value": nav_type,
                "get_request.return_value.get_uri.return_value": uri,
            },
        )

    def get_navigation_action(self):
        return self.action


@pytest.fixture
def _fake_decision_class(monkeypatch):
    """Make ``_FakeDecision`` count as a NavigationPolicyDecision."""
    monkeypatch.setattr(
        webkit_browser, "NavigationPolicyDecision", _FakeDecision,
    )


@pytest.mark.usefixtures("_fake_decision_class")
def test_policy_ignores_non_navigation_decisions():
    """Other decision kinds are left to WebKit."""
    ns = _adapter()
    assert View._on_decide_policy(ns, None, object(), 0) is False
    ns._emit.assert_not_called()


@pytest.mark.usefixtures("_fake_decision_class")
def test_policy_lets_other_navigation_types_through():
    """Non-click navigation (reload, load) is not intercepted."""
    decision = _FakeDecision(webkit_browser.NavigationType.RELOAD, "u")
    ns = _adapter()
    assert View._on_decide_policy(ns, None, decision, 0) is False
    decision.ignore.assert_not_called()


@pytest.mark.usefixtures("_fake_decision_class")
def test_policy_intercepts_link_clicks():
    """A clicked link is cancelled and reported to the application."""
    decision = _FakeDecision(
        webkit_browser.NavigationType.LINK_CLICKED, "http://x/",
    )
    ns = _adapter()
    assert View._on_decide_policy(ns, None, decision, 0) is True
    decision.ignore.assert_called_once_with()
    ns._emit.assert_called_once_with(EVENT_LINK_CLICKED, "http://x/")


def test_scroll_and_link_messages():
    """JS messages are translated to browser events."""
    ns = _adapter()
    View._on_scroll_message(ns, None, None)
    ns._emit.assert_called_with(EVENT_USER_SCROLLED)
    View._on_link_message(
        ns, None, Mock(**{"to_string.return_value": "#anchor"}),
    )
    ns._emit.assert_called_with(EVENT_LINK_CLICKED, "#anchor")


def test_context_menu_is_suppressed():
    """The context menu handler claims the event."""
    assert View._on_context_menu(_adapter()) is True


def test_found_and_failed_text_track_search_state():
    """Search results toggle the done flag."""
    ns = _adapter(_search_done=None)
    View._on_found_text(ns)
    assert ns._search_done is True
    View._on_failed_to_find_text(ns)
    assert ns._search_done is False


def test_render_incremental_patches_body_with_escaped_json():
    """The body is replaced through safely JSON-encoded JavaScript."""
    ns = _adapter(_view=Mock(), _fgcolor="#112233")
    assert View.render_incremental(ns, '<p>"q"</p>\n') is True
    script = ns._view.evaluate_javascript.call_args.args[0]
    assert 'document.fgColor="#112233";' in script
    assert r'document.body.innerHTML="<p>\"q\"</p>\n";' in script


def test_set_background_color_parses_hex():
    """The hex colour is converted to Gdk.RGBA."""
    ns = _adapter(_view=Mock())
    View.set_background_color(ns, "#ff0000")
    rgba = ns._view.set_background_color.call_args.args[0]
    assert (rgba.red, rgba.green, rgba.blue) == (1.0, 0.0, 0.0)


def test_set_foreground_color_remembers_and_applies():
    """The text colour is stored and applied immediately."""
    ns = _adapter(_apply_foreground_color=Mock(), _fgcolor="")
    View.set_foreground_color(ns, "#abcdef")
    assert ns._fgcolor == "#abcdef"
    ns._apply_foreground_color.assert_called_once_with()


def test_stop_search_finishes_find_controller():
    """Stopping search clears WebKit's highlighting."""
    ns = _adapter(_view=Mock())
    View.stop_search(ns)
    controller = ns._view.get_find_controller.return_value
    controller.search_finish.assert_called_once()
