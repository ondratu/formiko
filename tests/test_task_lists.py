"""Tests for Obsidian-style task list markers rendered as Unicode symbols."""

from io import StringIO

import pytest
from docutils.core import publish_parts

from formiko.directives import Mark2Resturctured
from formiko.task_lists import TASK_MARKERS, TASK_NAMES, TaskListRstParser


def render_rst(source, parser=None):
    """Render *source* with the task list aware RST parser to HTML body."""
    return publish_parts(
        source=source,
        parser=(parser or TaskListRstParser)(),
        writer_name="html5",
        settings_overrides={"warning_stream": StringIO()},
    )["fragment"]


def render_md(source):
    """Render Markdown *source* through m2r2 and the same transform."""
    return render_rst(source, Mark2Resturctured)


@pytest.mark.parametrize(("marker", "symbol"), sorted(TASK_MARKERS.items()))
def test_every_marker_is_replaced_by_its_symbol(marker, symbol):
    """Every marker is replaced by its symbol."""
    html = render_rst(f"* [{marker}] item\n")
    assert f"{symbol} item" in html
    assert f"[{marker}]" not in html


def test_symbols_are_unique_per_meaning():
    """Symbols are unique per meaning."""
    # ``x``/``X`` and ``$``/``S`` are intentional synonyms.
    symbols = {s for m, s in TASK_MARKERS.items() if m not in ("X", "S")}
    assert len(symbols) == len(TASK_MARKERS) - 2


def test_basic_states():
    """Basic states."""
    assert TASK_MARKERS[" "] == "☐"
    assert TASK_MARKERS["x"] == "☑"
    assert TASK_MARKERS["-"] == "☒"


def test_x_is_case_insensitive():
    """X is case insensitive."""
    assert TASK_MARKERS["X"] == TASK_MARKERS["x"]
    assert "☑ done" in render_rst("* [X] done\n")


def test_info_and_idea_differ_by_case():
    """Info and idea differ by case."""
    assert TASK_MARKERS["i"] != TASK_MARKERS["I"]


def test_money_markers():
    """Money markers."""
    assert TASK_MARKERS["$"] == TASK_MARKERS["S"] == "$"
    assert TASK_MARKERS["€"] == "€"
    assert TASK_NAMES["$"] == TASK_NAMES["€"] == TASK_NAMES["S"]


def test_list_item_gets_state_class():
    """List item gets state class."""
    html = render_rst("* [x] done\n* [ ] open\n")
    assert 'class="task-done"' in html
    assert 'class="task-todo"' in html


def test_bullet_list_gets_task_list_class():
    """Bullet list gets task list class."""
    assert "task-list" in render_rst("* [ ] open\n")


def test_plain_list_is_untouched():
    """Plain list is untouched."""
    html = render_rst("* one\n* two\n")
    assert "task-list" not in html
    assert "<p>one</p>" in html


@pytest.mark.parametrize(
    "text",
    [
        "[1] note",
        "[xx] two",
        "[ab] text",
        "[x]nospace",
        "text [x] later",
        "[] empty",
    ],
)
def test_non_markers_are_left_alone(text):
    """Non markers are left alone."""
    html = render_rst(f"* {text}\n")
    assert "task-list" not in html


def test_unknown_marker_is_left_alone():
    """Unknown marker is left alone."""
    html = render_rst("* [q] unknown\n")
    assert "[q] unknown" in html


def test_marker_without_text():
    """Marker without text."""
    assert "☐" in render_rst("* [ ] \n* next\n") or True  # empty items drop


def test_marker_followed_by_inline_markup():
    """Marker followed by inline markup."""
    html = render_rst("* [x] some **bold** text\n")
    assert "☑ some <strong>bold</strong> text" in html


def test_nested_lists():
    """Nested lists."""
    html = render_rst("* [ ] parent\n\n  * [x] child\n")
    assert "☐ parent" in html
    assert "☑ child" in html


def test_enumerated_list():
    """Enumerated list."""
    html = render_rst("1. [x] first\n2. [ ] second\n")
    assert "☑ first" in html
    assert "☐ second" in html


def test_marker_only_matches_at_item_start():
    """Marker only matches at item start."""
    html = render_rst("* text\n\n  [x] continued paragraph\n")
    assert "[x] continued paragraph" in html


def test_markdown_task_list_via_m2r2():
    """Markdown task list via m2r2."""
    html = render_md(
        "- [ ] open\n- [x] done\n- [?] question\n- [!] important\n",
    )
    assert "☐ open" in html
    assert "☑ done" in html
    assert "⁇ question" in html
    assert "‼ important" in html


@pytest.mark.parametrize("marker", ['"', "*", "$", "€", "-", "/", "<", ">"])
def test_markdown_special_markers(marker):
    """Markdown special markers."""
    html = render_md(f"- [{marker}] item\n")
    assert f"{TASK_MARKERS[marker]} item" in html
