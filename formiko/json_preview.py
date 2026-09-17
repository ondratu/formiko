"""JSON preview with folding, expanding, and highlighting in WebKit."""

import contextlib
from concurrent.futures import ThreadPoolExecutor
from html import escape
from importlib.resources import files
from json import dumps, loads
from typing import Any

from gi.repository import GLib, Gtk
from jsonpath_ng.exceptions import JsonPathParserError
from jsonpath_ng.ext import parse as json_parse
from jsonpath_ng.jsonpath import Root

from formiko.browser import EVENT_LOAD_FINISHED, BrowserView

JS_EXPAND_ALL = """
document.querySelectorAll('.jblock').forEach(
  el => el.classList.remove('collapsed')
);
"""

JS_COLLAPSE_ALL = """
document.querySelectorAll('.jblock:not([data-jpath=""])').forEach(
  el => el.classList.add('collapsed')
);
"""

_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def _datum_path(datum) -> str:
    """Return *datum*'s path as our own plain dot notation (e.g. "a.b").

    ``str(datum.full_path)`` can't be used for this: jsonpath_ng wraps
    paths 2+ levels deep in parentheses (e.g. "((a.b).c)" for $.a.b.c),
    which never matched ``_value_to_html``'s ``data-jpath`` and silently
    broke expand/highlight for any nested match. Built instead by
    joining each level's own single-segment ``str(path)`` root-to-leaf.
    """
    segments = []
    current = datum
    while current is not None and not isinstance(current.path, Root):
        segments.append(str(current.path))
        current = current.context
    path = ""
    for segment in reversed(segments):
        path = f"{path}.{segment}" if path else segment
    return path


def compute_jsonpath_view(json_data, expression: str | None):  # noqa: C901
    """Return (data, highlights, expands, expr) for given JSONPath expression.

    - highlights: list[str] of matched node paths
    - expands: set[str] of all paths to expand
      (ancestors + matched + descendants)
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
        msg = "Filter error"
        raise JsonPathParserError(msg) from e

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
        while current is not None and not isinstance(current.path, Root):
            expands.add(_datum_path(current))
            current = current.context

        # expand matched + descendants
        p = _datum_path(m)
        expands |= collect_descendant_paths(m.value, p)

        highlights.append(p)

    return json_data, highlights, expands, expression


class JSONPreview:
    """Manage JSON parsing, filtering, and rendering.

    Provides a collapsible and highlighted HTML preview.
    """

    def __init__(self, collapse_lines: int | None = None) -> None:
        self.collapse_lines = collapse_lines
        self._css: str | None = None
        self._js: str | None = None
        self._json_data: Any = None

        # These are set externally by the caller (e.g., Renderer)
        self.webview: BrowserView | None = None
        self._win: Gtk.Window | None = None

        self._fold_handler_id: int | None = None
        self._highlight_handler_id: int | None = None
        self._tab_width = 2
        self.filter_callback = None  # optional callback: (expr, match_count)

    # -------------------------- Public API ---------------------------------

    def to_html(self, text: str, tab_width: int = 2) -> str:
        """Parse JSON text and return the initial full HTML representation.

        The parsed data is stored for later filtering.  A one-shot
        ``load-changed`` handler is registered so that *jsonfold.js* is
        injected via :meth:`inject_fold_js` after the renderer loads the
        returned HTML — necessary because ``enable-javascript-markup`` is
        disabled for XSS protection.
        """
        self._json_data = loads(text)
        self._tab_width = tab_width
        self._schedule_fold_injection()
        return self._generate_html(self._json_data)

    def inject_fold_js(self, webview: BrowserView) -> None:
        """Inject jsonfold.js into the current page via a script run.

        Called after the page loads instead of relying on the inline
        ``<script>`` tag, which is blocked by the WebKit backend's XSS
        protection setting ``enable-javascript-markup = False``.  A no-JS
        backend simply renders the JSON tree fully expanded, without
        folding.
        """
        if not webview.can_run_script():
            return
        _, js = self._resources()
        webview.run_script(js)

    def expand_all(self) -> None:
        """Expand all collapsed elements."""
        if self.webview and self.webview.can_run_script():
            self.webview.run_script(JS_EXPAND_ALL)

    def collapse_all(self) -> None:
        """Collapse all elements except root."""
        if self.webview and self.webview.can_run_script():
            self.webview.run_script(JS_COLLAPSE_ALL)

    def _schedule_fold_injection(self) -> None:
        """Register a one-shot load-finished handler on the webview.

        Injects the fold JS after the renderer loads the initial render.
        Any previous pending handler is disconnected first so that rapid
        re-renders do not accumulate stale handlers.
        """
        if self.webview is None or not self.webview.can_run_script():
            return
        if self._fold_handler_id is not None:
            with contextlib.suppress(Exception):
                self.webview.disconnect(self._fold_handler_id)
            self._fold_handler_id = None

        def on_loaded() -> None:
            self.inject_fold_js(self.webview)
            if self._fold_handler_id is not None:
                self.webview.disconnect(self._fold_handler_id)
                self._fold_handler_id = None

        self._fold_handler_id = self.webview.connect(
            EVENT_LOAD_FINISHED, on_loaded,
        )

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
        dialog = Gtk.AlertDialog.new("Invalid JSONPath Expression")
        dialog.set_detail(message)
        dialog.show(self._win)
        return False

    def _generate_html(
        self,
        data: Any,
        expands: set[str] | None = None,
        highlights: frozenset[str] = frozenset(),
    ) -> str:
        """Generate the full HTML document for the given JSON data.

        *expands*/*highlights* bake a JSONPath filter's result directly
        into which nodes render collapsed/highlighted, so filtering works
        under a backend without scripting too (can_run_script() False,
        e.g. litehtml). *expands* is None for the unfiltered view, which
        keeps the original line-count-based auto-collapse heuristic.
        """
        pretty = dumps(
            data,
            indent=self._tab_width,
            sort_keys=True,
            ensure_ascii=False,
        )
        line_count = pretty.count("\n") + 1
        collapse = (
            self.collapse_lines is not None
            and line_count > self.collapse_lines
        )
        body = self._value_to_html(data, collapse, 0, "", expands, highlights)
        css, _ = self._resources()
        return (
            "<html><head><meta charset='utf-8'>"
            f"<style>{css}</style>"
            "</head><body><pre>" + body + "</pre>"
            "</body></html>"
        )

    def _resources(self) -> tuple[str, str]:
        """Load CSS and JS resources for folding/expanding."""
        if self._css is None or self._js is None:
            data_dir = files("formiko.data")
            self._css = (data_dir / "jsonfold.css").read_text(encoding="utf-8")
            self._js = (data_dir / "jsonfold.js").read_text(encoding="utf-8")
        return self._css, self._js

    @staticmethod
    def _is_collapsed(
        collapse: bool, level: int, path: str, expands: set[str] | None,
    ) -> bool:
        """Whether the node at *path* should render collapsed.

        With a JSONPath filter active (*expands* is not None), collapse
        everything except the paths it says to expand, ignoring the
        generic line-count heuristic - see _generate_html.
        """
        if expands is not None:
            return level > 0 and path not in expands
        return collapse and level > 0

    def _value_to_html(
        self,
        value: Any,
        collapse: bool,
        level: int,
        path: str,
        expands: set[str] | None = None,
        highlights: frozenset[str] = frozenset(),
    ) -> str:
        if isinstance(value, dict):
            entries = [
                (f"{path}.{key}" if path else key, escape(str(key)), val)
                for key, val in value.items()
            ]
            return self._block_to_html(
                entries, "{", "}", collapse, level, path, expands, highlights,
            )
        if isinstance(value, list):
            entries = [
                (f"{path}.[{i}]" if path else f"[{i}]", None, val)
                for i, val in enumerate(value)
            ]
            return self._block_to_html(
                entries, "[", "]", collapse, level, path, expands, highlights,
            )
        return self._leaf_to_html(value, path, path in highlights)

    def _block_to_html(
        self,
        # (child path, escaped dict key or None for a list item, child value)
        entries: list[tuple[str, str | None, Any]],
        open_char: str,
        close_char: str,
        collapse: bool,
        level: int,
        path: str,
        expands: set[str] | None,
        highlights: frozenset[str],
    ) -> str:
        """Render a dict or list (JSON "block") and its children.

        Both store ``data-jpath`` for JSONPath lookup, use the same
        collapse/highlight/toggler shell, and differ only in the
        bracket characters and whether a child gets a ``jkey`` label -
        *entries* already carries that difference, computed by the two
        isinstance branches in :meth:`_value_to_html`.
        """
        css_classes = ["jblock"]
        if self._is_collapsed(collapse, level, path, expands):
            css_classes.append("collapsed")
        if path in highlights:
            css_classes.append("jhighlight")
        items = [
            self._item_to_html(key, self._value_to_html(
                val, collapse, level + 1, child_path, expands, highlights,
            ))
            for child_path, key, val in entries
        ]
        children = "".join(items)
        return (
            f'<div class="{" ".join(css_classes)}" data-jpath="{path}">'
            f"<span class='jtoggler'></span>{open_char}"
            f"<div class='children'>{children}</div>{close_char}</div>"
        )

    @staticmethod
    def _item_to_html(key: str | None, child_html: str) -> str:
        if key is None:  # list item: no key label
            return f'<div class="jitem">{child_html}</div>'
        return (
            f'<div class="jitem"><span class="jkey">"{key}"</span>: '
            f"{child_html}</div>"
        )

    @staticmethod
    def _leaf_to_html(value: Any, path: str, is_highlighted: bool) -> str:
        """Render a primitive value: a span assigning its class and path."""
        if isinstance(value, str):
            base_class, text = "jstr", f'"{escape(value)}"'
        elif value is True or value is False:
            base_class, text = "jbool", str(value).lower()
        elif value is None:
            base_class, text = "jnull", "null"
        else:
            base_class, text = "jnum", str(value)
        if is_highlighted:
            base_class = f"{base_class} jhighlight"
        return f'<span class="{base_class}" data-jpath="{path}">{text}</span>'

    def _render(
        self,
        data: Any,
        highlights: list[str],
        expands: set[str],
        expr: str,
        count: int,
    ) -> bool:
        """Generate and load HTML with the filter's expand/highlight state."""
        html = self._generate_html(
            data,
            expands=expands if expr else None,
            highlights=frozenset(highlights),
        )

        if not self.webview:
            return False

        # Prevent leftover handlers from triggering multiple times
        if self._highlight_handler_id is not None:
            self.webview.disconnect(self._highlight_handler_id)
            self._highlight_handler_id = None

        def on_load_finished() -> None:
            # jsonfold.js must be injected first because inline <script>
            # is blocked by enable-javascript-markup = False (XSS fix).
            # No further script is needed for the filter itself - the
            # loaded HTML already has the right nodes collapsed/
            # highlighted (see _generate_html) - only the interactive
            # click-to-toggle behavior jsonfold.js adds is JS-only.
            self.inject_fold_js(self.webview)
            if self._highlight_handler_id is not None:
                self.webview.disconnect(self._highlight_handler_id)
                self._highlight_handler_id = None

        self._highlight_handler_id = self.webview.connect(
            EVENT_LOAD_FINISHED, on_load_finished,
        )
        self.webview.load(html, "text/html", "file:///")

        if self.filter_callback:
            self.filter_callback(expr, count)

        return False
