"""HTML preview renderer, backend-independent via :mod:`formiko.browser`."""

from importlib.util import find_spec
from io import StringIO
from os.path import exists, splitext
from traceback import format_exc
from urllib.parse import unquote

from docutils import DataError
from docutils.core import publish_string
from docutils.parsers.rst import Parser as RstParser
from docutils.writers.html4css1 import Writer as Writer4css1
from docutils.writers.html5_polyglot import Writer as Html5Writer
from docutils.writers.pep_html import Writer as WriterPep
from docutils.writers.s5_html import Writer as WriterS5
from gi.repository import Adw, Gdk, Gio, GObject, Gtk, Pango
from gi.repository.GLib import (
    get_home_dir,
    idle_add,
)
from gi.repository.Gtk import (
    Align,
    Label,
    Overlay,
)

from formiko.browser import (
    EVENT_HOVER_CHANGED,
    EVENT_LINK_CLICKED,
    EVENT_LOAD_FINISHED,
    EVENT_USER_SCROLLED,
    create_browser_view,
)
from formiko.dialogs import FileNotFoundDialog, run_alert_dialog
from formiko.directives import HtmlPreview, Mark2Resturctured, TinyWriter
from formiko.json_preview import JSONPreview
from formiko.mistune_preview import MistunePreview
from formiko.sourceview import LANG_BY_EXT
from formiko.utils import Undefined
from formiko.widgets import ImutableDict

# CSS spec: 1pt = 1/72 inch, 1 CSS pixel = 1/96 inch → 1pt = 96/72 CSS px.
# WebKit font sizes are in CSS pixels; HiDPI scaling is handled internally
# via the device pixel ratio, so this ratio is correct for all resolutions.
_PT_TO_CSS_PX = 96 / 72
_PYGMENTS_AVAILABLE = find_spec("pygments") is not None


def pygments_required(parser):
    """Return whether *parser* uses Docutils syntax highlighting."""
    return parser in ("rst", "m2r")


def _docutils_settings(tab_width, file_name, style):
    """Build Docutils settings while handling optional Pygments."""
    settings = {
        "warning_stream": StringIO(),
        "embed_stylesheet": True,
        "tab_width": tab_width,
        "file_name": file_name,
    }
    if not _PYGMENTS_AVAILABLE:
        settings["syntax_highlight"] = "none"
    if style:
        settings["stylesheet"] = style
        settings["stylesheet_path"] = []
    return settings


class Env:
    """Empty class for env overriding."""

    srcdir = ""


PARSERS = {
    "rst": {
        "key": "rst",
        "title": "Docutils reStructuredText parser",
        "class": RstParser,
        "package": "docutils",
        "url": "http://docutils.sourceforge.net",
    },
    "m2r": {
        "key": "m2r",
        "title": "MarkDown to reStructuredText",
        "class": Mark2Resturctured,
        "url": "https://github.com/crossnox/m2r2",
    },
    "mistune": {
        "key": "mistune",
        "title": "Mistune Markdown",
        "class": MistunePreview,
        "package": "mistune",
        "url": "https://github.com/lepture/mistune",
    },
    "html": {
        "key": "html",
        "title": "HTML preview",
        "class": HtmlPreview,
    },
    "json": {
        "key": "json",
        "title": "JSON preview",
        "class": JSONPreview,
    },
}

EXTS = {
    ".rst": "rst",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
}

#: Parser keys that consume literal Markdown syntax.
MARKDOWN_PARSERS = ("m2r", "mistune")

for _md_key in MARKDOWN_PARSERS:
    if not issubclass(PARSERS[_md_key]["class"], Undefined):
        EXTS[".md"] = _md_key
        break


def resolve_ext_parser(ext, preferred):
    """Return the parser key for *ext*, like :data:`EXTS`.

    For ``.md``, *preferred* wins when it's an available markdown parser,
    so a Mistune/m2r2 choice sticks across files.
    """
    if (
        ext == ".md"
        and preferred in MARKDOWN_PARSERS
        and not issubclass(PARSERS[preferred]["class"], Undefined)
    ):
        return preferred
    return EXTS.get(ext, preferred)


WRITERS = {
    "html4": {
        "key": "html4",
        "title": "Docutils HTML4 writer",
        "class": Writer4css1,
        "package": "docutils",
        "url": "https://www.docutils.org",
    },
    "s5": {
        "key": "s5",
        "title": "Docutils S5/HTML slide show writer",
        "class": WriterS5,
        "package": "docutils",
        "url": "https://www.docutils.org",
    },
    "pep": {
        "key": "pep",
        "title": "Docutils PEP HTML writer",
        "class": WriterPep,
        "package": "docutils",
        "url": "https://www.docutils.org",
    },
    "tiny": {
        "key": "tiny",
        "title": "Tiny HTML writer",
        "class": TinyWriter,
        "package": "docutils-tinyhtmlwriter",
        "url": "https://github.com/ondratu/docutils-tinyhtmlwriter",
    },
    "html5": {
        "key": "html5",
        "title": "HTML 5 writer",
        "class": Html5Writer,
        "package": "docutils",
        "url": "https://www.docutils.org",
    },
}


def component_available(component):
    """Return whether a parser or writer implementation is installed."""
    return not issubclass(component["class"], Undefined)


NOT_FOUND = """
<html>
  <head></head>
  <body>
    <h1>Component {title} Not Found!</h1>
    <p>Component <b>{title}</b> which you want to use is not found.
       See <a href="{url}">{url}</a> for more details and install it
       to system.
    </p>
  </body>
</html>
"""

DATA_ERROR = """
<html>
  <head></head>
  <body>
    <h1>%s Error!</h1>
    <p style="color:red; text-width:weight;">%s</p>
  </body>
</html>
"""

NOT_IMPLEMENTED_ERROR = """
<html>
  <head></head>
  <body>
    <h1>Library Error</h1>
    <p>Sorry about that. This seems to be not supported functionality in
       dependent library Reader or Writer</p>
    <pre style="color:red; text-width:weight;">%s</pre>
  </body>
</html>
"""

EXCEPTION_ERROR = """
<html>
  <head></head>
  <body>
    <h1>Exception Error!</h1>
    <pre style="color:red; text-width:weight;">%s</pre>
  </body>
</html>
"""

MARKUP = """<span background="#ddd"> %s </span>"""


class Renderer(Overlay):
    """Renderer widget; delegates HTML display to a :class:`BrowserView`."""

    __gsignals__ = ImutableDict({
        # Emitted when the user scrolls the rendered preview.
        "user-scrolled": (GObject.SignalFlags.RUN_FIRST, None, ()),
    })

    def __init__(self, win, parser="rst", writer="html4", style=""):
        super().__init__()

        self.fgcolor = "#000"
        self.bgcolor = "#fff"
        self.linkcolor = "#000"
        self.font_family = "sans-serif"
        self.font_size_px = 16  # WebKit default (≈ 12pt at 96 DPI)
        self.mono_family = "monospace"
        self.mono_size_px = 13  # WebKit default for monospace

        self.webview = create_browser_view()
        self.webview.connect(EVENT_HOVER_CHANGED, self._on_hover_changed)
        self.webview.connect(EVENT_LOAD_FINISHED, self._on_load_finished)
        self.webview.connect(EVENT_LINK_CLICKED, self._on_link_clicked)
        self.webview.connect(
            EVENT_USER_SCROLLED, lambda: self.emit("user-scrolled"),
        )

        Adw.StyleManager.get_default().connect(
            "notify::dark",
            self.on_theme_changed,
        )
        Gtk.Settings.get_default().connect(
            "notify::gtk-theme-name",
            self.on_theme_changed,
        )
        self.connect("realize", lambda _w: self.on_theme_changed())

        try:
            self._desktop_settings = Gio.Settings(
                schema_id="org.gnome.desktop.interface",
            )
            self._desktop_settings.connect(
                "changed::document-font-name",
                self._on_system_font_changed,
            )
            self._desktop_settings.connect(
                "changed::monospace-font-name",
                self._on_system_font_changed,
            )
        except Exception:
            self._desktop_settings = None  # non-GNOME desktop

        self.set_child(self.webview.widget)

        self._apply_system_font()

        self.label = Label()
        self.label.set_halign(Align.START)
        self.label.set_valign(Align.END)
        self.add_overlay(self.label)
        self.link_uri = None

        # Window reference must be available before parser initialization
        self.__win = win
        self.parser_instance = None

        self.set_writer(writer)
        self.set_parser(parser)

        self.style = style
        self.tab_width = 8
        self.file_name = None
        # Render context includes all values that can affect the page head.
        self._loaded_context = None
        self._pending_context = None
        self.pos = 0
        self.src = None  # None = no content yet; prevents spurious renders

    @staticmethod
    def _rgba_to_hex(rgba):
        """Convert Gdk.RGBA to #rrggbb hex string."""
        r = round(rgba.red * 255)
        g = round(rgba.green * 255)
        b = round(rgba.blue * 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _read_theme_colors(self):
        """Read background, foreground and accent colors from the widget style.

        Uses Adwaita named colors (view_bg_color, view_fg_color,
        accent_color) looked up on the realised widget so that the injected
        CSS always matches the active GTK theme without hardcoded values.
        Falls back to Adwaita defaults when a color is not found.
        """
        ctx = self.get_style_context()
        found_bg, bg = ctx.lookup_color("view_bg_color")
        found_fg, fg = ctx.lookup_color("view_fg_color")
        found_ac, ac = ctx.lookup_color("accent_color")
        is_dark = self._is_dark()
        self.bgcolor = (
            self._rgba_to_hex(bg)
            if found_bg
            else ("#1d1d1d" if is_dark else "#fafafa")
        )
        self.fgcolor = (
            self._rgba_to_hex(fg)
            if found_fg
            else ("#ffffff" if is_dark else "#2e2e2e")
        )
        self.linkcolor = self._rgba_to_hex(ac) if found_ac else self.fgcolor

    def _read_system_font(self):
        """Read document and monospace font family and size from GNOME."""
        try:
            settings = Gio.Settings(schema_id="org.gnome.desktop.interface")
            font_name = settings.get_string("document-font-name") or ""
            mono_name = settings.get_string("monospace-font-name") or ""
        except Exception:
            font_name = ""
            mono_name = ""

        if font_name:
            desc = Pango.FontDescription.from_string(font_name)
            self.font_family = desc.get_family() or self.font_family
            size = desc.get_size()
            self.font_size_px = round(
                (size / Pango.SCALE if size else 12) * _PT_TO_CSS_PX,
            )

        if mono_name:
            mono_desc = Pango.FontDescription.from_string(mono_name)
            self.mono_family = mono_desc.get_family() or self.mono_family
            mono_size = mono_desc.get_size()
            self.mono_size_px = round(
                (mono_size / Pango.SCALE if mono_size else 12) * _PT_TO_CSS_PX,
            )

    def _apply_system_font(self):
        """Apply system document and monospace fonts to the browser view."""
        self._read_system_font()
        self.webview.set_fonts(
            self.font_family,
            self.font_size_px,
            self.mono_family,
            self.mono_size_px,
        )

    def _on_system_font_changed(self, _settings, _key):
        """React to system font change and re-render the preview."""
        self._apply_system_font()
        idle_add(self._apply_theme_and_render)

    @staticmethod
    def _is_dark():
        """Return True if dark mode is active.

        Checks both Adwaita StyleManager and the GTK theme name so that
        the renderer updates regardless of whether the user switches via
        GNOME Settings (color-scheme) or GNOME Tweaks (gtk-theme-name).
        """
        if Adw.StyleManager.get_default().get_dark():
            return True
        theme = Gtk.Settings.get_default().get_property("gtk-theme-name")
        return "dark" in theme.lower()

    def on_theme_changed(self, *_):
        """Schedule a theme colour update after the CSS cascade settles."""
        idle_add(self._apply_theme_and_render)

    def _apply_theme_and_render(self):
        """Read current theme colours and re-render the preview.

        Called via idle_add so the GTK/libadwaita CSS cascade has finished
        recalculating before lookup_color() is invoked.
        """
        self._read_theme_colors()
        self.webview.set_background_color(self.bgcolor)
        self.webview.set_foreground_color(self.fgcolor)
        self.do_render()

    @property
    def position(self):
        """Return cursor position."""
        return self.webview.get_scroll_fraction()

    def _on_hover_changed(self, target):
        """Show url links on mouse over."""
        self.link_uri = target.uri if target else None
        if target is None:
            if self.label.is_visible():
                self.label.hide()
            return
        prefix = {"link": "link: ", "image": "image:", "media": "media: "}
        text = prefix[target.kind] + target.uri
        self.label.set_markup(MARKUP % text.replace("&", "&amp;"))
        self.label.show()

    def _on_link_clicked(self, uri):
        """Handle a link click reported by the browser view.

        Open files internally, others externally.
        Scroll to anchor for internal same-file links.
        """
        if uri.startswith("file://"):
            parts = uri[7:].split("#", 1)
            file_path = unquote(parts[0])
            anchor = unquote(parts[1]) if len(parts) > 1 else None
            if anchor and file_path == self.file_name:
                self.scroll_to_anchor(anchor)
            else:
                self.find_and_opendocument(file_path)
        else:
            Gtk.show_uri(self.__win, uri, Gdk.CURRENT_TIME)

    def scroll_to_anchor(self, anchor):
        """Scroll to a named anchor in the current document."""
        self.webview.scroll_to_anchor(anchor)

    def find_and_opendocument(self, file_path):
        """Find file on disk and open it."""
        ext = splitext(file_path)[1]
        if not ext:
            for ext in LANG_BY_EXT:
                tmp = file_path + ext
                if exists(tmp):
                    file_path = tmp
                    break
            else:
                # No existing file found; inherit the source file's
                # extension so a new file gets the same type as the
                # document it came from.
                src_ext = splitext(self.file_name)[1] if self.file_name else ""
                if src_ext in LANG_BY_EXT:
                    file_path += src_ext
                    ext = src_ext
        if ext in LANG_BY_EXT:
            self.__win.open_document(file_path)
        elif exists(file_path):
            Gtk.show_uri(self.__win, "file://" + file_path, Gdk.CURRENT_TIME)
        else:
            dialog = FileNotFoundDialog(file_path)
            run_alert_dialog(dialog, self.__win)

    def set_writer(self, writer):
        """Set renderer writer."""
        assert writer in WRITERS
        self.__writer = WRITERS[writer]
        klass = self.__writer["class"]
        self.writer_instance = klass() if klass is not None else None
        self._loaded_context = None
        idle_add(self.do_render)

    def get_writer(self):
        """Return renderer writer."""
        return self.__writer["key"]

    def set_parser(self, parser):
        """Set renderer parser."""
        assert parser in PARSERS
        self.__parser = PARSERS[parser]
        klass = self.__parser["class"]
        self.parser_instance = klass() if klass is not None else None
        self._loaded_context = None
        if isinstance(self.parser_instance, JSONPreview):
            self.parser_instance.webview = self.webview
            self.parser_instance._win = self.__win  # noqa: SLF001
        idle_add(self.do_render)

    def get_parser(self):
        """Return renderer parser."""
        return self.__parser["key"]

    def json_expand_all(self):
        """Expand all collapsed JSON elements."""
        if isinstance(self.parser_instance, JSONPreview):
            self.parser_instance.expand_all()

    def json_collapse_all(self):
        """Collapse all expanded JSON elements."""
        if isinstance(self.parser_instance, JSONPreview):
            self.parser_instance.collapse_all()

    def set_style(self, style):
        """Set style for webview."""
        self.style = style
        self._loaded_context = (
            None  # force full page reload to apply new stylesheet
        )
        idle_add(self.do_render)

    def get_style(self):
        """Return selected style."""
        return self.style

    def set_tab_width(self, width):
        """Set tab width."""
        self.tab_width = width
        idle_add(self.do_render)

    def render_output(self):  # noqa: C901, PLR0911
        """Render source and return output."""
        if getattr(self, "src", None) is None:
            return False, "", "text/plain"
        try:
            if self.__parser["class"] is None:
                html = NOT_FOUND.format(**self.__parser)
            elif self.__writer["class"] is None:
                html = NOT_FOUND.format(**self.__writer)
            elif issubclass(self.__parser["class"], JSONPreview):
                try:
                    parser = self.parser_instance
                    html = parser.to_html(self.src, self.tab_width)
                except (ValueError, TypeError) as e:
                    return False, DATA_ERROR % ("JSON", str(e)), "text/html"
                return True, html, "text/html"
            elif issubclass(self.__parser["class"], MistunePreview):
                html = self.parser_instance.to_html(self.src, self.tab_width)
                html = self._embed_stylesheet(html, self.style)
                return True, html, "text/html"
            elif not issubclass(self.__parser["class"], HtmlPreview):
                settings = _docutils_settings(
                    self.tab_width,
                    self.file_name,
                    self.style,
                )
                kwargs = {
                    "source": self.src,
                    "source_path": self.file_name,
                    "parser": self.parser_instance,
                    "writer": self.writer_instance,
                    "writer_name": "html",
                    "settings_overrides": settings,
                }
                if self.__writer["key"] == "pep":
                    kwargs["reader_name"] = "pep"
                    kwargs.pop("parser")  # pep is always rst
                html = publish_string(**kwargs).decode("utf-8")
                return True, html, "text/html"

        except DataError as e:
            return False, DATA_ERROR % ("Data", e), "text/html"

        except NotImplementedError:
            exc_str = format_exc()
            return False, NOT_IMPLEMENTED_ERROR % exc_str, "text/html"

        except BaseException:
            exc_str = format_exc()
            return False, EXCEPTION_ERROR % exc_str, "text/html"

        # output to file or html preview
        return False, self.src, "text/html"

    @staticmethod
    def _embed_stylesheet(html, style_path):
        """Inline *style_path*'s CSS content into *html*'s ``<head>``.

        Mirrors docutils' ``embed_stylesheet`` for parsers, like Mistune,
        that don't go through ``publish_string``.
        """
        if not style_path:
            return html
        try:
            with open(style_path, encoding="utf-8") as f:
                css = f.read()
        except OSError:
            return html
        return html.replace("</head>", f"<style>{css}</style></head>", 1)

    @staticmethod
    def _extract_body(html):
        """Extract the innerHTML of <body> from an HTML string, or None."""
        start = html.find("<body")
        end = html.rfind("</body>")
        if start < 0 or end < 0:
            return None
        tag_end = html.find(">", start)
        if tag_end < 0:
            return None
        return html[tag_end + 1: end]

    def do_render(self):
        """Render the source, and show rendered output."""
        # Skip until content has been explicitly set via render() or
        # load_file().  set_writer/set_parser/set_tab_width all call
        # idle_add(do_render) during initialisation before any content exists;
        # without this guard they each trigger a full WebKit load_bytes() with
        # empty HTML.
        if self.src is None:
            return
        state, html, mime_type = self.render_output()
        if html and self.__win.running:
            if mime_type == "text/html" and "</head>" in html:
                if not self.style:
                    theme_css = (
                        f"<style>"
                        f"body,main{{background-color:"
                        f"{self.bgcolor}!important;"
                        f"color:{self.fgcolor}!important}}"
                        f"a{{color:{self.linkcolor}!important}}"
                        f"</style>"
                    )
                    html = html.replace("</head>", theme_css + "</head>", 1)
                context = (
                    self.file_name,
                    mime_type,
                    self.style,
                    self.bgcolor,
                    self.fgcolor,
                    self.linkcolor,
                )
                if self._loaded_context == context:
                    body_html = self._extract_body(html)
                    patched = body_html is not None and (
                        self.webview.render_incremental(body_html)
                    )
                    if patched:
                        if hasattr(self.parser_instance, "inject_fold_js"):
                            self.parser_instance.inject_fold_js(self.webview)
                        self.scroll_to_position(self.pos)
                        return
            file_name = self.file_name or get_home_dir()
            self._pending_context = (
                self.file_name,
                mime_type,
                self.style,
                self.bgcolor,
                self.fgcolor,
                self.linkcolor,
            )
            self.webview.load(html, mime_type, "file://" + file_name)
        if state:
            self.scroll_to_position(self.pos)

    def render(self, src, file_name, pos=0):
        """Add render task to ui queue."""
        self.src = src
        self.pos = pos
        self.file_name = file_name
        idle_add(self.do_render)

    def print_page(self):
        """Print the rendered page."""
        self.webview.print_page(self.__win)

    def _on_load_finished(self):
        """Restore scroll position once a freshly loaded page is ready."""
        self._loaded_context = self._pending_context
        self.scroll_to_position(None)

    def owns_focus_widget(self, widget):
        """Return whether *widget* is this renderer's own focus target.

        Some backends expose an embeddable widget (``webview.widget``)
        that isn't itself the focusable/interactive part - e.g. the
        litehtml backend's is a ``Gtk.ScrolledWindow`` wrapping the
        actual ``Gtk.DrawingArea`` that receives focus - so a plain
        identity check against ``webview.widget`` misses those.
        """
        if widget is None:
            return False
        root = self.webview.widget
        return widget is root or widget.is_ancestor(root)

    def do_next_match(self, text):
        """Find next match."""
        return self.webview.find_next(text)

    def do_previous_match(self, text):
        """Find previous match."""
        return self.webview.find_previous(text)

    def stop_search(self):
        """Stop searching."""
        self.webview.stop_search()

    def scroll_to_position(self, position):
        """Scroll to right cursor position."""
        if position is not None:
            self.pos = position

        if self.pos > 1:  # vim
            a, b = len(self.src[:self.pos]), len(self.src[self.pos:])
            position = (float(a) / (a + b)) if a or b else 0
        else:
            position = self.pos

        self.webview.scroll_to_fraction(position)
