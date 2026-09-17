"""Abstract interface for the HTML preview widget.

:class:`BrowserView` decouples :class:`formiko.renderer.Renderer` from any
particular HTML rendering engine. ``formiko.webkit_browser.WebKitBrowserView``
(the default) and ``formiko.litehtml_browser.LitehtmlBrowserView``
(experimental, opt-in via ``$FORMIKO_BROWSER=litehtml``) both implement it;
:func:`create_browser_view` picks between them.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Callable

    from gi.repository import Gtk

logger = logging.getLogger(__name__)

#: Environment variable selecting the backend; see :func:`create_browser_view`.
ENV_BACKEND = "FORMIKO_BROWSER"

#: Emitted once a freshly loaded document has finished rendering. No payload.
EVENT_LOAD_FINISHED = "load-finished"
#: Emitted when the user scrolls the rendered document. No payload.
EVENT_USER_SCROLLED = "user-scrolled"
#: Emitted when the user clicks a link. Payload: the target URI (str).
EVENT_LINK_CLICKED = "link-clicked"
#: Emitted when the pointer enters/leaves a link, image or media element.
#: Payload: a :class:`HoverTarget`, or ``None`` once the pointer leaves it.
EVENT_HOVER_CHANGED = "hover-changed"


class HoverTarget(NamedTuple):
    """Element the pointer is currently hovering over."""

    kind: str  # "link", "image" or "media"
    uri: str


class BrowserView(ABC):
    """Interface an embeddable HTML preview backend must implement.

    Callers never touch a backend's native widget or engine API directly;
    everything they need - embedding, loading content, scrolling, search,
    printing, theming - goes through this contract, and events flow back
    out through :meth:`connect` instead of toolkit-specific signals.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, dict[int, Callable]] = {}
        self._next_handler_id = 1

    # ------------------------------------------------------------------
    # Event plumbing - a minimal, backend-independent replacement for
    # GObject signals so callers never need to know the concrete widget
    # toolkit a backend is built on.
    # ------------------------------------------------------------------

    def connect(self, event: str, callback: Callable) -> int:
        """Register *callback* for *event*; return a handler id."""
        handler_id = self._next_handler_id
        self._next_handler_id += 1
        self._handlers.setdefault(event, {})[handler_id] = callback
        return handler_id

    def disconnect(self, handler_id: int) -> None:
        """Unregister a handler previously returned by :meth:`connect`."""
        for handlers in self._handlers.values():
            handlers.pop(handler_id, None)

    def _emit(self, event: str, *args) -> None:
        """Call every handler registered for *event*, registration order."""
        for callback in list(self._handlers.get(event, {}).values()):
            callback(*args)

    # ------------------------------------------------------------------
    # Widget embedding
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def widget(self) -> Gtk.Widget:
        """Return the GTK widget to embed in the document page."""

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    @abstractmethod
    def load(self, html: str, mime_type: str, base_uri: str) -> None:
        """Replace the whole document with *html*."""

    def render_incremental(self, body_html: str) -> bool:
        """Patch the current document's ``<body>`` in place, if possible.

        Returns True when the patch was applied and no full :meth:`load`
        is needed, False when the caller must fall back to :meth:`load`.
        The default implementation never supports this optimisation.
        """
        return False

    # ------------------------------------------------------------------
    # Appearance
    # ------------------------------------------------------------------

    @abstractmethod
    def set_background_color(self, hex_color: str) -> None:
        """Set the document's background color (avoids a flash on load)."""

    @abstractmethod
    def set_foreground_color(self, hex_color: str) -> None:
        """Set the document's default text color."""

    @abstractmethod
    def set_fonts(
        self,
        font_family: str,
        font_size_px: int,
        mono_family: str,
        mono_size_px: int,
    ) -> None:
        """Set the default proportional and monospace fonts."""

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------

    @abstractmethod
    def get_scroll_fraction(self) -> float:
        """Return the current scroll position as a 0..1 fraction.

        May block the caller (spinning the main loop) until the backend
        has an answer, matching how callers used this today.
        """

    @abstractmethod
    def scroll_to_fraction(self, fraction: float) -> None:
        """Scroll to a 0..1 fraction of the document height."""

    @abstractmethod
    def scroll_to_anchor(self, anchor: str) -> None:
        """Scroll to the element with id/name *anchor*."""

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @abstractmethod
    def find_next(self, text: str) -> bool:
        """Search forward for *text*; return whether it was found."""

    @abstractmethod
    def find_previous(self, text: str) -> bool:
        """Search backward for *text*; return whether it was found."""

    @abstractmethod
    def stop_search(self) -> None:
        """Clear search highlighting/state."""

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------

    @abstractmethod
    def print_page(self, parent: Gtk.Window) -> None:
        """Run the platform print dialog for the current document."""

    # ------------------------------------------------------------------
    # Optional scripting capability
    # ------------------------------------------------------------------

    def can_run_script(self) -> bool:
        """Return whether :meth:`run_script` is supported.

        Only script-capable backends (WebKit) can back interactive
        features such as JSON folding; callers must check this first and
        degrade gracefully (e.g. render everything already expanded)
        when it returns False.
        """
        return False

    def run_script(self, script: str) -> None:
        """Run *script* in the document's script context.

        Only valid when :meth:`can_run_script` returns True.
        """
        msg = f"{type(self).__name__} does not support scripting"
        raise NotImplementedError(msg)


def create_browser_view() -> BrowserView:
    """Instantiate the :class:`BrowserView` backend to use.

    Reads ``$FORMIKO_BROWSER`` (see :data:`ENV_BACKEND`): unset or
    ``"webkit"`` picks the default :class:`WebKitBrowserView
    <formiko.webkit_browser.WebKitBrowserView>`; ``"litehtml"`` picks the
    experimental :class:`LitehtmlBrowserView
    <formiko.litehtml_browser.LitehtmlBrowserView>` instead, for trying it
    out without committing to it as the default.
    """
    backend = os.environ.get(ENV_BACKEND, "webkit").strip().lower()

    if backend == "litehtml":
        # Imported lazily so choosing this backend never requires WebKit,
        # and vice versa.
        from formiko.litehtml_browser import LitehtmlBrowserView

        return LitehtmlBrowserView()

    if backend not in ("webkit", ""):
        logger.warning(
            "Unknown %s=%r, falling back to the webkit backend",
            ENV_BACKEND,
            backend,
        )

    from formiko.webkit_browser import WebKitBrowserView

    return WebKitBrowserView()
