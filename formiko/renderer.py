# -*- coding: utf-8 -*-
from gi import require_version

require_version('WebKit2', '4.0')   # noqa

from gi.repository.WebKit2 import WebView
from gi.repository.GLib import idle_add, Bytes, get_home_dir
from gi.repository.Gtk import ScrolledWindow, PolicyType, Overlay, Label, \
    Align

from docutils import DataError
from docutils.core import publish_string
from docutils.parsers.rst import Parser as RstParser
from docutils.writers.html4css1 import Writer as Writer4css1
from docutils.writers.s5_html import Writer as WriterS5
from docutils.writers.pep_html import Writer as WriterPep

try:
    from docutils_tinyhtml import Writer as TinyWriter
except:
    TinyWriter = None

try:
    from htmlwriter import Writer as HtmlWriter
except:
    HtmlWriter = None

try:
    from docutils_html5 import Writer as Html5Writer
except:
    Html5Writer = None

try:
    from recommonmark.parser import CommonMarkParser
except:
    CommonMarkParser = None

from io import StringIO
from traceback import format_exc
from sys import version_info
from json import loads, dumps


class HtmlPreview(object):
    """Dummy html preview class"""
    pass


class JSONPreview(object):
    """Dummy json preview class"""
    pass


PARSERS = {
    'rst': {
        'key': 'rst',
        'title': 'Docutils reStructuredText parser',
        'class': RstParser,
        'url': 'http://docutils.sourceforge.net'},
    'md': {
        'key': 'md',
        'title': 'Common Mark parser',
        'class': CommonMarkParser,
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
    '.md': 'md',
    '.html': 'html',
    '.htm': 'html',
    '.json': 'json'
}

WRITERS = {
    'html4': {
        'key': 'html4',
        'title': 'Docutils HTML4 writer',
        'class': Writer4css1,
        'url': 'http://docutils.sourceforge.net'},
    's5': {
        'key': 's5',
        'title': 'Docutils S5/HTML slide show writer',
        'class': WriterS5,
        'url': 'http://docutils.sourceforge.net'},
    'pep': {
        'key': 'pep',
        'title': 'Docutils PEP HTML writer',
        'class': WriterPep,
        'url': 'http://docutils.sourceforge.net'},
    'tiny': {
        'key': 'tiny',
        'title': 'Tiny HTML writer',
        'class': TinyWriter,
        'url': 'https://github.com/ondratu/docutils-tinyhtmlwriter'},
    'html': {
        'key': 'html',
        'title': 'Yet another HTML writer',
        'class': HtmlWriter,
        'url': 'https://github.com/masayuko/docutils-htmlwriter'},
    'html5': {
        'key': 'html5',
        'title': 'HTML 5 writer',
        'class': Html5Writer,
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

MARKUP = """<span background="#ddd"> %s </span>"""


class Renderer(Overlay):
    def __init__(self, win, parser='rst', writer='html4', style=''):
        super(Renderer, self).__init__()
        scrolled = ScrolledWindow.new(None, None)
        scrolled.set_policy(PolicyType.AUTOMATIC, PolicyType.AUTOMATIC)
        self.sb = scrolled.get_vscrollbar()
        self.add(scrolled)

        self.webview = WebView()
        self.webview.connect("mouse-target-changed", self.on_mouse)
        scrolled.add(self.webview)

        self.label = Label()
        self.label.set_halign(Align.START)
        self.label.set_valign(Align.END)

        self.add_overlay(self.label)

        self.set_writer(writer)
        self.set_parser(parser)
        self.style = style
        self.__win = win

    def on_mouse(self, web_view, hit_test_result, modifiers):
        if hit_test_result.context_is_link():
            text = "link: %s" % hit_test_result.get_link_uri()
        elif hit_test_result.context_is_image():
            text = "image: %s" % hit_test_result.get_image_uri()
        elif hit_test_result.context_is_media():
            text = "media: %s" % hit_test_result.get_media_uri()
        else:
            if self.label.is_visible():
                self.label.hide()
            return

        self.label.set_markup(MARKUP % text)
        self.label.show()

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
                                         indent=4, separators=(',', ': ')),
                            'application/json')
                except ValueError as e:
                    return False, DATA_ERROR % ('JSON', str(e)), "text/html"
            else:
                if not issubclass(self.__parser['class'], HtmlPreview):
                    settings = {
                        'warning_stream': StringIO(),
                        'embed_stylesheet': True
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

        except:
            exc_str = format_exc()
            return False, EXCEPTION_ERROR % exc_str, 'text/html'

    def do_render(self):
        state, html, mime_type = self.render_output()
        if state:
            a, b = len(self.src[:self.pos]), len(self.src[self.pos:])
            position = (float(a)/(a+b)) if a or b else 0

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
