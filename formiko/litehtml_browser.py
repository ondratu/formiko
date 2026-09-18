"""Experimental litehtml backend for :class:`formiko.browser.BrowserView`.

Enabled by setting ``FORMIKO_BROWSER=litehtml`` (see
:func:`formiko.browser.create_browser_view`). A first spike, not a
feature-complete replacement for the WebKit backend:

- No JavaScript - JSON folding always renders fully expanded.
- No incremental re-render - every change does a full reload.
- Printing: not implemented, degrades gracefully.
- In-page search: whole-text-node granularity, rebuilt on every render.
- Text selection: whole-text-node granularity (litehtml has no
  character-level hit-testing); copy with Ctrl+C.
- Images: ``<img>``, ``background-image``, ``list-style-image`` all
  work, local and http(s); ``border-image`` doesn't (litehtml itself
  doesn't implement it).

Requires the third-party ``litehtmlpy`` package, not published on PyPI -
must be built from source. This module raises a clear ``ImportError`` if
it's missing; the default WebKit backend is unaffected either way.

Also depends on patches merged into upstream litehtmlpy via
https://github.com/m32/litehtmlpy/pull/3. An older, unpatched build still
mostly works (worse font rendering, no hover status, no search/selection,
slower rendering); the exception is the ``on_mouse_event`` fix, whose
absence is guarded against in :meth:`LitehtmlBrowserView._on_click`
instead of crashing.
"""

from __future__ import annotations

import ctypes
import io
import logging
import sys
import urllib.request
import warnings
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urljoin

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

try:
    import cairo
    from litehtmlpy import litehtmlpango as _lhpango
    from litehtmlpy import litehtmlpy as _lh
except ImportError as error:
    msg = (
        "The litehtml backend requires the third-party 'litehtmlpy' "
        "package (with pycairo), which is not on PyPI and must be built "
        "from source: see https://github.com/m32/litehtmlpy. Install it "
        "into this environment, or unset FORMIKO_BROWSER to use the "
        "default WebKit backend."
    )
    raise ImportError(msg) from error

from formiko.browser import (
    EVENT_HOVER_CHANGED,
    EVENT_LINK_CLICKED,
    EVENT_LOAD_FINISHED,
    EVENT_USER_SCROLLED,
    BrowserView,
    HoverTarget,
)
from formiko.widgets import ScrollDriftGuard

logger = logging.getLogger(__name__)

#: Rendering width used before the widget has been allocated a real size.
_DEFAULT_WIDTH = 800

#: Pointer movement (px) beyond which a press+release counts as a text
#: selection drag instead of a link click.
_DRAG_THRESHOLD = 4

#: Idle time after a scroll before it's reported as "user activity",
#: matching webkit_browser.py's own JS scroll listener.
_SCROLL_ACTIVITY_DEBOUNCE_MS = 500

#: A highlightable region in document (CSS px) coordinates: (x, y, w, h).
Box = tuple[float, float, float, float]

#: Background downloads for http(s) <img> sources; a small pool since a
#: single document rarely embeds more than a handful of remote images.
_IMAGE_EXECUTOR = ThreadPoolExecutor(max_workers=4)
_HTTP_TIMEOUT = 10  # seconds

if sys.platform == "win32":
    _CAIRO_SONAME = "libcairo-2.dll"
elif sys.platform == "darwin":
    _CAIRO_SONAME = "libcairo.2.dylib"
else:
    _CAIRO_SONAME = "libcairo.so.2"

_libcairo = ctypes.CDLL(_CAIRO_SONAME)
_libcairo.cairo_scale.argtypes = (
    ctypes.c_void_p,
    ctypes.c_double,
    ctypes.c_double,
)
_libcairo.cairo_scale.restype = None


def _cairo_scale(cairo_t_addr: int, sx: float, sy: float) -> None:
    """Call libcairo's ``cairo_scale()`` on a raw ``cairo_t*`` address.

    litehtmlpy exposes its internal Cairo context only as a plain
    ``uintptr_t`` int (litehtml's ``uint_ptr``), so there is no pycairo
    object to call ``.scale()`` on - this reaches straight into libcairo
    instead, which is already loaded in-process via ``import cairo``.
    """
    _libcairo.cairo_scale(ctypes.c_void_p(cairo_t_addr), sx, sy)


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert ``#rrggbb`` to a (r, g, b) tuple of floats in 0..1."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return r, g, b


def _gtk_dpi() -> int:
    """Return the desktop's font DPI from ``Gtk.Settings``.

    ``gtk-xft-dpi`` is stored in 1024ths (e.g. 96 dpi -> 98304); falls
    back to 96 when unset (-1) or the settings object is unavailable.
    """
    settings = Gtk.Settings.get_default()
    if settings is None:
        return 96
    raw = settings.get_property("gtk-xft-dpi")
    return raw // 1024 if raw and raw > 0 else 96


def _gtk_font_options() -> tuple[int, int, int] | None:
    """Read the desktop's font antialiasing/hinting settings from GTK.

    Returns ``(antialias, hint_style, subpixel_order)`` as the plain
    ``cairo_*_t`` enum ints litehtmlpy's (patched) ``set_font_options``
    expects, or None if ``Gtk.Settings`` isn't available.

    Antialiasing is deliberately capped at grayscale, never subpixel/LCD:
    subpixel-rendered glyphs only look correct when composited straight
    onto the exact opaque background they were drawn against. This
    backend renders into its own offscreen surface, round-trips it
    through PNG (which preserves alpha), and only then paints it over
    our background color - subpixel AA through that pipeline produces
    colored fringes around every glyph instead of clean text.
    """
    settings = Gtk.Settings.get_default()
    if settings is None:
        return None

    xft_antialias = settings.get_property("gtk-xft-antialias")
    xft_hinting = settings.get_property("gtk-xft-hinting")
    hintstyle = settings.get_property("gtk-xft-hintstyle") or ""

    antialias = (
        cairo.ANTIALIAS_NONE if xft_antialias == 0 else cairo.ANTIALIAS_GRAY
    )

    if xft_hinting == 0:
        hint_style = cairo.HINT_STYLE_NONE
    else:
        hint_style = {
            "hintnone": cairo.HINT_STYLE_NONE,
            "hintslight": cairo.HINT_STYLE_SLIGHT,
            "hintmedium": cairo.HINT_STYLE_MEDIUM,
            "hintfull": cairo.HINT_STYLE_FULL,
        }.get(hintstyle, cairo.HINT_STYLE_DEFAULT)

    return int(antialias), int(hint_style), int(cairo.SUBPIXEL_ORDER_DEFAULT)


def _find_link_href(el) -> str | None:
    """Walk up from *el* to the nearest ``<a href>``, *el* included.

    The element litehtml hit-tests is often an inline descendant of the
    link (e.g. a ``<b>`` inside the ``<a>``), not the link itself, and
    litehtmlpy's ``element`` has no selector API to jump straight to it.
    """
    node = el
    while node is not None:
        if node.get_tagName() == "a":
            href = node.get_attr("href", None)
            if href:
                return href
        node = node.parent()
    return None


def _find_element_by_anchor(el, anchor: str):
    """Depth-first search for an ``id``/(legacy) ``name`` match, *el* included.

    litehtmlpy exposes the DOM tree (``element.children()``) but no
    selector API, so a plain HTML/CSS-style ``#id`` lookup has to walk
    it by hand.
    """
    if el is None:
        return None
    if anchor in (el.get_attr("id", None), el.get_attr("name", None)):
        return el
    for child in el.children():
        found = _find_element_by_anchor(child, anchor)
        if found is not None:
            return found
    return None


def _collect_selection(
    el, x0: float, y0: float, x1: float, y1: float,
) -> tuple[list[tuple[float, float, float, float]], str]:
    """Find text nodes overlapping the box (*x0*, *y0*)-(*x1*, *y1*).

    litehtml has no selection or hit-testing-to-text-offset API at all,
    so this only works at whole-text-node granularity (each run of text
    between tags, e.g. one word or one sentence) - not per character
    like a real browser. Returns (boxes to highlight, joined text in
    document order).
    """
    boxes: list[tuple[float, float, float, float]] = []
    parts: list[str] = []

    def walk(node) -> None:
        if node is None:
            return
        if node.is_text():
            pos = node.get_placement()
            ex0, ey0 = pos.x.value, pos.y.value
            ex1, ey1 = ex0 + pos.width.value, ey0 + pos.height.value
            if ex0 < x1 and ex1 > x0 and ey0 < y1 and ey1 > y0:
                boxes.append((ex0, ey0, pos.width.value, pos.height.value))
                text = node.get_text().strip()
                if text:
                    parts.append(text)
            return  # text nodes have no children of their own
        for child in node.children():
            walk(child)

    walk(el)
    return boxes, " ".join(parts)


def _build_text_index(el) -> tuple[str, list[tuple[int, int, Box]]]:
    """Flatten *el*'s text nodes into one string plus a span per node.

    litehtml already splits inline text into one node per word/run of
    whitespace (see the module docstring), so concatenating their
    ``get_text()`` values in document order - without inserting any
    separators of our own - reconstructs the visible text with its
    original spacing. Each span is ``(start, end, box)`` into that
    string, letting a match's character range be mapped back to the
    node box(es) to highlight.
    """
    parts: list[str] = []
    spans: list[tuple[int, int, Box]] = []
    offset = 0

    def walk(node) -> None:
        nonlocal offset
        if node is None:
            return
        if node.is_text():
            text = node.get_text()
            if text:
                pos = node.get_placement()
                box = (
                    pos.x.value,
                    pos.y.value,
                    pos.width.value,
                    pos.height.value,
                )
                spans.append((offset, offset + len(text), box))
                parts.append(text)
                offset += len(text)
            return
        for child in node.children():
            walk(child)

    walk(el)
    return "".join(parts), spans


def _find_all_matches(
    full_text: str, spans: list[tuple[int, int, Box]], query: str,
) -> list[list[Box]]:
    """Return the boxes to highlight for each non-overlapping match.

    Case-insensitive substring search over *full_text*; a match's boxes
    are every span it overlaps, so a query spanning more than one text
    node (e.g. two words) highlights all of them.
    """
    if not query:
        return []
    haystack = full_text.lower()
    needle = query.lower()
    matches: list[list[Box]] = []
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            break
        end = index + len(needle)
        boxes = [box for s, e, box in spans if s < end and e > index]
        matches.append(boxes)
        start = end
    return matches


def _pixbuf_to_surface(pixbuf: GdkPixbuf.Pixbuf) -> cairo.ImageSurface:
    """Convert *pixbuf* to a premultiplied Cairo ARGB32 surface.

    ``Gdk.cairo_set_source_pixbuf`` does the RGB(A)-to-premultiplied-BGRA
    conversion natively in C (it's what GTK itself uses to paint pixbufs)
    - deprecated in GTK4 but still present and working, and ~30x faster
    than doing the same conversion by hand in a Python per-pixel loop
    (confirmed: ~9ms vs ~290ms for one 1600x1000 image).
    """
    width, height = pixbuf.get_width(), pixbuf.get_height()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surface)
    with warnings.catch_warnings():
        # Deprecated in GTK4 (no replacement offered) but still present
        # and correct; this runs once per image, so don't let the
        # warning spam logs on every render.
        warnings.simplefilter("ignore", DeprecationWarning)
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
    cr.paint()
    return surface


def _decode_image_to_surface(
    data: bytes | None, path: str | None,
) -> cairo.ImageSurface | None:
    """Decode an image (from *data* bytes, or *path* on disk) to Cairo ARGB32.

    PNG - identified by magic bytes or extension - decodes straight
    through Cairo's own C decoder, which already produces premultiplied
    ARGB32 (exactly what ``put_image()`` needs). Every other format
    GdkPixbuf can load (JPEG, GIF, WebP, ...) goes through
    :func:`_pixbuf_to_surface` instead, equally native-speed.
    """
    is_png = (data is not None and data[:8] == b"\x89PNG\r\n\x1a\n") or (
        path is not None and path.lower().endswith(".png")
    )
    if is_png:
        try:
            return cairo.ImageSurface.create_from_png(
                io.BytesIO(data) if data is not None else path,
            )
        except (cairo.Error, OSError):
            logger.debug(
                "litehtml: PNG fast path failed for %s, falling back to"
                " GdkPixbuf",
                path or "<remote>",
            )

    if data is not None:
        loader = GdkPixbuf.PixbufLoader()
        loader.write(data)
        loader.close()
        pixbuf = loader.get_pixbuf()
    else:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
    if pixbuf is None:
        return None
    return _pixbuf_to_surface(pixbuf)


class _Container(_lhpango.document_container):
    """litehtml document_container wired back into a LitehtmlBrowserView."""

    def __init__(self, owner: LitehtmlBrowserView) -> None:
        super().__init__(parent=None)
        self._owner = owner
        # Every re-render calls fromString() fresh, whose <img> parsing
        # calls load_image() again unconditionally regardless of whether
        # litehtmlpy's own image cache already has it - without this,
        # a successful fetch's queue_draw() triggers another render pass,
        # which re-fetches the same URL, which redraws again, forever.
        self._fetched_urls: set[str] = set()
        self.set_dpi(_gtk_dpi())

        # set_font_options() only exists on a litehtmlpy build patched to
        # expose container_cairo_pango::get_font_options() to Python (the
        # upstream default hardcodes it to return nullptr, so Cairo/Pango
        # fall back to generic AA/hinting instead of the desktop's actual
        # Xft/fontconfig settings - see the module docstring).
        font_options = _gtk_font_options()
        if font_options is not None and hasattr(self, "set_font_options"):
            self.set_font_options(*font_options)

    def load_image(self, src, baseurl, redraw_on_ready) -> None:
        """Load an image, local or http(s).

        litehtml core calls this same container hook for ``<img src>``,
        CSS ``background-image`` and ``list-style-image`` alike (see
        ``el_image.cpp``/``css_properties.cpp``), so all three work with
        no extra code here. ``border-image`` isn't a litehtml limitation
        we hit - the engine doesn't implement that CSS property at all.

        ``put_image()`` must be keyed by the raw, unresolved *src* -
        that's what a later ``get_image()`` lookup during layout/draw
        uses, since ``container_cairo::make_url()`` (not overridable
        from Python) is a plain passthrough that ignores the base path;
        *src* is only resolved against *baseurl* here to find the file
        or URL.
        """
        del redraw_on_ready  # we always queue_draw() once the image lands
        base = baseurl or self._owner._base_uri  # noqa: SLF001
        resolved = urljoin(base, src) if base else src

        if resolved.startswith(("http://", "https://")):
            if resolved not in self._fetched_urls:
                self._fetched_urls.add(resolved)
                _IMAGE_EXECUTOR.submit(
                    self._fetch_remote_image, src, resolved,
                )
            return

        if not resolved.startswith("file://"):
            return  # unsupported scheme (data:, ...)
        path = unquote(resolved[len("file://"):])
        try:
            surface = _decode_image_to_surface(None, path)
        except (GLib.Error, OSError):
            logger.warning("litehtml: could not load image %r", path)
            return
        if surface is None:
            return
        self.put_image(
            src,
            bytearray(surface.get_data()),
            surface.get_width(),
            surface.get_height(),
        )

    def _fetch_remote_image(self, src: str, url: str) -> None:
        """Download and decode *url* on a worker thread.

        Runs off the GTK main thread (network I/O plus decoding a
        possibly large image shouldn't block rendering); hands the
        result back to :meth:`_apply_remote_image` via ``GLib.idle_add``
        since litehtmlpy/GTK objects must only be touched from the main
        thread.
        """
        if not url.startswith(("http://", "https://")):
            return  # belt-and-suspenders: load_image() already checked
        headers = {"User-Agent": "formiko"}
        request = urllib.request.Request(url, headers=headers)  # noqa: S310
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=_HTTP_TIMEOUT,
            ) as resp:
                raw = resp.read()
        except (OSError, ValueError) as error:
            logger.warning(
                "litehtml: could not fetch image %r: %s", url, error,
            )
            self._fetched_urls.discard(url)  # let a later render retry
            return

        try:
            surface = _decode_image_to_surface(raw, None)
        except (GLib.Error, OSError) as error:
            logger.warning(
                "litehtml: could not decode image %r: %s", url, error,
            )
            self._fetched_urls.discard(url)
            return
        if surface is None:
            self._fetched_urls.discard(url)
            return
        GLib.idle_add(
            self._apply_remote_image,
            src,
            bytearray(surface.get_data()),
            surface.get_width(),
            surface.get_height(),
        )

    def _apply_remote_image(
        self, src: str, data, width: int, height: int,
    ) -> bool:
        """Register a downloaded image and repaint now that it exists."""
        self.put_image(src, data, width, height)
        self._owner._rendered_width = -1  # noqa: SLF001
        self._owner._area.queue_draw()  # noqa: SLF001
        return GLib.SOURCE_REMOVE

    def on_anchor_click(self, url, _el) -> None:
        """Report a link click to the owning :class:`LitehtmlBrowserView`.

        litehtml hands us the raw ``href`` attribute, not resolved
        against the document's URL the way WebKit's navigation events
        are - a bare relative link would otherwise reach ``Gtk.show_uri``
        as-is and fail to open.
        """
        resolved = urljoin(self._owner._base_uri, url)  # noqa: SLF001
        self._owner._emit(EVENT_LINK_CLICKED, resolved)  # noqa: SLF001

    def set_base_url(self, url) -> None:
        """Track a ``<base href>`` override for :meth:`on_anchor_click`."""
        if url:
            self._owner._base_uri = url  # noqa: SLF001

    def on_mouse_event(self, el, event) -> None:
        """Report link hover, mirroring the WebKit backend's status text.

        Fires on entering/leaving whichever element litehtml currently
        considers hovered; ``el`` is None or not a link on plain
        ``mouse_event_leave``, so the default branch below always clears
        the target in that case.
        """
        if event == _lh.mouse_event.mouse_event_enter and el is not None:
            href = _find_link_href(el)
            if href:
                resolved = urljoin(self._owner._base_uri, href)  # noqa: SLF001
                target = HoverTarget("link", resolved)
                self._owner._emit(EVENT_HOVER_CHANGED, target)  # noqa: SLF001
                return
        self._owner._emit(EVENT_HOVER_CHANGED, None)  # noqa: SLF001

    def set_cursor(self, cursor: str) -> None:
        """Apply the CSS cursor litehtml computed for the hovered element.

        litehtml passes the element's resolved CSS ``cursor`` value (e.g.
        ``"pointer"`` for links, via its built-in ``a:link`` rule).
        Non-link text normally resolves to the CSS-spec default value
        ``"auto"``, and elements outside the document give ``""``;
        neither is a real GDK cursor name (an unrecognized name falls
        back to a mismatched/oversized glyph instead of erroring), so
        both are normalized to the universally supported ``"default"``.
        """
        name = cursor if cursor and cursor != "auto" else "default"
        gdk_cursor = Gdk.Cursor.new_from_name(name, None)
        self._owner._area.set_cursor(gdk_cursor)  # noqa: SLF001


class LitehtmlBrowserView(BrowserView):
    """Browser backend based on litehtml, rendered via Cairo/Pango."""

    def __init__(self) -> None:
        super().__init__()
        self._html = ""
        self._base_uri = ""
        self._bgcolor = "#ffffff"
        self._rendered_width = -1
        self._rendered_scale = -1
        # Set by load(), cleared by _render_at_width: tells a genuine
        # content reload apart from a resize/DPI-only re-render.
        self._html_changed = True
        # Set by load(); cleared once that content is actually rendered
        # (see _render_at_width) and only then reported as loaded.
        self._pending_load_notify = True
        self._doc_height = 1
        self._surface: cairo.ImageSurface | None = None
        self._doc = None  # last rendered litehtml document, for hit-testing
        self._drag_start: tuple[float, float] | None = None
        # Scroll position when the current gesture began, so a stationary
        # click can't be misread as a long drag just because the page
        # itself kept scrolling underneath it (see _genuine_offset()).
        self._drag_start_scroll: tuple[float, float] | None = None
        self._selection_boxes: list[tuple[float, float, float, float]] = []
        self._selection_text = ""
        # Flattened text of the current document plus a (start, end, box)
        # span per text node, lazily (re)built by _ensure_text_index()
        # the first time a search actually runs against a given document.
        self._full_text = ""
        self._text_spans: list[tuple[int, int, Box]] = []
        self._text_index_doc = None  # which self._doc the above match
        self._search_text = ""
        self._search_matches: list[list[Box]] = []
        self._search_index = -1
        self._container = _Container(self)

        self._area = Gtk.DrawingArea()
        self._area.set_draw_func(self._on_draw)
        self._area.set_focusable(True)

        # A single click has to both open links (on_lbutton_down/up) and
        # start a text selection - litehtml has no selection concept of
        # its own, so a GestureDrag distinguishes the two by distance:
        # dragging past _DRAG_THRESHOLD selects text instead of clicking.
        drag = Gtk.GestureDrag.new()
        drag.set_button(Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self._area.add_controller(drag)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_motion_leave)
        self._area.add_controller(motion)

        key = Gtk.EventControllerKey.new()
        key.connect("key-pressed", self._on_key_pressed)
        self._area.add_controller(key)

        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_child(self._area)
        # Kinetic scrolling (momentum + elastic overscroll bounce) drifts
        # the scroll position on its own well after the user's scroll
        # gesture ends, with no further input - that's what fooled clicks
        # into misreading themselves as long drags (see _genuine_offset())
        # and it's also just a distracting drift on a document preview
        # that isn't a touch-scrolled view. Direct wheel/scrollbar input
        # still scrolls normally with this off.
        self._scrolled.set_kinetic_scrolling(False)
        # GTK moves this scroll position on its own for unrelated reasons
        # too, e.g. around tab switches - see ScrollDriftGuard.
        self._scroll_guard = ScrollDriftGuard(
            self._area, self._scrolled.get_vadjustment(),
        )
        # Reports scrolling as WakaTime activity, like webkit_browser.py.
        self._scroll_activity_source = 0
        self._scrolled.get_vadjustment().connect(
            "value-changed", self._on_scroll_activity,
        )

    # ------------------------------------------------------------------
    # BrowserView interface
    # ------------------------------------------------------------------

    @property
    def widget(self) -> Gtk.Widget:
        """Return the scrolled drawing area used to paint the document."""
        return self._scrolled

    def load(self, html: str, mime_type: str, base_uri: str) -> None:
        """Replace the whole document with *html*.

        ``mime_type`` is unused: litehtml only ever renders HTML here.
        ``base_uri`` resolves relative ``href``s in
        :meth:`_Container.on_anchor_click` and relative image sources in
        :meth:`_Container.load_image`.
        """
        del mime_type
        self._html = html
        self._base_uri = base_uri
        self._rendered_width = -1  # force a re-render at the next draw
        self._html_changed = True  # see _render_at_width
        self._selection_boxes = []
        self._selection_text = ""
        # A reload can land mid-gesture (e.g. live-preview re-render while
        # the mouse button is still down over the preview): self._doc and
        # the current scroll position are about to change from under the
        # gesture, so drop it rather than let _on_drag_update/_on_drag_end
        # act on stale (x, y) against the new document - that's what made
        # a click on one link turn into a text selection somewhere else
        # entirely, with the view jumping underneath it.
        self._drag_start = None
        self._drag_start_scroll = None
        # Notified from _render_at_width, not here: EVENT_LOAD_FINISHED
        # drives a scroll restore that needs this content's layout ready.
        self._pending_load_notify = True
        self._area.queue_draw()

    def set_background_color(self, hex_color: str) -> None:
        """Set the color painted behind the rendered document."""
        self._bgcolor = hex_color
        self._area.queue_draw()

    def set_foreground_color(self, hex_color: str) -> None:
        """No-op: text color comes from the ``<style>`` Renderer embeds."""

    def set_fonts(
        self,
        font_family: str,
        font_size_px: int,
        mono_family: str,
        mono_size_px: int,
    ) -> None:
        """Not wired up yet; litehtmlpango uses its own Pango defaults."""
        del font_family, font_size_px, mono_family, mono_size_px

    def get_scroll_fraction(self) -> float:
        """Return the current scroll position as a 0..1 fraction."""
        vadj = self._scrolled.get_vadjustment()
        span = vadj.get_upper() - vadj.get_page_size()
        return vadj.get_value() / span if span > 0 else 0.0

    def scroll_to_fraction(self, fraction: float) -> None:
        """Scroll to a 0..1 fraction of the document height."""
        vadj = self._scrolled.get_vadjustment()
        span = vadj.get_upper() - vadj.get_page_size()
        self._scroll_guard.apply(max(0.0, span) * fraction)

    def scroll_to_anchor(self, anchor: str) -> None:
        """Scroll to the element with id/name *anchor*, if found."""
        if self._doc is None:
            return
        el = _find_element_by_anchor(self._doc.root(), anchor)
        if el is None:
            logger.debug("scroll_to_anchor(%s): no such id/name", anchor)
            return
        y = el.get_placement().y.value
        vadj = self._scrolled.get_vadjustment()
        top = max(0.0, vadj.get_upper() - vadj.get_page_size())
        self._scroll_guard.apply(min(y, top))

    def find_next(self, text: str) -> bool:
        """Search forward for *text*, wrapping around; highlight + scroll."""
        return self._search(text, step=1)

    def find_previous(self, text: str) -> bool:
        """Search backward for *text*, wrapping around; highlight + scroll."""
        return self._search(text, step=-1)

    def stop_search(self) -> None:
        """Clear search highlighting."""
        self._search_text = ""
        self._search_matches = []
        self._search_index = -1
        self._area.queue_draw()

    def print_page(self, parent: Gtk.Window) -> None:
        """Tell the user printing isn't implemented for this backend yet."""
        dialog = Gtk.AlertDialog.new(
            "Printing isn't implemented yet for the litehtml backend.",
        )
        dialog.show(parent)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _notify_load_finished(self) -> bool:
        self._emit(EVENT_LOAD_FINISHED)
        return False

    def _ensure_text_index(self) -> None:
        """(Re)build the flattened search text for the current document.

        A full DOM walk, so it's only done here - the first time a
        search actually needs it - rather than on every render.
        """
        if self._text_index_doc is self._doc:
            return
        self._text_index_doc = self._doc
        if self._doc is None:
            self._full_text, self._text_spans = "", []
        else:
            self._full_text, self._text_spans = _build_text_index(
                self._doc.root(),
            )

    def _reapply_search(self) -> None:
        """Recompute the active search's match boxes for the new layout.

        Keeps the current match selected (clamped) rather than resetting.
        """
        if not self._search_text:
            return
        self._ensure_text_index()
        self._search_matches = _find_all_matches(
            self._full_text, self._text_spans, self._search_text,
        )
        if self._search_matches:
            self._search_index = min(
                max(self._search_index, 0), len(self._search_matches) - 1,
            )
        else:
            self._search_index = -1

    def _search(self, text: str, step: int) -> bool:
        """Move to the next/previous (*step*) match of *text* and scroll."""
        if text != self._search_text:
            self._ensure_text_index()
            self._search_text = text
            self._search_matches = _find_all_matches(
                self._full_text, self._text_spans, text,
            )
            self._search_index = -1
        if not self._search_matches:
            return False
        count = len(self._search_matches)
        self._search_index = (self._search_index + step) % count
        self._scroll_to_match(self._search_matches[self._search_index])
        self._area.queue_draw()
        return True

    def _scroll_to_match(self, boxes: list[Box]) -> None:
        """Scroll so the topmost box of a match is comfortably visible."""
        if not boxes:
            return
        y = min(box[1] for box in boxes)
        vadj = self._scrolled.get_vadjustment()
        top = max(0.0, vadj.get_upper() - vadj.get_page_size())
        target = max(0.0, y - vadj.get_page_size() / 3)
        vadj.set_value(min(target, top))

    def _render_at_width(self, width: int, scale: int) -> None:
        """Render ``self._html`` at *width* CSS px into ``self._surface``.

        The layout itself always happens at the logical *width* so page
        flow matches what's on screen; *scale* only controls how many
        raster pixels get sampled per CSS pixel (the display's device
        scale factor), via a ``cairo_scale()`` applied to litehtml's
        drawing surface before it paints anything. Skipping this and
        rasterizing 1:1 would make GTK upscale a too-small bitmap on any
        HiDPI (scale > 1) output, which is what made text look blurry.
        """
        self._container.size = _lh.size(width, 1)
        doc = self._container.fromString(self._html, None, None)
        self._doc = doc  # kept for click/selection hit-testing
        doc.render(_lh.pixel_float_t(width), _lh.render_all)
        # A content reload drops an active search; a resize/DPI-only
        # re-render just needs its highlight boxes recomputed instead.
        if self._html_changed:
            self._html_changed = False
            self._search_text = ""
            self._search_matches = []
            self._search_index = -1
        else:
            self._reapply_search()
        doc_width = max(1, int(doc.width().value))
        doc_height = max(1, int(doc.height().value))
        hdc = self._container.surface(doc_width * scale, doc_height * scale)
        if scale != 1:
            _cairo_scale(hdc, scale, scale)
        clip = _lh.position(0, 0, doc_width, doc_height)
        doc.draw(hdc, _lh.pixel_float_t(0), _lh.pixel_float_t(0), clip)

        surface = self._extract_surface(doc_width * scale, doc_height * scale)
        surface.set_device_scale(scale, scale)
        self._surface = surface
        self._rendered_width = width
        self._rendered_scale = scale
        if doc_height != self._doc_height:
            self._doc_height = doc_height
            self._area.set_content_height(doc_height)
        if self._pending_load_notify:  # now that layout is ready
            self._pending_load_notify = False
            GLib.idle_add(self._notify_load_finished)

    def _extract_surface(
        self, pixel_width: int, pixel_height: int,
    ) -> cairo.ImageSurface:
        """Get the just-drawn page as a ``cairo.ImageSurface``.

        Zero-copy on a litehtmlpy build with the ``get_data()`` patch:
        wraps litehtml's own ARGB32 buffer directly (valid only until the
        next ``surface()`` call, which is fine since we always rebuild
        ``self._surface`` right alongside it). Falls back to a PNG
        encode/decode round trip - slower, but keeps this backend usable
        against a plain upstream build.
        """
        if hasattr(self._container, "get_data"):
            stride = cairo.ImageSurface.format_stride_for_width(
                cairo.FORMAT_ARGB32, pixel_width,
            )
            return cairo.ImageSurface.create_for_data(
                self._container.get_data(),
                cairo.FORMAT_ARGB32,
                pixel_width,
                pixel_height,
                stride,
            )
        png_bytes = io.BytesIO()
        self._container.savestream(png_bytes.write)
        png_bytes.seek(0)
        return cairo.ImageSurface.create_from_png(png_bytes)

    def _on_draw(self, area, cr, width, _height) -> None:
        width = width or _DEFAULT_WIDTH
        scale = area.get_scale_factor() or 1
        if width != self._rendered_width or scale != self._rendered_scale:
            try:
                self._render_at_width(width, scale)
            except Exception:
                logger.exception("litehtml render failed")
                # Mark as attempted so unrelated redraws don't retry (and
                # re-log) forever; a real width/scale change still will.
                self._rendered_width = width
                self._rendered_scale = scale
                return
        r, g, b = _hex_to_rgb(self._bgcolor)
        cr.set_source_rgb(r, g, b)
        cr.paint()
        if self._surface is not None:
            cr.set_source_surface(self._surface, 0, 0)
            cr.paint()
        self._draw_selection(cr)
        self._draw_search_matches(cr)

    def _draw_selection(self, cr) -> None:
        if not self._selection_boxes:
            return
        cr.set_source_rgba(0.2, 0.4, 1.0, 0.35)
        for x, y, w, h in self._selection_boxes:
            cr.rectangle(x, y, w, h)
        cr.fill()

    def _draw_search_matches(self, cr) -> None:
        if not self._search_matches:
            return
        cr.set_source_rgba(1.0, 1.0, 0.0, 0.35)
        for boxes in self._search_matches:
            for x, y, w, h in boxes:
                cr.rectangle(x, y, w, h)
        cr.fill()
        if 0 <= self._search_index < len(self._search_matches):
            cr.set_source_rgba(1.0, 0.55, 0.0, 0.6)
            for x, y, w, h in self._search_matches[self._search_index]:
                cr.rectangle(x, y, w, h)
            cr.fill()

    def _on_click(self, x: float, y: float) -> None:
        """Forward a left-button press+release to litehtml for hit-testing.

        x/y from GTK are already in the drawing area's logical (CSS px)
        coordinates - the same space litehtml laid the document out in,
        so no scale conversion is needed here, only the device-pixel
        raster in :meth:`_render_at_width` cares about the scale factor.
        litehtml itself decides whether the click landed on a link and,
        if so, calls :meth:`_Container.on_anchor_click` - we never
        inspect boxes or URLs ourselves.
        """
        if self._doc is None:
            return
        try:
            self._doc.on_lbutton_down(int(x), int(y), int(x), int(y))
            self._doc.on_lbutton_up(int(x), int(y), int(x), int(y))
        except RuntimeError:
            # Unpatched litehtmlpy (see module docstring) raises here on
            # every click - degrade instead of crashing the handler.
            logger.exception("litehtml: on_lbutton_down/up failed")

    def _scroll_offsets(self) -> tuple[float, float]:
        """Return the current (horizontal, vertical) scroll position."""
        return (
            self._scrolled.get_hadjustment().get_value(),
            self._scrolled.get_vadjustment().get_value(),
        )

    def _genuine_offset(
        self, offset_x: float, offset_y: float,
    ) -> tuple[float, float]:
        """Strip scroll drift out of a ``GestureDrag`` offset.

        ``self._area`` spans the full document height, so GTK's reported
        drag offset is (genuine pointer movement) + (however much the
        scroll position itself moved meanwhile, normally 0 - see
        ``set_kinetic_scrolling(False)`` in ``__init__`` for why that
        isn't always true). Subtracting the latter isolates the
        pointer's actual movement, which is what the click-vs-drag
        decision (``_DRAG_THRESHOLD``) should be based on.
        """
        if self._drag_start_scroll is None:
            return offset_x, offset_y
        start_h, start_v = self._drag_start_scroll
        cur_h, cur_v = self._scroll_offsets()
        return offset_x - (cur_h - start_h), offset_y - (cur_v - start_v)

    def _on_drag_begin(self, gesture, x: float, y: float) -> None:
        """Start tracking a possible click-or-select gesture.

        Clears any existing selection immediately, matching how a plain
        click elsewhere clears text selection in a real browser; if this
        turns into a drag, :meth:`_on_drag_update` repopulates it.
        """
        self._area.grab_focus()
        self._drag_start = (x, y)
        self._drag_start_scroll = self._scroll_offsets()
        if self._selection_boxes:
            self._selection_boxes = []
            self._selection_text = ""
            self._area.queue_draw()
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _on_drag_update(
        self, _gesture, offset_x: float, offset_y: float,
    ) -> None:
        """Live-update the text selection while the pointer is dragged."""
        if self._drag_start is None or self._doc is None:
            return
        genuine_x, genuine_y = self._genuine_offset(offset_x, offset_y)
        if max(abs(genuine_x), abs(genuine_y)) < _DRAG_THRESHOLD:
            return
        sx, sy = self._drag_start
        x0, x1 = sorted((sx, sx + offset_x))
        y0, y1 = sorted((sy, sy + offset_y))
        boxes, text = _collect_selection(self._doc.root(), x0, y0, x1, y1)
        self._selection_boxes = boxes
        self._selection_text = text
        self._area.queue_draw()

    def _on_drag_end(self, _gesture, offset_x: float, offset_y: float) -> None:
        """Finish the gesture: a small drag is a click, not a selection."""
        if self._drag_start is None:
            return
        sx, sy = self._drag_start
        genuine_x, genuine_y = self._genuine_offset(offset_x, offset_y)
        self._drag_start = None
        self._drag_start_scroll = None
        if max(abs(genuine_x), abs(genuine_y)) < _DRAG_THRESHOLD:
            self._on_click(sx, sy)

    def _on_key_pressed(self, _controller, keyval, _keycode, state) -> bool:
        """Copy the current text selection to the clipboard on Ctrl+C."""
        is_copy = keyval in (Gdk.KEY_c, Gdk.KEY_C)
        if (
            is_copy
            and state & Gdk.ModifierType.CONTROL_MASK
            and self._selection_text
        ):
            self._area.get_clipboard().set(self._selection_text)
            return True
        return False

    def _on_motion(self, _controller, x, y) -> None:
        """Forward pointer motion so litehtml can update ``:hover``/cursor.

        Drives :meth:`_Container.set_cursor` (e.g. a hand cursor over
        links) via the same ``on_mouse_over`` litehtml uses internally to
        track hover state - see document.cpp's ``m_over_element``.
        """
        if self._doc is not None:
            self._doc.on_mouse_over(int(x), int(y), int(x), int(y))

    def _on_motion_leave(self, _controller) -> None:
        """Reset hover state and cursor once the pointer leaves the area."""
        if self._doc is not None:
            self._doc.on_mouse_leave()
        self._area.set_cursor(None)

    def _on_scroll_activity(self, _adj) -> None:
        """Debounce scroll position changes into one EVENT_USER_SCROLLED.

        See ``_SCROLL_ACTIVITY_DEBOUNCE_MS``.
        """
        if self._scroll_activity_source:
            GLib.source_remove(self._scroll_activity_source)
        self._scroll_activity_source = GLib.timeout_add(
            _SCROLL_ACTIVITY_DEBOUNCE_MS, self._emit_scroll_activity,
        )

    def _emit_scroll_activity(self) -> bool:
        self._scroll_activity_source = 0
        self._emit(EVENT_USER_SCROLLED)
        return GLib.SOURCE_REMOVE
