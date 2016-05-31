# -*- coding: utf-8 -*-
from gi.repository import Gtk, WebKit

from docutils.core import publish_string
# from docutils_tinyhtml import Writer
from docutils.writers.html4css1 import Writer

from io import StringIO
from traceback import print_exc


class Renderer(Gtk.ScrolledWindow):
    def __init__(self):
        super(Renderer, self).__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC,
                        Gtk.PolicyType.AUTOMATIC)
        self.webview = WebKit.WebView()
        self.sb = self.get_vscrollbar()
        self.add(self.webview)
        self.writer = Writer()

    def render(self, app_win, rst, pos=0):
        try:
            a, b = len(rst[:pos]), len(rst[pos:])
            position = (float(a)/(a+b)) if a or b else 0
            html = publish_string(
                source=rst,
                writer=self.writer,
                writer_name='html',
                settings_overrides={
                    'warning_stream': StringIO()
                }).decode('utf-8')
            html += """
                <script>
                  window.scrollTo(
                     0,
                     (document.documentElement.scrollHeight-window.innerHeight)*%f)
                </script>
            """ % position
            if not app_win.runing:
                return
            self.webview.load_string(html, "text/html", "UTF-8", "file:///")
        except:
            print_exc()
