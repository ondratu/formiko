"""WebKitGTK implementation of the :class:`formiko.browser.BrowserView`.

All WebKit-specific API (JavaScript evaluation, the find controller, print
operations, navigation policy, script message handlers, ...) lives here and
nowhere else, so :mod:`formiko.renderer` and :mod:`formiko.json_preview`
never import ``gi.repository.WebKit`` directly.
"""

from json import dumps

from gi import require_version

require_version("WebKit", "6.0")

from gi.repository import Gdk, Gtk  # noqa: E402
from gi.repository.GLib import (  # noqa: E402
    MAXUINT,
    Bytes,
    Error,
    LogLevelFlags,
    MainContext,
    log_default_handler,
)
from gi.repository.WebKit import (  # noqa: E402
    FindOptions,
    LoadEvent,
    NavigationPolicyDecision,
    NavigationType,
    PrintOperation,
    WebView,
)

from formiko.browser import (  # noqa: E402
    EVENT_HOVER_CHANGED,
    EVENT_LINK_CLICKED,
    EVENT_LOAD_FINISHED,
    EVENT_USER_SCROLLED,
    BrowserView,
    HoverTarget,
)

JS_POSITION = """
window.scrollY/(document.documentElement.scrollHeight-window.innerHeight)
"""

JS_SCROLL = """
    window.scrollTo(
        0,
        (document.documentElement.scrollHeight-window.innerHeight)*%f);
"""

# Debounced scroll listener, re-injected after every page load (each load
# is a fresh JS context). Used to emit EVENT_USER_SCROLLED for WakaTime -
# reading/scrolling is considered activity same as editing.
JS_SCROLL_LISTENER = """
(function () {
    if (window.__formikoScrollHooked) return;
    window.__formikoScrollHooked = true;
    let timer;
    window.addEventListener("scroll", function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
            window.webkit.messageHandlers.formikoScroll.postMessage("");
        }, 500);
    }, {passive: true});
})();
"""

JS_LINK_LISTENER = """
(function () {
    if (window.__formikoLinksHooked) return;
    window.__formikoLinksHooked = true;
    document.addEventListener("click", function (event) {
        const target = event.target instanceof Element
            ? event.target
            : event.target.parentElement;
        const link = target && target.closest("a[href]");
        if (!link) return;
        event.preventDefault();
        window.webkit.messageHandlers.formikoLink.postMessage(link.href);
    }, true);
})();
"""


class WebKitBrowserView(BrowserView):
    """Browser backend based on ``gi.repository.WebKit`` (WebKitGTK 6.0)."""

    def __init__(self) -> None:
        super().__init__()
        self._search_done = None
        self._fgcolor = None
        self._position = None

        self._view = WebView()
        self._view.connect(
            "mouse-target-changed", self._on_mouse_target_changed,
        )
        self._view.connect("context-menu", self._on_context_menu)
        self._view.connect("load-changed", self._on_load_changed)
        self._view.connect("decide-policy", self._on_decide_policy)

        content_manager = self._view.get_user_content_manager()
        content_manager.register_script_message_handler("formikoScroll")
        content_manager.register_script_message_handler("formikoLink")
        content_manager.connect(
            "script-message-received::formikoScroll",
            self._on_scroll_message,
        )
        content_manager.connect(
            "script-message-received::formikoLink",
            self._on_link_message,
        )

        settings = self._view.get_settings()
        settings.set_enable_javascript_markup(False)  # XSS fix

        find_controller = self._view.get_find_controller()
        find_controller.connect("found-text", self._on_found_text)
        find_controller.connect(
            "failed-to-find-text", self._on_failed_to_find_text,
        )

    # ------------------------------------------------------------------
    # BrowserView interface
    # ------------------------------------------------------------------

    @property
    def widget(self) -> Gtk.Widget:
        """Return the underlying WebKit.WebView."""
        return self._view

    def load(self, html: str, mime_type: str, base_uri: str) -> None:
        """Replace the whole document with *html*."""
        self._view.load_bytes(
            Bytes(html.encode("utf-8")), mime_type, "UTF-8", base_uri,
        )

    def render_incremental(self, body_html: str) -> bool:
        """Patch ``<body>`` in place via JS instead of a full reload."""
        fgcolor_js = dumps(self._fgcolor)
        body_js = dumps(body_html)
        self._view.evaluate_javascript(
            f"document.fgColor={fgcolor_js};"
            f"document.body.innerHTML={body_js};",
            -1, None, None, None, None,
        )
        return True

    def set_background_color(self, hex_color: str) -> None:
        """Set the document's background color."""
        rgba = Gdk.RGBA()
        rgba.parse(hex_color)
        self._view.set_background_color(rgba)

    def set_foreground_color(self, hex_color: str) -> None:
        """Set the document's default text color."""
        self._fgcolor = hex_color
        self._apply_foreground_color()

    def set_fonts(
        self,
        font_family: str,
        font_size_px: int,
        mono_family: str,
        mono_size_px: int,
    ) -> None:
        """Set the default proportional and monospace fonts."""
        settings = self._view.get_settings()
        settings.set_default_font_family(font_family)
        settings.set_default_font_size(font_size_px)
        settings.set_monospace_font_family(mono_family)
        settings.set_default_monospace_font_size(mono_size_px)

    def get_scroll_fraction(self) -> float:
        """Return the current scroll position as a 0..1 fraction."""
        self._position = None
        self._view.evaluate_javascript(
            JS_POSITION, -1, None, None, None, self._on_position_result,
        )
        while self._position is None:
            MainContext.default().iteration(True)
        return self._position

    def scroll_to_fraction(self, fraction: float) -> None:
        """Scroll to a 0..1 fraction of the document height."""
        self._view.evaluate_javascript(
            JS_SCROLL % fraction, -1, None, None, None, None,
        )

    def scroll_to_anchor(self, anchor: str) -> None:
        """Scroll to the element with id/name *anchor*."""
        # The anchor comes from a link in the document: pass it only as a
        # JSON string, never spliced into a selector or other script text.
        self._view.evaluate_javascript(
            "(function (anchor) {"
            " var el = document.getElementById(anchor) ||"
            " Array.from(document.querySelectorAll('a[name]')).find("
            "function (a) { return a.getAttribute('name') === anchor; });"
            " if (el) el.scrollIntoView();"
            f"}})({dumps(anchor)});",
            -1, None, None, None, None,
        )

    def find_next(self, text: str) -> bool:
        """Search forward for *text*; return whether it was found."""
        return self._find(text, FindOptions.WRAP_AROUND, "search_next")

    def find_previous(self, text: str) -> bool:
        """Search backward for *text*; return whether it was found."""
        return self._find(
            text,
            FindOptions.WRAP_AROUND | FindOptions.BACKWARDS,
            "search_previous",
        )

    def stop_search(self) -> None:
        """Clear search highlighting/state."""
        self._view.get_find_controller().search_finish()

    def print_page(self, parent: Gtk.Window) -> None:
        """Run the platform print dialog for the current document."""
        po = PrintOperation.new(self._view)
        po.connect("failed", self._on_print_failed)
        po.run_dialog(parent)

    def can_run_script(self) -> bool:
        """Return True: WebKit always supports running scripts."""
        return True

    def run_script(self, script: str) -> None:
        """Run *script* in the document's script context."""
        self._view.evaluate_javascript(script, -1, None, None, None, None)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find(self, text: str, options: FindOptions, step: str) -> bool:
        """Start searching for *text*, or *step* to its next match.

        A new *text* is searched for right away, waiting for the answer;
        the same text again just moves on to the next (or previous) match.
        """
        controller = self._view.get_find_controller()
        if controller.get_search_text() != text:
            self._search_done = None
            controller.search(text, options, MAXUINT)
            while self._search_done is None:
                MainContext.default().iteration(True)
        elif self._search_done:
            getattr(controller, step)()
        return self._search_done

    def _apply_foreground_color(self) -> None:
        if self._fgcolor is not None:
            self._view.evaluate_javascript(
                f"document.fgColor={dumps(self._fgcolor)}",
                -1, None, None, None, None,
            )

    def _on_position_result(self, webview, result) -> None:
        try:
            js_value = webview.evaluate_javascript_finish(result)
            self._position = js_value.to_double()
        except Error:
            self._position = 0

    def _on_mouse_target_changed(
        self, _webview, hit_test_result, _modifiers,
    ) -> None:
        if hit_test_result.context_is_link():
            target = HoverTarget("link", hit_test_result.get_link_uri())
        elif hit_test_result.context_is_image():
            target = HoverTarget("image", hit_test_result.get_image_uri())
        elif hit_test_result.context_is_media():
            target = HoverTarget("media", hit_test_result.get_media_uri())
        else:
            target = None
        self._emit(EVENT_HOVER_CHANGED, target)

    def _on_context_menu(self, *_args) -> bool:
        return True  # disable context menu for now

    def _on_load_changed(self, _webview, load_event) -> None:
        if load_event != LoadEvent.FINISHED:
            return
        self._apply_foreground_color()
        self._view.evaluate_javascript(
            JS_SCROLL_LISTENER, -1, None, None, None, None,
        )
        self._view.evaluate_javascript(
            JS_LINK_LISTENER, -1, None, None, None, None,
        )
        self._emit(EVENT_LOAD_FINISHED)

    def _on_decide_policy(self, _webview, decision, _decision_type) -> bool:
        """Intercept link navigation and report it via EVENT_LINK_CLICKED."""
        if not isinstance(decision, NavigationPolicyDecision):
            return False
        action = decision.get_navigation_action()
        if action.get_navigation_type() != NavigationType.LINK_CLICKED:
            return False
        uri = action.get_request().get_uri()
        decision.ignore()
        self._emit(EVENT_LINK_CLICKED, uri)
        return True

    def _on_scroll_message(self, _content_manager, _js_result) -> None:
        self._emit(EVENT_USER_SCROLLED)

    def _on_link_message(self, _content_manager, js_result) -> None:
        """Handle links whose navigation policy WebKit does not emit."""
        self._emit(EVENT_LINK_CLICKED, js_result.to_string())

    def _on_found_text(self, *_args) -> None:
        self._search_done = True

    def _on_failed_to_find_text(self, *_args) -> None:
        self._search_done = False

    def _on_print_failed(self, _po, error) -> None:
        # FIXME: if dialog is used, application will lock :-(
        log_default_handler(
            "Application",
            LogLevelFlags.LEVEL_WARNING,
            error.message,
        )
