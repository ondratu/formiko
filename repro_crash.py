"""TEMPORARY diagnostic script - reproduces the writer-switch crash headlessly.

Mirrors formiko/litehtml_browser.py's LitehtmlBrowserView: a single
_lhpango.document_container is reused across renders (as
LitehtmlBrowserView reuses self._container across every load()), and
_extract_surface()'s zero-copy path wraps the container's own buffer
directly via cairo.ImageSurface.create_for_data(container.get_data(), ...).

Renders README.rst first with the HTML4 writer, then with the HTML5
writer using the SAME container - the same sequence that froze/crashed
the real app when switching the writer in the UI - to check whether this
is a litehtml/litehtmlpy bug independent of GTK.
"""

from io import StringIO

import cairo
from docutils.core import publish_string
from docutils.writers.html4css1 import Writer as Writer4css1
from docutils.writers.html5_polyglot import Writer as Html5Writer
from litehtmlpy import litehtmlpango as _lhpango
from litehtmlpy import litehtmlpy as _lh

with open("README.rst", encoding="utf-8") as f:
    src = f.read()


def render_html(writer_class):
    settings = {
        "warning_stream": StringIO(),
        "embed_stylesheet": True,
        "tab_width": 4,
        "file_name": "README.rst",
    }
    return publish_string(
        source=src,
        writer=writer_class(),
        writer_name="html",
        settings_overrides=settings,
    ).decode("utf-8")


print("Rendering HTML4 writer output...", flush=True)
html4 = render_html(Writer4css1)
print("Rendering HTML5 writer output...", flush=True)
html5 = render_html(Html5Writer)


class Container(_lhpango.document_container):
    def __init__(self):
        super().__init__(parent=None)
        self.set_dpi(96)

    def load_image(self, src, baseurl, redraw_on_ready):
        pass

    def on_anchor_click(self, url, el):
        pass

    def set_base_url(self, url):
        pass

    def on_mouse_event(self, el, event):
        pass

    def set_cursor(self, cursor):
        pass


def render_once(container, html, width=800, label=""):
    print(f"[{label}] fromString...", flush=True)
    container.size = _lh.size(width, 1)
    doc = container.fromString(html, None, None)
    print(f"[{label}] render...", flush=True)
    doc.render(_lh.pixel_float_t(width), _lh.render_all)
    doc_width = max(1, int(doc.width().value))
    doc_height = max(1, int(doc.height().value))
    print(f"[{label}] surface {doc_width}x{doc_height}...", flush=True)
    hdc = container.surface(doc_width, doc_height)
    clip = _lh.position(0, 0, doc_width, doc_height)
    print(f"[{label}] draw...", flush=True)
    doc.draw(hdc, _lh.pixel_float_t(0), _lh.pixel_float_t(0), clip)
    print(f"[{label}] get_data + create_for_data...", flush=True)
    stride = cairo.ImageSurface.format_stride_for_width(
        cairo.FORMAT_ARGB32, doc_width,
    )
    surface = cairo.ImageSurface.create_for_data(
        container.get_data(),
        cairo.FORMAT_ARGB32,
        doc_width,
        doc_height,
        stride,
    )
    print(f"[{label}] done", flush=True)
    return surface


c = Container()
s1 = render_once(c, html4, label="html4")
print("Rendering html5 with the SAME container now...", flush=True)
s2 = render_once(c, html5, label="html5")
print("Dropping the old (html4) surface now...", flush=True)
del s1
print("SUCCESS: no crash", flush=True)
