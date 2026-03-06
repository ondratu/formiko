"""Webkit based renderer."""

from io import StringIO
from json import dumps
from os.path import exists, splitext
from traceback import format_exc

from docutils import DataError
from docutils.core import publish_string
from docutils.parsers.rst import Parser as RstParser
from docutils.writers.html4css1 import Writer as Writer4css1
from docutils.writers.html5_polyglot import Writer as Html5Writer
from docutils.writers.pep_html import Writer as WriterPep
from docutils.writers.s5_html import Writer as WriterS5
from gi.repository import Adw, Gdk, Gtk
from gi.repository.GLib import (
    MAXUINT,
    Bytes,
    Error,
    LogLevelFlags,
    MainContext,
    get_home_dir,
    idle_add,
    log_default_handler,
)
from gi.repository.Gtk import (
    Align,
    Label,
    Overlay,
)
from gi.repository.WebKit import (
    FindOptions,
    LoadEvent,
    PrintOperation,
    WebView,
)

from formiko.dialogs import FileNotFoundDialog, run_alert_dialog
from formiko.json_preview import JSONPreview
from formiko.sourceview import LANG_BY_EXT
from formiko.utils import Undefined

try:
    from docutils_tinyhtml import Writer as TinyWriter
except ImportError:

    class TinyWriter(Undefined):  # type: ignore[no-redef]
        """Not imported TinyWriter."""


try:
    from m2r2 import convert as m2r_convert  # type: ignore[import]

    class Mark2Resturctured(RstParser):
        """Converting from MarkDown to reStructuredText before parse."""

        def parse(self, inputstring, document):
            """Create RST from MD first and call than parse."""
            return super().parse(m2r_convert(inputstring), document)

except ImportError:

    class Mark2Resturctured(Undefined):  # type: ignore[no-redef]
        """Not imported TinyWriter."""


class HtmlPreview:
    """Dummy html preview class."""


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

if not issubclass(Mark2Resturctured, Undefined):
    EXTS[".md"] = "m2r"

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

NOT_FOUND = """
<html>
  <head></head>
  <body>
    <h1>Commponent {title} Not Found!</h1>
    <p>Component <b>{title}</b> which you want to use is not found.
       See <a href="{url}">{url}</a> for mor details and install it
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

SCROLL = """
<script>
    window.scrollTo(
        0,
        (document.documentElement.scrollHeight-window.innerHeight)*%f)
</script>
"""

JS_SCROLL = """
    window.scrollTo(
        0,
        (document.documentElement.scrollHeight-window.innerHeight)*%f);
"""

JS_POSITION = """
window.scrollY/(document.documentElement.scrollHeight-window.innerHeight)
"""

MARKUP = """<span background="#ddd"> %s </span>"""


class Renderer(Overlay):
    """Renderer widget, mainly based on Webkit."""

    def __init__(self, win, parser="rst", writer="html4", style=""):
        super().__init__()

        self.fgcolor = "#000"
        self.bgcolor = "#fff"
        self.linkcolor = "#000"

        self.webview = WebView()
        self.webview.connect("mouse-target-changed", self.on_mouse)
        self.webview.connect("context-menu", self.on_context_menu)
        self.webview.connect("load-changed", self.on_load_changed)

        # Button release via GestureClick (GTK4)
        gesture = Gtk.GestureClick.new()
        gesture.set_button(0)  # all buttons
        gesture.connect("released", self.on_button_release)
        self.webview.add_controller(gesture)
        self._gesture = gesture

        style_manager = Adw.StyleManager.get_default()
        style_manager.connect("notify::dark", self.on_theme_changed)
        Gtk.Settings.get_default().connect(
            "notify::gtk-theme-name",
            self.on_theme_changed,
        )
        self.connect("realize", lambda _w: self.on_theme_changed())

        self.set_child(self.webview)

        web_settings = self.webview.get_settings()
        web_settings.set_enable_javascript_markup(False)  # XSS Fix

        controller = self.webview.get_find_controller()
        self.search_done = None
        controller.connect("found-text", self.on_found_text)
        controller.connect("failed-to-find-text", self.on_faild_to_find_text)

        self.label = Label()
        self.label.set_halign(Align.START)
        self.label.set_valign(Align.END)
        self.add_overlay(self.label)
        self.link_uri = None
        self.context_button = 3  # will be rewritten by real value

        # Window reference must be available before parser initialization
        self.__win = win
        self.parser_instance = None

        self.set_writer(writer)
        self.set_parser(parser)

        self.style = style
        self.tab_width = 8
        self.__position = -1
        self.file_name = None
        self._loaded_context = None  # (file_name, mime_type) of last full load
        self.pos = 0
        self.src = ""

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
        background = Gdk.RGBA()
        background.parse(self.bgcolor)
        self.webview.set_background_color(background)
        self.do_render()

    @property
    def position(self):
        """Return cursor position."""
        self.__position = -1
        self.webview.evaluate_javascript(
            JS_POSITION,
            -1,
            None,
            None,
            None,
            self.on_position_callback,
        )
        while self.__position < 0:
            Gtk.main_iteration()
        return self.__position

    def on_position_callback(self, webview, result):
        """Set cursor position value."""
        try:
            js_res = webview.evaluate_javascript_finish(result)
            self.__position = js_res.get_js_value().to_double()
        except Error:
            self.__position = 0

    def on_mouse(self, webview, hit_test_result, modifiers):
        """Show url links on mouse over."""
        self.link_uri = None
        if hit_test_result.context_is_link():
            self.link_uri = hit_test_result.get_link_uri()
            text = "link: " + self.link_uri
        elif hit_test_result.context_is_image():
            text = "image:" + hit_test_result.get_image_uri()
        elif hit_test_result.context_is_media():
            text = "media: " + hit_test_result.get_media_uri()
        else:
            if self.label.is_visible():
                self.label.hide()
            return
        self.label.set_markup(MARKUP % text.replace("&", "&amp;"))
        self.label.show()

    def on_context_menu(self, webview, menu, hit_test_result):
        """No action on webkit context menu."""
        self.context_button = self._gesture.get_current_button()
        return True  # disable context menu for now

    def on_button_release(self, gesture, *_):
        """Open links and let other clicks propagate."""
        button = gesture.get_current_button()
        if button != self.context_button and self.link_uri:
            if self.link_uri.startswith("file://"):  # try to open source
                self.find_and_opendocument(self.link_uri[7:].split("#")[0])
            else:
                Gtk.show_uri(None, self.link_uri, Gdk.CURRENT_TIME)

    def find_and_opendocument(self, file_path):
        """Find file on disk and open it."""
        ext = splitext(file_path)[1]
        if not ext:
            for ext in LANG_BY_EXT:
                tmp = file_path + ext
                if exists(tmp):
                    file_path = tmp
                    break
        if ext in LANG_BY_EXT:
            self.__win.open_document(file_path)
        elif exists(file_path):
            Gtk.show_uri(None, "file://" + file_path, Gdk.CURRENT_TIME)
        else:
            dialog = FileNotFoundDialog(file_path)
            run_alert_dialog(dialog, self.__win)

    def set_writer(self, writer):
        """Set renderer writer."""
        assert writer in WRITERS
        self.__writer = WRITERS[writer]
        klass = self.__writer["class"]
        self.writer_instance = klass() if klass is not None else None
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
            elif not issubclass(self.__parser["class"], HtmlPreview):
                settings = {
                    "warning_stream": StringIO(),
                    "embed_stylesheet": True,
                    "tab_width": self.tab_width,
                    "file_name": self.file_name,
                }
                if self.style:
                    settings["stylesheet"] = self.style
                    settings["stylesheet_path"] = []
                kwargs = {
                    "source": self.src,
                    "parser": self.parser_instance,
                    "writer": self.writer_instance,
                    "writer_name": "html",
                    "settings_overrides": settings,
                }
                if self.__writer["key"] == "pep":
                    kwargs["reader_name"] = "pep"
                    kwargs.pop("parser")  # pep is allways rst
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
        state, html, mime_type = self.render_output()
        if html and self.__win.runing:
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
                context = (self.file_name, mime_type)
                if self._loaded_context == context:
                    body_html = self._extract_body(html)
                    if body_html is not None:
                        fgcolor = dumps(self.fgcolor)
                        body_html = dumps(body_html)
                        self.webview.evaluate_javascript(
                            (
                                f"document.fgColor={fgcolor};"
                                f"document.body.innerHTML={body_html};"
                            ),
                            -1,
                            None,
                            None,
                            None,
                            None,
                        )
                        if hasattr(self.parser_instance, "inject_fold_js"):
                            self.parser_instance.inject_fold_js(self.webview)
                        self.scroll_to_position(self.pos)
                        return
            file_name = self.file_name or get_home_dir()
            self._loaded_context = (self.file_name, mime_type)
            self.webview.load_bytes(
                Bytes(html.encode("utf-8")),
                mime_type,
                "UTF-8",
                "file://" + file_name,
            )
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
        po = PrintOperation.new(self.webview)
        po.connect("failed", self.on_print_failed)
        po.run_dialog(self.__win)

    def on_print_failed(self, _, error):
        """Log error when print failed."""
        # FIXME: if dialog is used, application will lock :-(
        log_default_handler(
            "Application",
            LogLevelFlags.LEVEL_WARNING,
            error.message,
        )

    def on_load_changed(self, _webview, load_event):
        """On page load handler.

        Set foreground color and restore scroll when page finishes loading.
        """
        if load_event != LoadEvent.FINISHED:
            return
        self.webview.evaluate_javascript(
            f"document.fgColor='{self.fgcolor}'",
            -1,
            None,
            None,
            None,
            None,
        )
        self.scroll_to_position(None)

    def do_next_match(self, text):
        """Find next metch."""
        controller = self.webview.get_find_controller()
        if controller.get_search_text() != text:
            self.search_done = None
            controller.search(text, FindOptions.WRAP_AROUND, MAXUINT)
            while self.search_done is None:
                MainContext.default().iteration(False)
        elif self.search_done:
            controller.search_next()

        return self.search_done

    def do_previous_match(self, text):
        """Find previous match."""
        controller = self.webview.get_find_controller()
        if controller.get_search_text() != text:
            self.search_done = None
            controller.search(
                text,
                FindOptions.WRAP_AROUND | FindOptions.BACKWARDS,
                MAXUINT,
            )
            while self.search_done is None:
                MainContext.default().iteration(False)
        elif self.search_done:
            controller.search_previous()

        return self.search_done

    def stop_search(self):
        """Stop searching."""
        controller = self.webview.get_find_controller()
        controller.search_finish()

    def on_found_text(self, *_):
        """Mark search as done."""
        self.search_done = True

    def on_faild_to_find_text(self, _):
        """Mark search as not done."""
        self.search_done = False

    def scroll_to_position(self, position):
        """Scroll to right cursor position."""
        if position is not None:
            self.pos = position

        if self.pos > 1:  # vim
            a, b = len(self.src[: self.pos]), len(self.src[self.pos:])
            position = (float(a) / (a + b)) if a or b else 0
        else:
            position = self.pos

        self.webview.evaluate_javascript(
            JS_SCROLL % position,
            -1,
            None,
            None,
            None,
            None,
        )
