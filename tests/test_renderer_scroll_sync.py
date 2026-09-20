"""Tests for keeping the preview's scroll position in sync with the editor.

The renderer is exercised through a duck-typed adapter (only the methods
under test are borrowed from :class:`formiko.renderer.Renderer`) driving a
fake browser view, so no GTK widget tree or display server is needed.
"""

from types import FunctionType, SimpleNamespace

from formiko.renderer import Renderer

HEAD = "<html><head></head><body>{}</body></html>"


class _FakeBrowser:
    """Browser view that models what a real engine does to scrolling.

    A scroll issued while a document is still loading is lost (it hits
    the old document), a finished load starts at the top, and a body patch
    that grows the content moves the scroll fraction of the same offset.
    """

    def __init__(self):
        self.scroll = 0.0
        self.loading = False
        self.loads = 0
        self.patches = 0
        self.body = None
        self._owner = None

    def load(self, html, _mime_type, _base_uri):
        self.loads += 1
        self.loading = True
        self.body = Renderer._extract_body(html)

    def render_incremental(self, body_html):
        self.patches += 1
        if body_html != self.body:
            self.scroll *= 0.9  # the content got longer
        self.body = body_html
        return True

    def scroll_to_fraction(self, fraction):
        if not self.loading:
            self.scroll = fraction

    def finish_load(self):
        """Complete the pending load like the engine would."""
        self.loading = False
        self.scroll = 0.0
        self._owner._on_load_finished()


class _RendererAdapter:
    """Stand-in for :class:`Renderer` running its own render/scroll code.

    Every plain method of ``Renderer`` is borrowed, so the logic under
    test is the real one; only the state it reads is provided here.
    """

    def __init__(self, pos=0.0):
        self.webview = _FakeBrowser()
        self.webview._owner = self
        self._Renderer__win = SimpleNamespace(running=True)
        self.parser_instance = None
        self.file_name = "doc.rst"
        self.style = ""
        self.bgcolor = self.fgcolor = self.linkcolor = "#000"
        self.src = "text"
        self.pos = pos
        self.html = HEAD.format("one")
        self._loaded_context = None
        self._pending_context = None
        self._pending_html = None
        self._synced_pos = None
        self._synced_html = None

    def render_output(self):
        return True, self.html, "text/html"

    def render(self, html):
        """Render *html* now, as the idle callback would."""
        self.html = html
        self.do_render()


for _name, _member in vars(Renderer).items():
    if isinstance(_member, FunctionType | staticmethod) and not hasattr(
        _RendererAdapter, _name,
    ):
        setattr(_RendererAdapter, _name, _member)


def _loaded(pos):
    """Return an adapter whose first render has fully loaded at *pos*."""
    renderer = _RendererAdapter(pos)
    renderer.render(HEAD.format("one"))
    renderer.webview.finish_load()
    return renderer


def test_first_load_restores_scroll_once_loaded():
    """A fresh document is scrolled to the editor position after loading."""
    renderer = _loaded(0.4)

    assert renderer.webview.scroll == 0.4


def test_reload_with_unchanged_position_restores_scroll():
    """A theme/style change reloads the page but the position is the same."""
    renderer = _loaded(0.4)

    renderer.style = "other.css"  # a different render context: full reload
    renderer._loaded_context = None
    renderer.render(HEAD.format("one"))
    renderer.webview.finish_load()

    assert renderer.webview.loads == 2
    assert renderer.webview.scroll == 0.4


def test_typing_at_end_of_document_keeps_preview_at_the_end():
    """The position stays 1.0 while the content grows below the preview."""
    renderer = _loaded(1.0)

    renderer.render(HEAD.format("one two"))

    assert renderer.webview.patches == 1
    assert renderer.webview.scroll == 1.0


def test_unchanged_rerender_does_not_stomp_manual_preview_scroll():
    """Re-rendering identical content leaves the user's own scroll alone."""
    renderer = _loaded(0.4)
    renderer.webview.scroll = 0.7  # scrolled by hand in the preview

    renderer.render(HEAD.format("one"))

    assert renderer.webview.patches == 1
    assert renderer.webview.scroll == 0.7


def test_editor_scroll_is_applied_to_preview():
    """Moving the editor scrolls the preview and survives a re-render."""
    renderer = _loaded(0.4)

    renderer.scroll_to_position(0.6)
    renderer.render(HEAD.format("one"))

    assert renderer.webview.scroll == 0.6
