"""Direct Markdown-to-HTML preview using mistune (no RST/docutils).

Unlike the ``m2r2``-based parser, which converts Markdown to
reStructuredText and renders that through docutils, this renders
GitHub-flavored Markdown and Mistune's built-in extensions straight to HTML
via mistune.
"""

import re

from formiko.utils import Undefined

_TASK_ITEM_RE = re.compile(r"^\[([ xX])\]\s+")
_MISTUNE_PLUGINS = [
    "table",
    "strikethrough",
    "task_lists",
    "url",
    "abbr",
    "def_list",
    "footnotes",
    "mark",
    "insert",
    "superscript",
    "subscript",
    "math",
    "ruby",
    "spoiler",
    "speedup",
]

try:
    import mistune

    if hasattr(mistune, "create_markdown"):

        def _make_markdown():
            return mistune.create_markdown(
                escape=False,
                plugins=_MISTUNE_PLUGINS,
            )

    else:
        # mistune < 2.0 (e.g. the 0.8.4 pinned as a transitive dependency
        # of m2r2): tables, strikethrough and bare-URL autolinking are
        # already part of its default grammar; only GFM task-list
        # checkboxes need adding by hand.
        class _TaskListRenderer(mistune.Renderer):
            """Renderer adding GFM task-list checkboxes to list items."""

            def list_item(self, text):
                """Render ``<li>``, converting a leading task marker."""
                match = _TASK_ITEM_RE.match(text)
                if not match:
                    return super().list_item(text)
                checked = " checked" if match.group(1) != " " else ""
                rest = text[match.end():]
                box = f'<input type="checkbox" disabled{checked}> '
                return f"<li>{box}{rest}</li>\n"

        def _make_markdown():
            return mistune.Markdown(renderer=_TaskListRenderer(escape=False))

    class MistunePreview:
        """Render Markdown directly to HTML via mistune, bypassing RST."""

        def __init__(self) -> None:
            self._markdown = _make_markdown()

        def to_html(self, text: str, tab_width: int = 8) -> str:
            """Convert Markdown *text* to a full HTML document."""
            body = self._markdown(text.expandtabs(tab_width))
            return (
                "<html><head><meta charset='utf-8'></head>"
                f"<body>{body}</body></html>"
            )

except ImportError:

    class MistunePreview(Undefined):  # type: ignore[no-redef]
        """Not imported MistunePreview."""
