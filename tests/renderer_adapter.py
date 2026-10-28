"""Duck-typed stand-in for :class:`formiko.renderer.Renderer`.

``Renderer`` is a ``Gtk.Overlay`` and cannot be built without a display
(the constructor segfaults), so tests borrow methods from the class and run
them against this adapter. Keep the knowledge of which private attributes
``render_output`` reads, including the name-mangled ones, in this one place.

Import it after ``gi.require_version`` has been called.
"""

from types import SimpleNamespace

from formiko.renderer import PARSERS, WRITERS, Renderer


def make_render_adapter(parser="rst", writer="html4", **overrides):
    """Return an adapter that ``Renderer.render_output`` can run against."""
    adapter = SimpleNamespace(
        src="Title\n=====\n\ntext\n",
        file_name="/tmp/x.rst",  # noqa: S108
        tab_width=8,
        style="",
        parser_instance=PARSERS[parser]["class"](),
        writer_instance=WRITERS[writer]["class"](),
        _embed_stylesheet=Renderer._embed_stylesheet,
    )
    adapter._Renderer__parser = PARSERS[parser]
    adapter._Renderer__writer = WRITERS[writer]
    for key, value in overrides.items():
        setattr(adapter, key, value)
    return adapter
