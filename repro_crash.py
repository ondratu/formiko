"""TEMPORARY diagnostic script - reproduces the writer-switch crash headlessly.

Drives the real formiko.litehtml_browser.LitehtmlBrowserView directly (no
GTK main loop, no visible window): load()s README.rst rendered with the
HTML4 writer, invokes its real _on_draw() against a plain cairo.ImageSurface
target (exactly how GTK's own DrawingArea draw callback would), then
load()s it again rendered with the HTML5 writer and draws again - the same
sequence that froze/crashed the real app when switching the writer in the
UI. Loops a few times in case the underlying bug is a heap-corruption
effect that doesn't reproduce on the very first switch.
"""

from io import StringIO

import cairo
from docutils.core import publish_string
from docutils.writers.html4css1 import Writer as Writer4css1
from docutils.writers.html5_polyglot import Writer as Html5Writer
from gi import require_version

require_version("Gtk", "4.0")
require_version("Gdk", "4.0")
require_version("Adw", "1")
require_version("GtkSource", "5")
require_version("Pango", "1.0")

from formiko.litehtml_browser import LitehtmlBrowserView

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

view = LitehtmlBrowserView()
width, height = 800, 600
target = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
cr = cairo.Context(target)


def do_draw(label):
    print(f"[{label}] load()...", flush=True)
    print(f"[{label}] _on_draw()...", flush=True)
    view._on_draw(view._area, cr, width, height)  # noqa: SLF001
    print(f"[{label}] drawn", flush=True)


for i in range(10):
    print(f"=== iteration {i} ===", flush=True)
    view.load(html4, "text/html", "file://README.rst")
    do_draw(f"html4-{i}")
    do_draw(f"html4-{i}-redraw")  # same width - exercises the cached path
    view.load(html5, "text/html", "file://README.rst")
    do_draw(f"html5-{i}")
    do_draw(f"html5-{i}-redraw")

print("SUCCESS: no crash", flush=True)
