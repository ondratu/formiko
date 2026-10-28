"""Tests for JSONPath filtering helpers in :mod:`formiko.json_preview`."""

from concurrent.futures import Future

import gi
import pytest

gi.require_version("Gtk", "4.0")

from jsonpath_ng.exceptions import JsonPathParserError  # noqa: E402

from formiko import json_preview  # noqa: E402
from formiko.json_preview import (  # noqa: E402
    JSONPreview,
    _datum_path,
    compute_jsonpath_view,
)

DATA = {"a": {"b": {"c": 1}}, "list": [{"x": 1}, {"x": 2}], "s": "t"}


def _matches(expression):
    from jsonpath_ng.ext import parse

    return parse(expression).find(DATA)


def test_datum_path_is_plain_dot_notation():
    """Nested paths are not wrapped in parentheses."""
    assert _datum_path(_matches("$.a.b.c")[0]) == "a.b.c"


def test_datum_path_of_top_level_key():
    """A single-level path is just the key."""
    assert _datum_path(_matches("$.s")[0]) == "s"


def test_datum_path_includes_indexes():
    """List indexes are part of the path."""
    paths = [_datum_path(m) for m in _matches("$.list[*].x")]
    assert paths == ["list.[0].x", "list.[1].x"]


@pytest.mark.parametrize("expression", [None, "", "   "])
def test_blank_expression_returns_everything(expression):
    """No filter expands only the root and highlights nothing."""
    data, highlights, expands, expr = compute_jsonpath_view(DATA, expression)
    assert data is DATA
    assert highlights == []
    assert expands == {""}
    assert expr == ""


def test_expression_highlights_and_expands_ancestors_and_descendants():
    """Matches are highlighted, ancestors and descendants expanded."""
    _, highlights, expands, expr = compute_jsonpath_view(DATA, "$.a.b")
    assert highlights == ["a.b"]
    assert expr == "$.a.b"
    assert {"", "a", "a.b", "a.b.c"} <= expands
    assert "list" not in expands


def test_descendants_of_lists_use_index_notation():
    """Descendant paths of lists use ``[i]`` segments."""
    _, _, expands, _ = compute_jsonpath_view(DATA, "$.list")
    assert {"list", "list.[0]", "list.[0].x", "list.[1].x"} <= expands


def test_root_match_expands_all_descendants():
    """Matching the root with a relative path still yields sub-paths."""
    _, highlights, expands, _ = compute_jsonpath_view(DATA, "$.s")
    assert highlights == ["s"]
    assert "s" in expands


def test_invalid_expression_raises_parser_error():
    """A syntax error raises JsonPathParserError."""
    with pytest.raises(JsonPathParserError):
        compute_jsonpath_view(DATA, "$.[[[")


def test_runtime_failure_is_wrapped(monkeypatch):
    """Unexpected errors from jsonpath become a "Filter error"."""

    def explode(_expression):
        class _Expr:
            def find(self, _data):
                msg = "boom"
                raise RuntimeError(msg)

        return _Expr()

    monkeypatch.setattr(json_preview, "json_parse", explode)
    with pytest.raises(JsonPathParserError, match="Filter error"):
        compute_jsonpath_view(DATA, "$.a")


class _InlineExecutor:
    """Run submitted tasks synchronously."""

    def submit(self, task):
        future = Future()
        try:
            future.set_result(task())
        except Exception as e:
            future.set_exception(e)
        return future


@pytest.fixture
def preview(monkeypatch):
    """Return a JSONPreview with sync executor and recorded idle calls."""
    monkeypatch.setattr(json_preview, "_EXECUTOR", _InlineExecutor())
    calls = []
    monkeypatch.setattr(
        json_preview.GLib,
        "idle_add",
        lambda func, *args: calls.append((func, args)),
    )
    obj = JSONPreview()
    obj._json_data = DATA
    obj.calls = calls
    return obj


def test_apply_path_filter_renders_matches(preview):
    """A valid filter schedules a render with the match count."""
    preview.apply_path_filter("$.list[*].x")
    func, args = preview.calls[-1]
    assert func == preview._render
    assert args[1] == ["list.[0].x", "list.[1].x"]
    assert args[-1] == 2


def test_apply_path_filter_none_clears_filter(preview):
    """None expression renders everything with zero matches."""
    preview.apply_path_filter(None)
    func, args = preview.calls[-1]
    assert func == preview._render
    assert args[-1] == 0


def test_apply_path_filter_error_shows_dialog_and_resets(preview):
    """An invalid expression shows an error and renders unfiltered."""
    preview.apply_path_filter("$.[[[")
    assert preview.calls[0][0] == preview._show_error_dialog
    func, args = preview.calls[-1]
    assert func == preview._render
    assert args[1] == []
    assert args[-1] == 0


@pytest.mark.parametrize(
    ("value", "css_class", "text"),
    [
        ("a<b", "jstr", '"a&lt;b"'),
        (True, "jbool", "true"),
        (False, "jbool", "false"),
        (None, "jnull", "null"),
        (12, "jnum", "12"),
        (1.5, "jnum", "1.5"),
    ],
)
def test_leaf_to_html_by_type(value, css_class, text):
    """Each primitive gets its own class and text."""
    html = JSONPreview._leaf_to_html(value, "p", False)
    assert f'class="{css_class}"' in html
    assert f">{text}</span>" in html
    assert 'data-jpath="p"' in html


def test_leaf_to_html_highlight_and_path_escape():
    """Highlight adds a class and the path is escaped."""
    html = JSONPreview._leaf_to_html(1, 'a"b', True)
    assert "jnum jhighlight" in html
    assert 'data-jpath="a&quot;b"' in html
