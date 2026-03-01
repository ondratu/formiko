"""Headless tests for SourceView formatting methods.

These tests use a bare ``GtkSource.Buffer`` without any display
server — they exercise the GTK buffer manipulation logic that sits
between the pure-Python ``format_utils`` functions and the UI.

Run normally with ``pytest``; no ``xvfb-run`` or ``$DISPLAY`` needed.
"""

import contextlib

import gi

gi.require_version("GtkSource", "5")
gi.require_version("Adw", "1")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from gi.repository import GtkSource  # noqa: E402

GtkSource.init()


# ------------------------------------------------------------------
# Lightweight adapter: just enough of SourceView to test formatting
# ------------------------------------------------------------------

class _BufferAdapter:
    """Minimal stand-in for :class:`formiko.sourceview.SourceView`.

    Exposes only ``text_buffer`` and the extracted helper methods
    so that the public ``toggle_*`` methods can be tested without
    creating a full widget tree.
    """

    def __init__(self, text: str, cursor_line: int = 0, cursor_col: int = 0):
        self.text_buffer = GtkSource.Buffer()
        self.text_buffer.set_text(text)
        self._place_cursor(cursor_line, cursor_col)

    # --- import the methods under test from SourceView -----------------
    from formiko.sourceview import SourceView as _SV

    _get_current_line = _SV._get_current_line
    _get_line_text = _SV._get_line_text
    _replace_line = _SV._replace_line
    _replace_range = _SV._replace_range
    _toggle_list_item = _SV._toggle_list_item
    toggle_line_format = _SV.toggle_line_format
    toggle_line_exclusive = _SV.toggle_line_exclusive
    toggle_rst_header = _SV.toggle_rst_header
    toggle_bullet = _SV.toggle_bullet
    toggle_ordered = _SV.toggle_ordered
    toggle_format = _SV.toggle_format
    get_selected_text = _SV.get_selected_text
    get_selection_offsets = _SV.get_selection_offsets
    insert_link_text = _SV.insert_link_text

    del _SV

    # --- helpers -------------------------------------------------------

    def _place_cursor(self, line, col=0):
        buf = self.text_buffer
        _, it = buf.get_iter_at_line(line)
        it.forward_chars(col)
        buf.place_cursor(it)

    def _select(self, start_offset, end_offset):
        buf = self.text_buffer
        s = buf.get_iter_at_offset(start_offset)
        e = buf.get_iter_at_offset(end_offset)
        buf.select_range(s, e)

    @property
    def text(self):
        return self.text_buffer.props.text

    @property
    def selection(self):
        """Return selected text, or ``None``."""
        bounds = self.text_buffer.get_selection_bounds()
        if not bounds:
            return None
        return self.text_buffer.get_text(bounds[0], bounds[1], True)


# ==================================================================
# Tests for private helpers
# ==================================================================


class TestGetCurrentLine:
    """Tests for ``_get_current_line``."""

    def test_single_line(self):
        sv = _BufferAdapter("Hello world")
        num, _s, _e, text = sv._get_current_line()
        assert num == 0
        assert text == "Hello world"

    def test_middle_line(self):
        sv = _BufferAdapter("a\nbb\nccc", cursor_line=1)
        num, _s, _e, text = sv._get_current_line()
        assert num == 1
        assert text == "bb"

    def test_last_line(self):
        sv = _BufferAdapter("a\nb\nc", cursor_line=2)
        num, _s, _e, text = sv._get_current_line()
        assert num == 2
        assert text == "c"


class TestGetLineText:
    """Tests for ``_get_line_text``."""

    def test_valid_line(self):
        sv = _BufferAdapter("aaa\nbbb\nccc")
        assert sv._get_line_text(1) == "bbb"

    def test_negative_returns_none(self):
        sv = _BufferAdapter("x")
        assert sv._get_line_text(-1) is None


class TestReplaceLine:
    """Tests for ``_replace_line``."""

    def test_replaces_content(self):
        sv = _BufferAdapter("old line")
        _, start, end, text = sv._get_current_line()
        sv._replace_line(start, end, text, "new line")
        assert sv.text == "new line"

    def test_no_op_when_same(self):
        sv = _BufferAdapter("same")
        _, start, end, text = sv._get_current_line()
        sv._replace_line(start, end, text, "same")
        assert sv.text == "same"


# ==================================================================
# Tests for public toggle methods (integration with GTK buffer)
# ==================================================================


class TestToggleLineFormat:
    """toggle_line_format on a real GtkSource.Buffer."""

    def test_add_blockquote_md(self):
        sv = _BufferAdapter("Hello")
        sv.toggle_line_format("> ")
        assert sv.text == "> Hello"

    def test_remove_blockquote_md(self):
        sv = _BufferAdapter("> Hello")
        sv.toggle_line_format("> ")
        assert sv.text == "Hello"

    def test_strip_other_on_toggle(self):
        sv = _BufferAdapter("- Item")
        sv.toggle_line_format(
            "> ", all_block_variants=(("- ", ""),),
        )
        assert sv.text == "> Item"


class TestToggleLineExclusive:
    """toggle_line_exclusive on a real GtkSource.Buffer."""

    _VARIANTS = [
        ("# ", ""), ("## ", ""), ("### ", ""),
    ]

    def test_add_header(self):
        sv = _BufferAdapter("Title")
        sv.toggle_line_exclusive("## ", "", self._VARIANTS)
        assert sv.text == "## Title"

    def test_toggle_off_same_header(self):
        sv = _BufferAdapter("## Title")
        sv.toggle_line_exclusive("## ", "", self._VARIANTS)
        assert sv.text == "Title"

    def test_switch_header_level(self):
        sv = _BufferAdapter("## Title")
        sv.toggle_line_exclusive("# ", "", self._VARIANTS)
        assert sv.text == "# Title"


class TestToggleRstHeader:
    """toggle_rst_header on a real GtkSource.Buffer."""

    def test_add_underline(self):
        sv = _BufferAdapter("Title")
        sv.toggle_rst_header("=")
        assert sv.text == "Title\n====="

    def test_toggle_off_same_underline(self):
        sv = _BufferAdapter("Title\n=====")
        sv.toggle_rst_header("=")
        assert sv.text == "Title"

    def test_replace_underline(self):
        sv = _BufferAdapter("Title\n=====")
        sv.toggle_rst_header("-")
        assert sv.text == "Title\n-----"

    def test_empty_line_noop(self):
        sv = _BufferAdapter("")
        sv.toggle_rst_header("=")
        assert sv.text == ""


class TestToggleBullet:
    """toggle_bullet on a real GtkSource.Buffer."""

    def test_add_bullet(self):
        sv = _BufferAdapter("Item")
        sv.toggle_bullet("- ", "", (), needs_blank=False)
        assert sv.text == "- Item"

    def test_remove_bullet(self):
        sv = _BufferAdapter("- Item")
        sv.toggle_bullet("- ", "", (), needs_blank=False)
        assert sv.text == "Item"

    def test_blank_line_inserted(self):
        sv = _BufferAdapter("Prev\nItem", cursor_line=1)
        sv.toggle_bullet("- ", "", (), needs_blank=True)
        assert sv.text == "Prev\n\n- Item"

    def test_no_blank_when_prev_is_bullet(self):
        sv = _BufferAdapter("- Prev\nItem", cursor_line=1)
        sv.toggle_bullet("- ", "", (), needs_blank=True)
        assert sv.text == "- Prev\n- Item"

    def test_strips_header_on_toggle(self):
        sv = _BufferAdapter("## Heading")
        sv.toggle_bullet(
            "- ", "",
            (("## ", ""), ("# ", "")),
            needs_blank=False,
        )
        assert sv.text == "- Heading"


class TestToggleOrdered:
    """toggle_ordered on a real GtkSource.Buffer."""

    def test_add_ordered(self):
        sv = _BufferAdapter("Item")
        sv.toggle_ordered((), needs_blank=False)
        assert sv.text == "1. Item"

    def test_remove_ordered(self):
        sv = _BufferAdapter("1. Item")
        sv.toggle_ordered((), needs_blank=False)
        assert sv.text == "Item"

    def test_auto_number_rst(self):
        sv = _BufferAdapter("1. First\nSecond", cursor_line=1)
        sv.toggle_ordered(
            (), needs_blank=True, auto_number=True,
        )
        assert sv.text == "1. First\n2. Second"

    def test_blank_line_inserted(self):
        sv = _BufferAdapter("Prev\nItem", cursor_line=1)
        sv.toggle_ordered((), needs_blank=True)
        assert sv.text == "Prev\n\n1. Item"


class TestToggleFormat:
    """toggle_format (inline) on a real GtkSource.Buffer."""

    def test_add_bold(self):
        sv = _BufferAdapter("hello world")
        sv._select(6, 11)  # "world"
        sv.toggle_format("**", "**", [("**", "**")])
        assert sv.text == "hello **world**"
        assert sv.selection == "world"

    def test_remove_bold(self):
        sv = _BufferAdapter("hello **world**")
        sv._select(8, 13)  # "world" inside markers
        sv.toggle_format("**", "**", [("**", "**")])
        assert sv.text == "hello world"
        assert sv.selection == "world"

    def test_switch_format(self):
        sv = _BufferAdapter("hello *world*")
        sv._select(7, 12)  # "world" inside *
        known = [("**", "**"), ("*", "*")]
        sv.toggle_format("**", "**", known)
        assert sv.text == "hello **world**"
        assert sv.selection == "world"


class TestInsertLinkText:
    def test_insert_at_cursor(self):
        sv = _BufferAdapter("hello world")
        sv._place_cursor(0, 5)  # after "hello"
        sv.insert_link_text("[link](url)", 5, 5)
        assert sv.text == "hello [link](url) world"
        assert sv.selection == "[link](url)"

    def test_insert_replaces_selection(self):
        sv = _BufferAdapter("hello world")
        sv._select(6, 11)  # "world"
        sv.insert_link_text("[world](url)", 6, 11)
        assert sv.text == "hello [world](url)"
        assert sv.selection == "[world](url)"

    def test_no_extra_space_at_line_start(self):
        sv = _BufferAdapter("hello")
        sv._place_cursor(0, 0)
        sv.insert_link_text("[link](url)", 0, 0)
        assert sv.text == "[link](url) hello"
        assert sv.selection == "[link](url)"

    def test_no_extra_space_at_line_end(self):
        sv = _BufferAdapter("hello")
        sv._place_cursor(0, 5)
        sv.insert_link_text("[link](url)", 5, 5)
        assert sv.text == "hello [link](url)"
        assert sv.selection == "[link](url)"

    def test_no_double_space(self):
        sv = _BufferAdapter("hello world")
        sv._place_cursor(0, 5)  # after "hello", before space
        sv.insert_link_text("[x](y)", 5, 5)
        # space before link because "hello" ends without space;
        # but there IS already a space after, so no suffix
        assert sv.text == "hello [x](y) world"
        assert sv.selection == "[x](y)"
