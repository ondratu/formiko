"""JSON preview with folding, expanding, and highlighting in WebKit."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
from importlib.resources import files
from json import dumps, loads
from typing import Any

from gi.repository import GLib, Gtk
from gi.repository.Gtk import MessageDialog, MessageType
from gi.repository.WebKit2 import LoadEvent, WebView

from jsonpath_ng.exceptions import JsonPathParserError
from jsonpath_ng.ext import parse as json_parse

JS_EXPAND_HIGHLIGHT = r"""
const highlights = __HIGHLIGHTS__;
const expands = __EXPANDS__;

document.querySelectorAll('.jblock').forEach(el => el.classList.add('collapsed'));

expands.forEach(p => {
  const el = document.querySelector(`[data-jpath="${p}"]`);
  if (el) el.classList.remove('collapsed');
});

highlights.forEach(p => {
  const el = document.querySelector(`[data-jpath="${p}"]`);
  if (el) el.classList.add('jhighlight');
});
"""

JS_EXPAND_ALL = """
document.querySelectorAll('.jblock').forEach(
  el => el.classList.remove('collapsed')
);
"""

_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def compute_jsonpath_view(json_data, expression: str | None):
    """Return (data, highlights, expands, expr) for a given JSONPath expression.

    - highlights: list[str] of matched node paths
    - expands: set[str] of all paths to expand (ancestors + matched + descendants)
    - expr: the original expression ('' if none/blank)
    """
    if not expression or not expression.strip():
        return json_data, [], {""}, ""

    try:
        expr = json_parse(expression)
        matches = expr.find(json_data)
    except JsonPathParserError:
        raise
    except Exception as e:
        raise JsonPathParserError("Filter error") from e

    def collect_descendant_paths(val, base_path=""):
        paths = {base_path}
        if isinstance(val, dict):
            for k, v in val.items():
                child = f"{base_path}.{k}" if base_path else k
                paths |= collect_descendant_paths(v, child)
        elif isinstance(val, list):
            for i, v in enumerate(val):
                child = f"{base_path}.[{i}]" if base_path else f"[{i}]"
                paths |= collect_descendant_paths(v, child)
        return paths

    highlights: list[str] = []
    expands: set[str] = {""}  # include root so the tree opens from top

    for m in matches:
        # expand ancestors
        current = m
        while current:
            p = str(current.full_path)
            if p == "$":
                p = ""
            expands.add(p)
            current = current.context

        # expand matched + descendants
        p = str(m.full_path)
        p = "" if p == "$" else p
        expands |= collect_descendant_paths(m.value, p)

        highlights.append(p)

    return json_data, highlights, expands, expression


class JSONPreview:
    """Manage JSON parsing, filtering, and rendering.

    Provides a collapsible and highlighted HTML preview.
    """

    def __init__(self, collapse_lines: int = 100) -> None:
        self.collapse_lines = collapse_lines
        self._css: str | None = None
        self._js: str | None = None
        self._json_data: Any = None

        # These are set externally by the caller (e.g., Renderer)
        self.webview: WebView | None = None
        self._win: Gtk.Window | None = None

        self._tab_width = 2
        self.filter_callback = None  # optional callback: (expr, match_count) -> None

    # -------------------------- Public API ---------------------------------

    def to_html(self, text: str, tab_width: int = 2) -> str:
        """Parse JSON text and return the initial full HTML representation.

        The parsed data is stored for later filtering.
        """
        self._json_data = loads(text)
        self._tab_width = tab_width
        return self._generate_html(self._json_data)

    def apply_path_filter(self, expression: str | None) -> None:
        """Filter JSON by JSONPath and update the preview asynchronously.

        A callback is fired with ``(expression, match_count)`` when done.

        ``expression`` may be ``None`` or empty to clear any existing filter
        and fully expand the JSON tree.
        """

        def _task():
            return compute_jsonpath_view(self._json_data, expression)

        def _done(fut):
            try:
                data, highlights, expands, expr = fut.result()
            except JsonPathParserError as e:
                GLib.idle_add(self._show_error_dialog, str(e))
                data, highlights, expands, expr = self._json_data, [], {""}, ""

            GLib.idle_add(
                self._render,
                data,
                highlights,
                expands,
                expr,
                len(highlights),
            )

        _EXECUTOR.submit(_task).add_done_callback(_done)

    # -------------------------- Internals ----------------------------------

    def _show_error_dialog(self, message: str) -> bool:
        """Display an error dialog when JSONPath parsing fails."""
        dialog = MessageDialog(
            transient_for=self._win,
            modal=True,
            message_type=MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Invalid JSONPath Expression",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
        return False

    def _generate_html(self, data: Any) -> str:
        """Generate the full HTML document for the given JSON data."""
        pretty = dumps(
            data,
            indent=self._tab_width,
            sort_keys=True,
            ensure_ascii=False,
        )
        line_count = pretty.count("\n") + 1
        collapse = line_count > self.collapse_lines
        body = self._value_to_html(data, collapse, 0, "")
        css, js = self._resources()
        return (
            "<html><head><meta charset='utf-8'>"
            f"<style>{css}</style>"
            "</head><body><pre>"
            + body
            + "</pre>"
            f"<script>{js}</script>"
            "</body></html>"
        )

    def _resources(self) -> tuple[str, str]:
        """Load CSS and JS resources for folding/expanding."""
        if self._css is None or self._js is None:
            data_dir = files("formiko.data")
            self._css = (data_dir / "jsonfold.css").read_text(encoding="utf-8")
            self._js = (data_dir / "jsonfold.js").read_text(encoding="utf-8")
        return self._css, self._js

    def _value_to_html(
        self,
        value: Any,
        collapse: bool,
        level: int,
        path: str,
    ) -> str:
        # Dictionary: use dot notation for child keys, store data-jpath for JSONPath lookup
        if isinstance(value, dict):
            css_classes = ["jblock"]
            if collapse and level > 0:
                css_classes.append("collapsed")
            items = []
            for _key, val in value.items():
                new_path = f"{path}.{_key}" if path else _key
                child_html = self._value_to_html(val, collapse, level + 1, new_path)
                items.append(
                    '<div class="jitem">'
                    '<span class="jkey">'
                    f'"{escape(str(_key))}"'
                    "</span>: "
                    f"{child_html}"
                    "</div>"
                )
            children = "".join(items)
            return (
                f'<div class="{" ".join(css_classes)}" data-jpath="{path}">'
                "<span class='jtoggler'></span>{"
                f"<div class='children'>{children}</div>}}</div>"
            )

        # List: use [i] notation, and dot prefix if not at the root
        if isinstance(value, list):
            css_classes = ["jblock"]
            if collapse and level > 0:
                css_classes.append("collapsed")
            items = []
            for i, v in enumerate(value):
                new_path = f"{path}.[{i}]" if path else f"[{i}]"
                child_html = self._value_to_html(v, collapse, level + 1, new_path)
                items.append('<div class="jitem">' f"{child_html}" "</div>")
            children = "".join(items)
            return (
                f'<div class="{" ".join(css_classes)}" data-jpath="{path}">'
                '<span class="jtoggler"></span>['
                f'<div class="children">{children}</div>]</div>'
            )

        # Primitive values: wrap with a span, assign class by type, and store data-jpath
        if isinstance(value, str):
            esc = escape(value)
            return f'<span class="jstr" data-jpath="{path}">"{esc}"</span>'
        if value is True or value is False:
            val_str = str(value).lower()
            return f'<span class="jbool" data-jpath="{path}">{val_str}</span>'
        if value is None:
            return f'<span class="jnull" data-jpath="{path}">null</span>'
        return f'<span class="jnum" data-jpath="{path}">{value}</span>'

    def _render(
        self,
        data: Any,
        highlights: list[str],
        expands: set[str],
        expr: str,
        count: int,
    ) -> bool:
        """Generate and load HTML, then run JS to fold and highlight."""
        html = self._generate_html(data)

        if not self.webview:
            return False

        # Prevent leftover handlers from triggering multiple times
        if hasattr(self.webview, "highlight_handler_id"):
            self.webview.disconnect(self.webview.highlight_handler_id)

        def on_load_finished(webview: WebView, load_event: LoadEvent):
            if load_event == LoadEvent.FINISHED:
                if expr:
                    js = (
                        JS_EXPAND_HIGHLIGHT
                        .replace("__HIGHLIGHTS__", dumps(highlights))
                        .replace("__EXPANDS__", dumps(list(expands)))
                    )
                    webview.run_javascript(js)
                else:
                    webview.run_javascript(JS_EXPAND_ALL)

                if hasattr(webview, "highlight_handler_id"):
                    webview.disconnect(webview.highlight_handler_id)
                    del webview.highlight_handler_id

        handler_id = self.webview.connect("load-changed", on_load_finished)
        self.webview.highlight_handler_id = handler_id
        self.webview.load_html(html, "file:///")

        if self.filter_callback:
            self.filter_callback(expr, count)

        return False
