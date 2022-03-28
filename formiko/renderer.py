# -*- coding: utf-8 -*-
from io import StringIO
from traceback import format_exc
from sys import version_info
from json import loads, dumps
from os.path import abspath, dirname, splitext, exists

from gi import require_version
require_version('WebKit2', '4.0')   # noqa

from gi.repository.WebKit2 import WebView, PrintOperation, FindOptions
from gi.repository.GLib import idle_add, Bytes, get_home_dir, \
    log_default_handler, LogLevelFlags, MAXUINT, Error
from gi.repository.Gtk import Overlay, Label, Align, main_iteration, \
    show_uri_on_window

from docutils import DataError
from docutils.core import publish_string
from docutils.parsers.rst import Parser as RstParser
from docutils.writers.html4css1 import Writer as Writer4css1
from docutils.writers.s5_html import Writer as WriterS5
from docutils.writers.pep_html import Writer as WriterPep

from formiko.dialogs import FileNotFoundDialog
from formiko.sourceview import LANGS

try:
    from docutils_tinyhtml import Writer as TinyWriter
except ImportError:
    TinyWriter = None

try:
    from docutils_html5 import Writer as Html5Writer
except ImportError:
    Html5Writer = None

try:
    from recommonmark.parser import CommonMarkParser
    from recommonmark.transform import AutoStructify, DummyStateMachine

    class StringStructify(AutoStructify):
        """Support AutoStructify for publish_string function."""
        def apply(self):
            """Apply the transformation by configuration."""
            file_name = self.document.settings.file_name

            self.url_resolver = self.config['url_resolver']
            assert callable(self.url_resolver)

            self.state_machine = DummyStateMachine()
            self.current_level = 0
            self.file_dir = abspath(dirname(file_name))
            self.root_dir = self.file_dir
            self.traverse(self.document)

    class ExtendCommonMarkParser(CommonMarkParser):
        """CommonMarkParser with working AutoStructify."""
        settings_spec = RstParser.settings_spec

        def get_transforms(self):
            return CommonMarkParser.get_transforms(self) + [StringStructify]


except ImportError:
    ExtendCommonMarkParser = None


try:
    from m2r import convert as m2r_convert

    class Mark2Resturctured(RstParser):
        """Converting from MarkDown to reStructuredText before parse"""

        def parse(self, inputstring, document):
            return super(Mark2Resturctured, self).parse(
                m2r_convert(inputstring), document)

except ImportError:
    Mark2Resturctured = None


class HtmlPreview(object):
    """Dummy html preview class"""
    pass


class JSONPreview(object):
    """Dummy json preview class"""
    pass


class Env(object):
    """Empty class for env overriding."""
    srcdir = ''


PARSERS = {
    'rst': {
        'key': 'rst',
        'title': 'Docutils reStructuredText parser',
        'class': RstParser,
        'package': 'docutils',
        'url': 'http://docutils.sourceforge.net'},
    'm2r': {
        'key': 'm2r',
        'title': 'MarkDown to reStructuredText',
        'class': Mark2Resturctured,
        'url': 'https://github.com/miyakogi/m2r'},
    'cm': {
        'key': 'cm',
        'title': 'Common Mark parser',
        'class': ExtendCommonMarkParser,
        'url': 'https://github.com/rtfd/recommonmark'},
    'html': {
        'key': 'html',
        'title': 'HTML preview',
        'class': HtmlPreview},
    'json': {
        'key': 'json',
        'title': 'JSON preview',
        'class': JSONPreview}
}

EXTS = {
    '.rst': 'rst',
    '.html': 'html',
    '.htm': 'html',
    '.json': 'json'
}


if Mark2Resturctured:
    EXTS[".md"] = "m2r"
elif ExtendCommonMarkParser:
    EXTS[".md"] = "cm"


WRITERS = {
    'html4': {
        'key': 'html4',
        'title': 'Docutils HTML4 writer',
        'class': Writer4css1,
        'package': 'docutils',
        'url': 'http://docutils.sourceforge.net'},
    's5': {
        'key': 's5',
        'title': 'Docutils S5/HTML slide show writer',
        'class': WriterS5,
        'package': 'docutils',
        'url': 'http://docutils.sourceforge.net'},
    'pep': {
        'key': 'pep',
        'title': 'Docutils PEP HTML writer',
        'class': WriterPep,
        'package': 'docutils',
        'url': 'http://docutils.sourceforge.net'},
    'tiny': {
        'key': 'tiny',
        'title': 'Tiny HTML writer',
        'class': TinyWriter,
        'package': 'docutils-tinyhtmlwriter',
        'url': 'https://github.com/ondratu/docutils-tinyhtmlwriter'},
    'html5': {
        'key': 'html5',
        'title': 'HTML 5 writer',
        'class': Html5Writer,
        'package': 'docutils-html5-writer',
        'url': 'https://github.com/Kozea/docutils-html5-writer'},
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

    def __init__(self, win, parser='rst', writer='html4', style=''):
        super(Renderer, self).__init__()

        self.webview = WebView()
        self.webview.connect("mouse-target-changed", self.on_mouse)
        self.webview.connect("context-menu", self.on_context_menu)
        self.webview.connect("button-release-event", self.on_button_release)
        self.add(self.webview)

        controller = self.webview.get_find_controller()
        self.search_done = None
        controller.connect("found-text", self.on_found_text)
        controller.connect("failed-to-find-text", self.on_faild_to_find_text)

        self.label = Label()
        self.label.set_halign(Align.START)
        self.label.set_valign(Align.END)
        self.add_overlay(self.label)
        self.link_uri = None
        self.context_button = 3     # will be rewrite by real value

        self.set_writer(writer)
        self.set_parser(parser)
        self.style = style
        self.tab_width = 8
        self.__win = win

    @property
    def position(self):
        self.__position = -1
        self.webview.run_javascript(
            JS_POSITION, None, self.on_position_callback, None)
        while self.__position < 0:
            # this call at this place do problem, when Gdk.threads_init
            main_iteration()
        return self.__position

    def on_position_callback(self, webview, result, data):
        try:
            js_res = webview.run_javascript_finish(result)
            self.__position = js_res.get_js_value().to_double()
        except Error:
            self.__position = 0

    def on_mouse(self, webview, hit_test_result, modifiers):
        self.link_uri = None
        if hit_test_result.context_is_link():
            self.link_uri = hit_test_result.get_link_uri()
            text = "link: %s" % self.link_uri
        elif hit_test_result.context_is_image():
            text = "image: %s" % hit_test_result.get_image_uri()
        elif hit_test_result.context_is_media():
            text = "media: %s" % hit_test_result.get_media_uri()
        else:
            if self.label.is_visible():
                self.label.hide()
            return
        self.label.set_markup(MARKUP % text.replace("&", "&amp;"))
        self.label.show()

    def on_context_menu(self, webview, menu, event, hit_test_result):
        self.context_button = event.button.button
        return True     # disable context menu for now

    def on_button_release(self, webview, event):
        """Catch release-button only when try to follow link.

        Context menu is catch by webview before this callback.
        """
        if event.button == self.context_button:
            return True
        if self.link_uri:
            if self.link_uri.startswith("file://"):    # try to open source
                self.find_and_opendocument(self.link_uri[7:].split('#')[0])
            else:
                show_uri_on_window(None, self.link_uri, 0)
        return True

    def find_and_opendocument(self, file_path):
        ext = splitext(file_path)[1]
        if not ext:
            for EXT in LANGS.keys():
                tmp = file_path + EXT
                if exists(tmp):
                    file_path = tmp
                    ext = EXT
                    break
        if ext in LANGS:
            self.__win.open_document(file_path)
        elif exists(file_path):
            show_uri_on_window(None, "file://"+file_path, 0)
        else:
            dialog = FileNotFoundDialog(self.__win, file_path)
            dialog.run()
            dialog.destroy()

    def set_writer(self, writer):
        assert writer in WRITERS
        self.__writer = WRITERS[writer]
        klass = self.__writer['class']
        self.writer_instance = klass() if klass is not None else None
        idle_add(self.do_render)

    def get_writer(self):
        return self.__writer['key']

    def set_parser(self, parser):
        assert parser in PARSERS
        self.__parser = PARSERS[parser]
        klass = self.__parser['class']
        self.parser_instance = klass() if klass is not None else None
        idle_add(self.do_render)

    def get_parser(self):
        return self.__parser['key']

    def set_style(self, style):
        self.style = style
        idle_add(self.do_render)

    def get_style(self):
        return self.style

    def set_tab_width(self, width):
        self.tab_width = width

    def render_output(self):
        if getattr(self, 'src', None) is None:
            return False, "", "text/plain"
        try:
            if self.__parser['class'] is None:
                html = NOT_FOUND.format(**self.__parser)
            elif self.__writer['class'] is None:
                html = NOT_FOUND.format(**self.__writer)
            elif issubclass(self.__parser['class'], JSONPreview):
                try:
                    json = loads(self.src)
                    return (False, dumps(json, sort_keys=True,
                                         ensure_ascii=False,
                                         indent=4, separators=(',', ': ')),
                            'application/json')
                except ValueError as e:
                    return False, DATA_ERROR % ('JSON', str(e)), "text/html"
            else:
                if not issubclass(self.__parser['class'], HtmlPreview):
                    settings = {
                        'warning_stream': StringIO(),
                        'embed_stylesheet': True,
                        'tab_width': self.tab_width,
                        'file_name': self.file_name
                    }
                    if self.style:
                        settings['stylesheet'] = self.style
                        settings['stylesheet_path'] = []
                    kwargs = {'source': self.src,
                              'parser': self.parser_instance,
                              'writer': self.writer_instance,
                              'writer_name': 'html',
                              'settings_overrides': settings}
                    if self.__writer['key'] == 'pep':
                        kwargs['reader_name'] = 'pep'
                        kwargs.pop('parser')    # pep is allways rst
                    html = publish_string(**kwargs).decode('utf-8')
                    return True, html, 'text/html'
                else:
                    if version_info.major == 2:
                        html = self.src.decode("utf-8")
                    else:
                        html = self.src

            # output to file or html preview
            return False, html, 'text/html'
        except DataError as e:
            return False, DATA_ERROR % ('Data', e), 'text/html'

        except NotImplementedError:
            exc_str = format_exc()
            return False, NOT_IMPLEMENTED_ERROR % exc_str, 'text/html'

        except BaseException:
            exc_str = format_exc()
            return False, EXCEPTION_ERROR % exc_str, 'text/html'

    def do_render(self):
        state, html, mime_type = self.render_output()
        if state:
            if self.pos > 1:     # vim
                a, b = len(self.src[:self.pos]), len(self.src[self.pos:])
                position = (float(a)/(a+b)) if a or b else 0
            else:
                position = self.pos

            html += SCROLL % position
        if html and self.__win.runing:
            file_name = self.file_name or get_home_dir()
            self.webview.load_bytes(Bytes(html.encode("utf-8")),
                                    mime_type, "UTF-8", "file://"+file_name)

    def render(self, src, file_name, pos=0):
        self.src = src
        self.pos = pos
        self.file_name = file_name
        idle_add(self.do_render)

    def print_page(self):
        po = PrintOperation.new(self.webview)
        po.connect("failed", self.on_print_failed)
        po.run_dialog(self.__win)

    def on_print_failed(self, po, error):
        # FIXME: if dialog is used, application will lock :-(
        log_default_handler("Application", LogLevelFlags.LEVEL_WARNING,
                            error.message)

    def do_next_match(self, text):
        controller = self.webview.get_find_controller()
        if controller.get_search_text() != text:
            self.search_done = None
            controller.search(text, FindOptions.WRAP_AROUND, MAXUINT)
            while self.search_done is None:
                main_iteration()
        elif self.search_done:
            controller.search_next()

        return self.search_done

    def do_previous_match(self, text):
        controller = self.webview.get_find_controller()
        if controller.get_search_text() != text:
            self.search_done = None
            controller.search(
                text, FindOptions.WRAP_AROUND | FindOptions.BACKWARDS, MAXUINT)
            while self.search_done is None:
                main_iteration()
        elif self.search_done:
            controller.search_previous()

        return self.search_done

    def stop_search(self):
        controller = self.webview.get_find_controller()
        controller.search_finish()

    def on_found_text(self, controller, count):
        self.search_done = True

    def on_faild_to_find_text(self, controller):
        self.search_done = False

    def scroll_to_position(self, position):
        if position is not None:
            self.pos = position

        if self.pos > 1:     # vim
            a, b = len(self.src[:self.pos]), len(self.src[self.pos:])
            position = (float(a)/(a+b)) if a or b else 0
        else:
            position = self.pos

        self.webview.run_javascript(JS_SCROLL % position, None, None, None)
