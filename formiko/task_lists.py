"""Obsidian-style task list markers rendered as Unicode symbols.

A list item starting with ``[x]``, ``[ ]``, ``[?]`` ... gets the marker
replaced by a plain Unicode symbol, so it looks the same with every
writer and without any CSS. Works for reStructuredText and (through
m2r2, which keeps the marker as literal text) for Markdown as well.
"""

import re

from docutils import nodes
from docutils.parsers.rst import Parser as RstParser
from docutils.transforms import Transform

#: ``(marker, state name, symbol)``. Markers are case sensitive; synonyms
#: are added below.
_TASK_STATES = (
    (" ", "todo", "☐"),  # ☐
    ("x", "done", "☑"),  # ☑
    ("/", "incomplete", "◐"),  # ◐
    ("-", "canceled", "☒"),  # ☒
    (">", "forwarded", "➔"),  # ➔
    ("<", "scheduling", "◷"),  # ◷
    ("?", "question", "⁇"),  # ⁇
    ("!", "important", "‼"),  # ‼
    ("*", "star", "★"),  # ★
    ('"', "quote", "❝"),  # ❝
    ("l", "location", "⌖"),  # ⌖
    ("b", "bookmark", "⚑"),  # ⚑
    ("i", "information", "ⓘ"),  # ⓘ
    ("I", "idea", "✦"),  # ✦
    ("$", "money", "$"),
    ("€", "money", "€"),  # €
    ("p", "pros", "\u2295"),  # circled plus
    ("c", "cons", "\u2296"),  # circled minus
    ("f", "fire", "♨"),  # ♨
    ("k", "key", "⚿"),  # ⚿
    ("w", "win", "✪"),  # ✪
    ("u", "up", "▲"),  # ▲
    ("d", "down", "▼"),  # ▼
)

#: Marker character -> Unicode symbol.
TASK_MARKERS = {marker: symbol for marker, _name, symbol in _TASK_STATES}
#: Marker character -> state name used for the ``task-<name>`` class.
TASK_NAMES = {marker: name for marker, name, _symbol in _TASK_STATES}

for _alias, _marker in (("X", "x"), ("S", "$")):
    TASK_MARKERS[_alias] = TASK_MARKERS[_marker]
    TASK_NAMES[_alias] = TASK_NAMES[_marker]

_TASK_ITEM = re.compile(
    r"\[([{}])\](?:\s+|$)".format(re.escape("".join(TASK_MARKERS))),
)


class TaskListTransform(Transform):
    """Replace ``[x]``-like markers at the start of list items by symbols."""

    default_priority = 100

    def apply(self, **kwargs):
        """Walk all list items and rewrite the ones with a task marker."""
        for item in self.document.findall(nodes.list_item):
            self._rewrite_item(item)

    @staticmethod
    def _rewrite_item(item):
        if not item.children or not isinstance(item[0], nodes.paragraph):
            return
        paragraph = item[0]
        if not paragraph.children or not isinstance(paragraph[0], nodes.Text):
            return
        text = paragraph[0].astext()
        match = _TASK_ITEM.match(text)
        if match is None:
            return
        marker = match.group(1)
        end = match.end()
        rest = text[end:]
        symbol = TASK_MARKERS[marker]
        if rest or len(paragraph.children) > 1:
            symbol += " "
        paragraph[0] = nodes.Text(symbol + rest)
        item["classes"].append(f"task-{TASK_NAMES[marker]}")
        if "task-list" not in item.parent["classes"]:
            item.parent["classes"].append("task-list")


class TaskListRstParser(RstParser):
    """reStructuredText parser which also handles task list markers."""

    def get_transforms(self):
        """Add :class:`TaskListTransform` to the parser transforms."""
        return [*super().get_transforms(), TaskListTransform]
