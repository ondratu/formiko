"""Tests for the pure DOM and text helpers of the litehtml backend."""

from types import SimpleNamespace

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

pytest.importorskip("litehtmlpy", reason="needs the litehtmlpy package")

from formiko.litehtml_browser import (  # noqa: E402
    _build_text_index,
    _collect_selection,
    _find_all_matches,
    _find_element_by_anchor,
    _find_link_href,
    _hex_to_rgb,
)


class Node:
    """Fake litehtmlpy element."""

    def __init__(self, tag="div", attrs=None, children=(), text=None,
                 box=(0, 0, 0, 0)):
        self.tag = tag
        self.attrs = attrs or {}
        self._children = list(children)
        self.text = text
        self.box = box
        self._parent = None
        for child in self._children:
            child._parent = self

    def get_tagName(self):  # noqa: N802
        return self.tag

    def get_attr(self, name, default):
        return self.attrs.get(name, default)

    def parent(self):
        return self._parent

    def children(self):
        return self._children

    def is_text(self):
        return self.text is not None

    def get_text(self):
        return self.text

    def get_placement(self):
        x, y, w, h = self.box
        return SimpleNamespace(
            x=SimpleNamespace(value=x),
            y=SimpleNamespace(value=y),
            width=SimpleNamespace(value=w),
            height=SimpleNamespace(value=h),
        )


def Text(text, box):  # noqa: N802, D103
    return Node("", text=text, box=box)


@pytest.mark.parametrize(
    ("color", "rgb"),
    [
        ("#000000", (0, 0, 0)),
        ("#ffffff", (1, 1, 1)),
        ("ff0000", (1, 0, 0)),
        ("#336699", (0x33 / 255, 0x66 / 255, 0x99 / 255)),
    ],
)
def test_hex_to_rgb(color, rgb):
    """Hex colours become 0..1 float triplets, with or without ``#``."""
    assert _hex_to_rgb(color) == pytest.approx(rgb)


def test_find_link_href_on_link_itself():
    """The link element returns its own href."""
    link = Node("a", {"href": "http://x"})
    assert _find_link_href(link) == "http://x"


def test_find_link_href_from_nested_element():
    """A child of the link finds the ancestor's href."""
    inner = Node("b")
    Node("a", {"href": "#top"}, [Node("i", children=[inner])])
    assert _find_link_href(inner) == "#top"


def test_find_link_href_skips_anchor_without_href():
    """A named anchor is not a link."""
    inner = Node("b")
    Node("a", {"name": "x"}, [inner])
    assert _find_link_href(inner) is None


def test_find_link_href_none_input():
    """No element means no link."""
    assert _find_link_href(None) is None


def test_find_element_by_anchor_matches_id_and_name():
    """Both ``id`` and legacy ``name`` are matched, depth first."""
    target = Node("h1", {"id": "intro"})
    legacy = Node("a", {"name": "old"})
    root = Node(children=[Node(children=[target]), legacy])
    assert _find_element_by_anchor(root, "intro") is target
    assert _find_element_by_anchor(root, "old") is legacy


def test_find_element_by_anchor_includes_root():
    """The starting element itself can match."""
    root = Node(attrs={"id": "r"})
    assert _find_element_by_anchor(root, "r") is root


def test_find_element_by_anchor_missing():
    """Unknown anchors and None roots give None."""
    assert _find_element_by_anchor(Node(), "zz") is None
    assert _find_element_by_anchor(None, "zz") is None


def _doc():
    return Node(children=[
        Node("p", children=[
            Text("Hello", (0, 0, 40, 10)),
            Text(" ", (40, 0, 5, 10)),
            Text("world", (45, 0, 40, 10)),
        ]),
        Node("p", children=[Text("  second  ", (0, 20, 50, 10))]),
    ])


def test_collect_selection_picks_overlapping_text():
    """Only text nodes touching the rectangle are returned, in order."""
    boxes, text = _collect_selection(_doc(), 30, 0, 60, 5)
    assert boxes == [(0, 0, 40, 10), (40, 0, 5, 10), (45, 0, 40, 10)]
    assert text == "Hello world"


def test_collect_selection_excludes_non_overlapping():
    """A rectangle on the second line selects only that line."""
    boxes, text = _collect_selection(_doc(), 0, 19, 10, 25)
    assert boxes == [(0, 20, 50, 10)]
    assert text == "second"


def test_collect_selection_edges_do_not_count():
    """Touching edges is not an overlap."""
    boxes, text = _collect_selection(_doc(), 85, 0, 100, 10)
    assert (boxes, text) == ([], "")


def test_collect_selection_none_root():
    """None root yields nothing."""
    assert _collect_selection(None, 0, 0, 10, 10) == ([], "")


def test_build_text_index_concatenates_without_separators():
    """The text keeps its original spacing and spans map to boxes."""
    full, spans = _build_text_index(_doc())
    assert full == "Hello world" + "  second  "
    assert spans[0] == (0, 5, (0, 0, 40, 10))
    assert spans[1] == (5, 6, (40, 0, 5, 10))
    assert spans[-1] == (11, 21, (0, 20, 50, 10))


def test_build_text_index_skips_empty_text_and_none():
    """Empty text nodes produce no span."""
    root = Node(children=[Text("", (0, 0, 1, 1)), Text("a", (1, 1, 2, 2))])
    assert _build_text_index(root) == ("a", [(0, 1, (1, 1, 2, 2))])
    assert _build_text_index(None) == ("", [])


def test_find_all_matches_maps_to_boxes():
    """Matches are case-insensitive and may span several nodes."""
    full, spans = _build_text_index(_doc())
    matches = _find_all_matches(full, spans, "O W")
    assert matches == [[(0, 0, 40, 10), (40, 0, 5, 10), (45, 0, 40, 10)]]


def test_find_all_matches_multiple_non_overlapping():
    """Every non-overlapping hit is reported once."""
    root = Node(children=[Text("aaaa", (0, 0, 4, 1))])
    full, spans = _build_text_index(root)
    assert len(_find_all_matches(full, spans, "aa")) == 2


@pytest.mark.parametrize("query", ["", "zzz"])
def test_find_all_matches_empty_or_missing(query):
    """Empty queries and misses give no matches."""
    full, spans = _build_text_index(_doc())
    assert _find_all_matches(full, spans, query) == []
