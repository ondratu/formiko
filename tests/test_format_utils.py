"""Tests for formiko.format_utils.compute_toggle_format."""

from typing import ClassVar

import pytest

from formiko.format_utils import (
    RST_HEADER_CHARS,
    compute_toggle_format,
    compute_toggle_line_exclusive,
    compute_toggle_line_format,
    compute_toggle_ordered,
    compute_toggle_rst_header,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Per-parser known-formats lists (mirrors window.py _KNOWN_FORMATS)
RST_FORMATS = [
    (":del:`", "`"),
    ("**", "**"),
    ("``", "``"),
    ("*", "*"),
]
MD_FORMATS = [
    ("**", "**"),
    ("~~", "~~"),
    ("*", "*"),
    ("`", "`"),
]
HTML_FORMATS = [
    ("<code>", "</code>"),
    ("<b>", "</b>"),
    ("<i>", "</i>"),
    ("<s>", "</s>"),
]

BOLD_MD = ("**", "**")
ITALIC_MD = ("*", "*")
STRIKE_MD = ("~~", "~~")
CODE_MD = ("`", "`")

BOLD_RST = ("**", "**")
ITALIC_RST = ("*", "*")
STRIKE_RST = (":del:`", "`")
CODE_RST = ("``", "``")

BOLD_HTML = ("<b>", "</b>")
ITALIC_HTML = ("<i>", "</i>")
STRIKE_HTML = ("<s>", "</s>")
CODE_HTML = ("<code>", "</code>")


def toggle(buf, sel_start, sel_end, before, after, known):
    """Shortcut: return (result_buf, new_sel_start, new_sel_end)."""
    eff_start, eff_end, result, inner_start, inner_end = compute_toggle_format(
        buf,
        sel_start,
        sel_end,
        before,
        after,
        known,
    )
    new_buf = buf[:eff_start] + result + buf[eff_end:]
    new_sel_start = eff_start + inner_start
    new_sel_end = eff_start + inner_end
    return new_buf, new_sel_start, new_sel_end


# ---------------------------------------------------------------------------
# Markdown / RST — markers INSIDE the selection
# ---------------------------------------------------------------------------


class TestMarkdownInsideSelection:
    """Selection includes the formatting markers."""

    def test_no_format_apply_bold(self):
        buf = "hello text world"
        #            ^---^ sel: "text"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "hello **text** world"
        assert new_buf[ss:se] == "text"

    def test_no_format_apply_italic(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_MD, MD_FORMATS)
        assert new_buf == "hello *text* world"
        assert new_buf[ss:se] == "text"

    def test_bold_inside_sel_toggle_off(self):
        buf = "hello **text** world"
        #            ^-------^ sel: "**text**"
        start, end = 6, 14
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_bold_inside_sel_switch_to_italic(self):
        buf = "hello **text** world"
        start, end = 6, 14
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_MD, MD_FORMATS)
        assert new_buf == "hello *text* world"
        assert new_buf[ss:se] == "text"

    def test_italic_inside_sel_toggle_off(self):
        buf = "hello *text* world"
        #            ^------^ sel: "*text*"
        start, end = 6, 12
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_MD, MD_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_italic_inside_sel_switch_to_bold(self):
        buf = "hello *text* world"
        start, end = 6, 12
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "hello **text** world"
        assert new_buf[ss:se] == "text"


# ---------------------------------------------------------------------------
# Markdown / RST — markers OUTSIDE the selection
# ---------------------------------------------------------------------------


class TestMarkdownOutsideSelection:
    """User selected only the inner text; markers sit just outside."""

    def test_bold_outside_sel_toggle_off(self):
        buf = "hello **text** world"
        #               ^--^ sel: "text"  (offsets 8..12)
        start, end = 8, 12
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_bold_outside_sel_switch_to_italic(self):
        buf = "hello **text** world"
        start, end = 8, 12
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_MD, MD_FORMATS)
        assert new_buf == "hello *text* world"
        assert new_buf[ss:se] == "text"

    def test_italic_outside_sel_toggle_off(self):
        buf = "hello *text* world"
        #              ^--^ sel: "text"  (offsets 7..11)
        start, end = 7, 11
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_MD, MD_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_italic_outside_sel_switch_to_bold(self):
        buf = "hello *text* world"
        start, end = 7, 11
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "hello **text** world"
        assert new_buf[ss:se] == "text"


# ---------------------------------------------------------------------------
# HTML — markers INSIDE the selection
# ---------------------------------------------------------------------------


class TestHtmlInsideSelection:
    def test_no_format_apply_bold(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *BOLD_HTML, HTML_FORMATS)
        assert new_buf == "hello <b>text</b> world"
        assert new_buf[ss:se] == "text"

    def test_no_format_apply_italic(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_HTML, HTML_FORMATS)
        assert new_buf == "hello <i>text</i> world"
        assert new_buf[ss:se] == "text"

    def test_bold_inside_sel_toggle_off(self):
        buf = "hello <b>text</b> world"
        #            ^----------^ sel: "<b>text</b>"  (6..17)
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *BOLD_HTML, HTML_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_bold_inside_sel_switch_to_italic(self):
        buf = "hello <b>text</b> world"
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_HTML, HTML_FORMATS)
        assert new_buf == "hello <i>text</i> world"
        assert new_buf[ss:se] == "text"

    def test_italic_inside_sel_toggle_off(self):
        buf = "hello <i>text</i> world"
        #            ^----------^ sel: "<i>text</i>"  (6..17)
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_HTML, HTML_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_italic_inside_sel_switch_to_bold(self):
        buf = "hello <i>text</i> world"
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *BOLD_HTML, HTML_FORMATS)
        assert new_buf == "hello <b>text</b> world"
        assert new_buf[ss:se] == "text"


# ---------------------------------------------------------------------------
# HTML — markers OUTSIDE the selection
# ---------------------------------------------------------------------------


class TestHtmlOutsideSelection:
    def test_bold_outside_sel_toggle_off(self):
        buf = "hello <b>text</b> world"
        #               ^--^ sel: "text"  (9..13)
        start, end = 9, 13
        new_buf, ss, se = toggle(buf, start, end, *BOLD_HTML, HTML_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_bold_outside_sel_switch_to_italic(self):
        buf = "hello <b>text</b> world"
        start, end = 9, 13
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_HTML, HTML_FORMATS)
        assert new_buf == "hello <i>text</i> world"
        assert new_buf[ss:se] == "text"

    def test_italic_outside_sel_toggle_off(self):
        buf = "hello <i>text</i> world"
        #               ^--^ sel: "text"  (9..13)
        start, end = 9, 13
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_HTML, HTML_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_italic_outside_sel_switch_to_bold(self):
        buf = "hello <i>text</i> world"
        start, end = 9, 13
        new_buf, ss, se = toggle(buf, start, end, *BOLD_HTML, HTML_FORMATS)
        assert new_buf == "hello <b>text</b> world"
        assert new_buf[ss:se] == "text"


# ---------------------------------------------------------------------------
# Selection preservation — inner_start / inner_end offsets
# ---------------------------------------------------------------------------


class TestSelectionPreservation:
    """After the operation the selection must cover only the inner text."""

    @pytest.mark.parametrize(
        ("apply_bold", "apply_italic"),
        [
            (True, False),
            (False, True),
        ],
    )
    def test_apply_format_sel_covers_inner(self, apply_bold, apply_italic):
        buf = "hello text world"
        start, end = 6, 10  # "text"
        fmt = BOLD_MD if apply_bold else ITALIC_MD
        new_buf, ss, se = toggle(buf, start, end, *fmt, MD_FORMATS)
        assert new_buf[ss:se] == "text"

    def test_toggle_off_sel_covers_inner(self):
        buf = "**text**"
        start, end = 0, 8
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "text"
        assert new_buf[ss:se] == "text"

    def test_switch_sel_covers_inner(self):
        buf = "**text**"
        start, end = 0, 8
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_MD, MD_FORMATS)
        assert new_buf == "*text*"
        assert new_buf[ss:se] == "text"

    def test_outer_markers_sel_covers_inner(self):
        buf = "**text**"
        # Select only "text" (inside the markers)
        start, end = 2, 6
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "text"
        assert new_buf[ss:se] == "text"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_no_adjacent_markers_no_change_on_toggle_off(self):
        """Plain text with no markers — toggle off is impossible, applies."""
        buf = "text"
        start, end = 0, 4
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "**text**"
        assert new_buf[ss:se] == "text"

    def test_at_start_of_buffer(self):
        buf = "text rest"
        start, end = 0, 4
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "**text** rest"
        assert new_buf[ss:se] == "text"

    def test_at_end_of_buffer(self):
        buf = "hello text"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "hello **text**"
        assert new_buf[ss:se] == "text"

    def test_whole_buffer_bold(self):
        buf = "text"
        start, end = 0, 4
        new_buf, _, _ = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "**text**"

    def test_empty_inner_text(self):
        """Toggling off bold on '****' yields empty string."""
        buf = "****"
        start, end = 0, 4
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == ""
        assert ss == se  # empty selection

    def test_markers_not_adjacent_no_expand(self):
        """Markers elsewhere in buffer must not affect selection."""
        buf = "**other** text **more**"
        #               ^---^ "text" at 10..14
        start, end = 10, 14
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "**other** **text** **more**"
        assert new_buf[ss:se] == "text"

    def test_multiword_selection(self):
        buf = "hello world foo"
        start, end = 0, 11  # "hello world"
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_MD, MD_FORMATS)
        assert new_buf == "*hello world* foo"
        assert new_buf[ss:se] == "hello world"


# ---------------------------------------------------------------------------
# Markdown — strikethrough and inline code
# ---------------------------------------------------------------------------


class TestMarkdownStrikethrough:
    """Strikethrough (~~) for markdown."""

    def test_no_format_apply_strikethrough(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_MD, MD_FORMATS)
        assert new_buf == "hello ~~text~~ world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_inside_sel_toggle_off(self):
        buf = "hello ~~text~~ world"
        start, end = 6, 14
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_MD, MD_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_inside_sel_switch_to_bold(self):
        buf = "hello ~~text~~ world"
        start, end = 6, 14
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "hello **text** world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_outside_sel_toggle_off(self):
        buf = "hello ~~text~~ world"
        start, end = 8, 12  # "text" inside ~~
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_MD, MD_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_outside_sel_switch_to_italic(self):
        buf = "hello ~~text~~ world"
        start, end = 8, 12
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_MD, MD_FORMATS)
        assert new_buf == "hello *text* world"
        assert new_buf[ss:se] == "text"

    def test_bold_switch_to_strikethrough(self):
        buf = "hello **text** world"
        start, end = 6, 14
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_MD, MD_FORMATS)
        assert new_buf == "hello ~~text~~ world"
        assert new_buf[ss:se] == "text"


class TestMarkdownCode:
    """Inline code (`) for markdown."""

    def test_no_format_apply_code(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *CODE_MD, MD_FORMATS)
        assert new_buf == "hello `text` world"
        assert new_buf[ss:se] == "text"

    def test_code_inside_sel_toggle_off(self):
        buf = "hello `text` world"
        start, end = 6, 12
        new_buf, ss, se = toggle(buf, start, end, *CODE_MD, MD_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_code_inside_sel_switch_to_bold(self):
        buf = "hello `text` world"
        start, end = 6, 12
        new_buf, ss, se = toggle(buf, start, end, *BOLD_MD, MD_FORMATS)
        assert new_buf == "hello **text** world"
        assert new_buf[ss:se] == "text"

    def test_code_outside_sel_toggle_off(self):
        buf = "hello `text` world"
        start, end = 7, 11  # "text" inside `
        new_buf, ss, se = toggle(buf, start, end, *CODE_MD, MD_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_italic_switch_to_code(self):
        buf = "hello *text* world"
        start, end = 6, 12
        new_buf, ss, se = toggle(buf, start, end, *CODE_MD, MD_FORMATS)
        assert new_buf == "hello `text` world"
        assert new_buf[ss:se] == "text"


# ---------------------------------------------------------------------------
# RST — all four formats (including asymmetric strikethrough)
# ---------------------------------------------------------------------------


class TestRstFormats:
    """RST-specific marker combinations."""

    def test_no_format_apply_bold(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *BOLD_RST, RST_FORMATS)
        assert new_buf == "hello **text** world"
        assert new_buf[ss:se] == "text"

    def test_no_format_apply_italic(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_RST, RST_FORMATS)
        assert new_buf == "hello *text* world"
        assert new_buf[ss:se] == "text"

    def test_no_format_apply_code(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *CODE_RST, RST_FORMATS)
        assert new_buf == "hello ``text`` world"
        assert new_buf[ss:se] == "text"

    def test_no_format_apply_strikethrough(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_RST, RST_FORMATS)
        assert new_buf == "hello :del:`text` world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_inside_sel_toggle_off(self):
        buf = "hello :del:`text` world"
        # ":del:`text`" is at 6..17
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_RST, RST_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_inside_sel_switch_to_bold(self):
        buf = "hello :del:`text` world"
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *BOLD_RST, RST_FORMATS)
        assert new_buf == "hello **text** world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_outside_sel_toggle_off(self):
        """Select only 'text' with :del:` outside."""
        buf = "hello :del:`text` world"
        # ":del:`" ends at offset 12, "`" starts at offset 16
        start, end = 12, 16
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_RST, RST_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_outside_sel_switch_to_italic(self):
        buf = "hello :del:`text` world"
        start, end = 12, 16
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_RST, RST_FORMATS)
        assert new_buf == "hello *text* world"
        assert new_buf[ss:se] == "text"

    def test_code_inside_sel_toggle_off(self):
        buf = "hello ``text`` world"
        start, end = 6, 14
        new_buf, ss, se = toggle(buf, start, end, *CODE_RST, RST_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_code_outside_sel_switch_to_bold(self):
        buf = "hello ``text`` world"
        start, end = 8, 12  # "text" inside ``
        new_buf, ss, se = toggle(buf, start, end, *BOLD_RST, RST_FORMATS)
        assert new_buf == "hello **text** world"
        assert new_buf[ss:se] == "text"

    def test_bold_outside_sel_switch_to_code(self):
        buf = "hello **text** world"
        start, end = 8, 12  # "text" inside **
        new_buf, ss, se = toggle(buf, start, end, *CODE_RST, RST_FORMATS)
        assert new_buf == "hello ``text`` world"
        assert new_buf[ss:se] == "text"


# ---------------------------------------------------------------------------
# HTML — strikethrough and code
# ---------------------------------------------------------------------------


class TestHtmlStrikethrough:
    def test_no_format_apply_strikethrough(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_HTML, HTML_FORMATS)
        assert new_buf == "hello <s>text</s> world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_inside_sel_toggle_off(self):
        buf = "hello <s>text</s> world"
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_HTML, HTML_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_inside_sel_switch_to_bold(self):
        buf = "hello <s>text</s> world"
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *BOLD_HTML, HTML_FORMATS)
        assert new_buf == "hello <b>text</b> world"
        assert new_buf[ss:se] == "text"

    def test_strikethrough_outside_sel_toggle_off(self):
        buf = "hello <s>text</s> world"
        start, end = 9, 13  # "text" inside <s>
        new_buf, ss, se = toggle(buf, start, end, *STRIKE_HTML, HTML_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"


class TestHtmlCode:
    def test_no_format_apply_code(self):
        buf = "hello text world"
        start, end = 6, 10
        new_buf, ss, se = toggle(buf, start, end, *CODE_HTML, HTML_FORMATS)
        assert new_buf == "hello <code>text</code> world"
        assert new_buf[ss:se] == "text"

    def test_code_inside_sel_toggle_off(self):
        buf = "hello <code>text</code> world"
        # "<code>text</code>" is at 6..23
        start, end = 6, 23
        new_buf, ss, se = toggle(buf, start, end, *CODE_HTML, HTML_FORMATS)
        assert new_buf == "hello text world"
        assert new_buf[ss:se] == "text"

    def test_code_outside_sel_switch_to_italic(self):
        buf = "hello <code>text</code> world"
        start, end = 12, 16  # "text" inside <code>
        new_buf, ss, se = toggle(buf, start, end, *ITALIC_HTML, HTML_FORMATS)
        assert new_buf == "hello <i>text</i> world"
        assert new_buf[ss:se] == "text"

    def test_bold_switch_to_code(self):
        buf = "hello <b>text</b> world"
        start, end = 6, 17
        new_buf, ss, se = toggle(buf, start, end, *CODE_HTML, HTML_FORMATS)
        assert new_buf == "hello <code>text</code> world"
        assert new_buf[ss:se] == "text"


# ---------------------------------------------------------------------------
# Cross-format switching (all → all) for markdown
# ---------------------------------------------------------------------------


class TestMarkdownCrossFormatSwitching:
    """Every format can be switched to every other format."""

    FORMATS: ClassVar = [BOLD_MD, ITALIC_MD, STRIKE_MD, CODE_MD]
    FORMAT_NAMES: ClassVar = ["bold", "italic", "strikethrough", "code"]

    @pytest.mark.parametrize(
        ("src_fmt", "dst_fmt"),
        [
            (src, dst)
            for src in [BOLD_MD, ITALIC_MD, STRIKE_MD, CODE_MD]
            for dst in [BOLD_MD, ITALIC_MD, STRIKE_MD, CODE_MD]
            if src != dst
        ],
    )
    def test_switch(self, src_fmt, dst_fmt):
        src_b, src_a = src_fmt
        dst_b, dst_a = dst_fmt
        buf = f"{src_b}text{src_a}"
        start, end = 0, len(buf)
        new_buf, ss, se = toggle(buf, start, end, *dst_fmt, MD_FORMATS)
        assert new_buf == f"{dst_b}text{dst_a}"
        assert new_buf[ss:se] == "text"


# ===========================================================================
# Tests for compute_toggle_line_format
# ===========================================================================


class TestToggleLineFormat:
    """Tests for compute_toggle_line_format (block / paragraph formatting)."""

    # -------------------------------------------------------------------
    # Markdown blockquote  (before="> ", after="")
    # -------------------------------------------------------------------

    def test_md_blockquote_toggle_on(self):
        result = compute_toggle_line_format("Hello world", "> ")
        assert result == "> Hello world"

    def test_md_blockquote_toggle_off(self):
        result = compute_toggle_line_format("> Hello world", "> ")
        assert result == "Hello world"

    def test_md_blockquote_empty_line_on(self):
        assert compute_toggle_line_format("", "> ") == "> "

    def test_md_blockquote_empty_line_off(self):
        assert compute_toggle_line_format("> ", "> ") == ""

    def test_md_blockquote_no_false_strip(self):
        # Line starts with ">" but not "> " — should add, not strip
        assert compute_toggle_line_format(">text", "> ") == "> >text"

    # -------------------------------------------------------------------
    # RST blockquote — spaces variant  (before="    ", after="")
    # -------------------------------------------------------------------

    def test_rst_blockquote_spaces_toggle_on(self):
        assert compute_toggle_line_format("Hello", "    ") == "    Hello"

    def test_rst_blockquote_spaces_toggle_off(self):
        assert compute_toggle_line_format("    Hello", "    ") == "Hello"

    def test_rst_blockquote_spaces_empty_on(self):
        assert compute_toggle_line_format("", "    ") == "    "

    def test_rst_blockquote_spaces_empty_off(self):
        assert compute_toggle_line_format("    ", "    ") == ""

    # -------------------------------------------------------------------
    # RST blockquote — tab variant  (before="\t", after="")
    # -------------------------------------------------------------------

    def test_rst_blockquote_tab_toggle_on(self):
        assert compute_toggle_line_format("Hello", "\t") == "\tHello"

    def test_rst_blockquote_tab_toggle_off(self):
        assert compute_toggle_line_format("\tHello", "\t") == "Hello"

    # -------------------------------------------------------------------
    # HTML blockquote  (before="<blockquote>", after="</blockquote>")
    # -------------------------------------------------------------------

    HTML_B = "<blockquote>"
    HTML_A = "</blockquote>"

    def test_html_blockquote_toggle_on(self):
        result = compute_toggle_line_format(
            "Hello world",
            self.HTML_B,
            self.HTML_A,
        )
        assert result == "<blockquote>Hello world</blockquote>"

    def test_html_blockquote_toggle_off(self):
        result = compute_toggle_line_format(
            "<blockquote>Hello world</blockquote>",
            self.HTML_B,
            self.HTML_A,
        )
        assert result == "Hello world"

    def test_html_blockquote_empty_line_on(self):
        result = compute_toggle_line_format("", self.HTML_B, self.HTML_A)
        assert result == "<blockquote></blockquote>"

    def test_html_blockquote_empty_line_off(self):
        result = compute_toggle_line_format(
            "<blockquote></blockquote>",
            self.HTML_B,
            self.HTML_A,
        )
        assert result == ""

    def test_html_blockquote_only_before_adds_both(self):
        # Only the before-marker is present — should add, not strip
        result = compute_toggle_line_format(
            "<blockquote>Hello world",
            self.HTML_B,
            self.HTML_A,
        )
        assert result == ("<blockquote><blockquote>Hello world</blockquote>")

    def test_html_blockquote_only_after_adds_both(self):
        # Only the after-marker is present — should add, not strip
        result = compute_toggle_line_format(
            "Hello world</blockquote>",
            self.HTML_B,
            self.HTML_A,
        )
        assert result == ("<blockquote>Hello world</blockquote></blockquote>")

    # -------------------------------------------------------------------
    # Idempotency: toggling on and then off returns original text
    # -------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("before", "after", "text"),
        [
            ("> ", "", "Hello world"),
            ("> ", "", ""),
            ("    ", "", "Some RST text"),
            ("\t", "", "Tab indented"),
            ("<blockquote>", "</blockquote>", "HTML paragraph"),
            ("<blockquote>", "</blockquote>", ""),
        ],
    )
    def test_idempotent_round_trip(self, before, after, text):
        toggled_on = compute_toggle_line_format(text, before, after)
        # Must change (unless text was already empty and prefix is also empty)
        assert toggled_on != text or not text
        toggled_off = compute_toggle_line_format(toggled_on, before, after)
        assert toggled_off == text


# ===========================================================================
# Tests for compute_toggle_line_exclusive  (header levels)
# ===========================================================================


class TestToggleLineExclusive:
    """Tests for compute_toggle_line_exclusive (mutually exclusive formats)."""

    MD_VARIANTS: ClassVar = [(f"{'#' * n} ", "") for n in range(1, 7)]
    HTML_VARIANTS: ClassVar = [(f"<h{n}>", f"</h{n}>") for n in range(1, 7)]

    # --- Markdown -----------------------------------------------------------

    def test_md_h1_toggle_on(self):
        result = compute_toggle_line_exclusive(
            "Hello",
            "# ",
            "",
            self.MD_VARIANTS,
        )
        assert result == "# Hello"

    def test_md_h3_toggle_on(self):
        result = compute_toggle_line_exclusive(
            "Hello",
            "### ",
            "",
            self.MD_VARIANTS,
        )
        assert result == "### Hello"

    def test_md_h1_toggle_off(self):
        result = compute_toggle_line_exclusive(
            "# Hello",
            "# ",
            "",
            self.MD_VARIANTS,
        )
        assert result == "Hello"

    def test_md_switch_h1_to_h3(self):
        result = compute_toggle_line_exclusive(
            "# Hello",
            "### ",
            "",
            self.MD_VARIANTS,
        )
        assert result == "### Hello"

    def test_md_switch_h3_to_h6(self):
        result = compute_toggle_line_exclusive(
            "### Hello",
            "###### ",
            "",
            self.MD_VARIANTS,
        )
        assert result == "###### Hello"

    def test_md_all_levels_round_trip(self):
        for level in range(1, 7):
            before = "#" * level + " "
            line = f"{before}Text"
            # Toggle off
            stripped = compute_toggle_line_exclusive(
                line,
                before,
                "",
                self.MD_VARIANTS,
            )
            assert stripped == "Text"

    # --- HTML ---------------------------------------------------------------

    def test_html_h1_toggle_on(self):
        result = compute_toggle_line_exclusive(
            "Hello",
            "<h1>",
            "</h1>",
            self.HTML_VARIANTS,
        )
        assert result == "<h1>Hello</h1>"

    def test_html_h2_toggle_off(self):
        result = compute_toggle_line_exclusive(
            "<h2>Hello</h2>",
            "<h2>",
            "</h2>",
            self.HTML_VARIANTS,
        )
        assert result == "Hello"

    def test_html_switch_h1_to_h4(self):
        result = compute_toggle_line_exclusive(
            "<h1>Hello</h1>",
            "<h4>",
            "</h4>",
            self.HTML_VARIANTS,
        )
        assert result == "<h4>Hello</h4>"


# ===========================================================================
# Tests for compute_toggle_rst_header
# ===========================================================================


class TestToggleRstHeader:
    """Tests for compute_toggle_rst_header."""

    # --- Add underline (no existing underline) ------------------------------

    def test_add_h1(self):
        underline, had = compute_toggle_rst_header("Hello", None, "=")
        assert underline == "====="
        assert not had

    def test_add_h2_with_next_line_unrelated(self):
        underline, had = compute_toggle_rst_header("Hi", "Some text", "-")
        assert underline == "--"
        assert not had

    def test_underline_matches_text_length(self):
        text = "A longer title"
        underline, _ = compute_toggle_rst_header(text, None, "=")
        assert underline == "=" * len(text)

    # --- Toggle off (same underline char) -----------------------------------

    def test_toggle_off_h1(self):
        underline, had = compute_toggle_rst_header("Hello", "=====", "=")
        assert underline is None
        assert had

    def test_toggle_off_longer_underline(self):
        # Underline longer than title — still recognised
        underline, had = compute_toggle_rst_header("Hi", "=====", "=")
        assert underline is None
        assert had

    # --- Replace (different underline char) ---------------------------------

    def test_replace_h1_with_h2(self):
        underline, had = compute_toggle_rst_header("Hello", "=====", "-")
        assert underline == "-----"
        assert had

    def test_replace_h3_with_h5(self):
        underline, had = compute_toggle_rst_header("Test", "^^^^", "~")
        assert underline == "~~~~"
        assert had

    # --- Edge cases ---------------------------------------------------------

    def test_empty_line_no_op(self):
        underline, had = compute_toggle_rst_header("", None, "=")
        assert underline is None
        assert not had

    def test_whitespace_only_line_no_op(self):
        underline, had = compute_toggle_rst_header("   ", None, "=")
        assert underline is None
        assert not had

    def test_all_known_chars_recognised(self):
        for char in RST_HEADER_CHARS:
            underline, had = compute_toggle_rst_header("X", char * 5, char)
            assert underline is None
            assert had

    def test_unknown_char_not_recognised(self):
        # '#' is not an RST underline char
        underline, had = compute_toggle_rst_header("Hello", "#####", "=")
        assert underline == "====="
        assert not had


# ===========================================================================
# Tests for compute_toggle_bullet
# ===========================================================================

from formiko.format_utils import compute_toggle_bullet  # noqa: E402

MD_BLOCK_VARIANTS = (
    ("###### ", ""),
    ("##### ", ""),
    ("#### ", ""),
    ("### ", ""),
    ("## ", ""),
    ("# ", ""),
    ("> ", ""),
)
HTML_BLOCK_VARIANTS = tuple(
    [(f"<h{n}>", f"</h{n}>") for n in range(1, 7)]
    + [("<blockquote>", "</blockquote>")],
)


class TestToggleBullet:
    """Tests for compute_toggle_bullet."""

    # -------------------------------------------------------------------
    # Basic toggle on / off
    # -------------------------------------------------------------------

    def test_toggle_on_plain_line(self):
        text, blank = compute_toggle_bullet("Hello", None, "- ")
        assert text == "- Hello"
        assert not blank

    def test_toggle_off(self):
        text, blank = compute_toggle_bullet("- Hello", None, "- ")
        assert text == "Hello"
        assert not blank

    def test_toggle_off_never_inserts_blank(self):
        # Even if prev line has content, toggle-off never requests blank line
        text, blank = compute_toggle_bullet("- Hello", "Some text", "- ")
        assert text == "Hello"
        assert not blank

    # -------------------------------------------------------------------
    # Blank-line separator logic
    # -------------------------------------------------------------------

    def test_blank_line_when_prev_has_text(self):
        _, blank = compute_toggle_bullet("Hello", "Previous text", "- ")
        assert blank

    def test_no_blank_when_prev_is_empty(self):
        _, blank = compute_toggle_bullet("Hello", "", "- ")
        assert not blank

    def test_no_blank_when_prev_is_whitespace_only(self):
        _, blank = compute_toggle_bullet("Hello", "   ", "- ")
        assert not blank

    def test_no_blank_when_prev_is_list_item(self):
        _, blank = compute_toggle_bullet("Hello", "- Previous", "- ")
        assert not blank

    def test_no_blank_when_no_prev_line(self):
        _, blank = compute_toggle_bullet("Hello", None, "- ")
        assert not blank

    # -------------------------------------------------------------------
    # Block-format stripping (Markdown)
    # -------------------------------------------------------------------

    def test_strips_h1_before_adding_bullet(self):
        text, _ = compute_toggle_bullet(
            "# Title",
            None,
            "- ",
            all_block_variants=MD_BLOCK_VARIANTS,
        )
        assert text == "- Title"

    def test_strips_h3_before_adding_bullet(self):
        text, _ = compute_toggle_bullet(
            "### Title",
            None,
            "- ",
            all_block_variants=MD_BLOCK_VARIANTS,
        )
        assert text == "- Title"

    def test_strips_blockquote_before_adding_bullet(self):
        text, _ = compute_toggle_bullet(
            "> Text",
            None,
            "- ",
            all_block_variants=MD_BLOCK_VARIANTS,
        )
        assert text == "- Text"

    def test_strips_h6_and_adds_blank(self):
        text, blank = compute_toggle_bullet(
            "###### Title",
            "Previous",
            "- ",
            all_block_variants=MD_BLOCK_VARIANTS,
        )
        assert text == "- Title"
        assert blank

    # -------------------------------------------------------------------
    # Block-format stripping (HTML)
    # -------------------------------------------------------------------

    def test_html_strips_h2_tag(self):
        text, _ = compute_toggle_bullet(
            "<h2>Title</h2>",
            None,
            "<li>",
            "</li>",
            HTML_BLOCK_VARIANTS,
        )
        assert text == "<li>Title</li>"

    def test_html_strips_blockquote(self):
        text, _ = compute_toggle_bullet(
            "<blockquote>Text</blockquote>",
            None,
            "<li>",
            "</li>",
            HTML_BLOCK_VARIANTS,
        )
        assert text == "<li>Text</li>"

    def test_html_no_blank_line_logic(self):
        # prev_line_text=None suppresses blank line for HTML
        _, blank = compute_toggle_bullet(
            "Text",
            None,
            "<li>",
            "</li>",
            HTML_BLOCK_VARIANTS,
        )
        assert not blank

    # -------------------------------------------------------------------
    # Nested lists: leading indentation is preserved
    # -------------------------------------------------------------------

    def test_nested_toggle_on_preserves_indent(self):
        text, _ = compute_toggle_bullet("    Text", None, "- ")
        assert text == "    - Text"

    def test_nested_tab_indent_preserved(self):
        text, _ = compute_toggle_bullet("\tText", None, "- ")
        assert text == "\t- Text"

    def test_nested_toggle_off_preserves_indent(self):
        text, _ = compute_toggle_bullet("  - Item", None, "- ")
        assert text == "  Item"

    def test_nested_blank_line_with_prev_text(self):
        _, blank = compute_toggle_bullet("Text", "Previous", "- ")
        assert blank

    def test_nested_no_blank_if_prev_is_indented_bullet(self):
        _, blank = compute_toggle_bullet("  Text", "  - Prev", "- ")
        assert not blank


# ---------------------------------------------------------------------------
# TestToggleOrdered
# ---------------------------------------------------------------------------

_MD_BLOCK_VARIANTS = [
    ("> ", ""),
    ("# ", ""),
    ("## ", ""),
    ("### ", ""),
    ("#### ", ""),
    ("##### ", ""),
    ("###### ", ""),
]


class TestToggleOrdered:
    """Tests for compute_toggle_ordered (MD / RST / HTML via toggle_bullet)."""

    # ------- toggle-off ------------------------------------------------------

    def test_md_toggle_off(self):
        text, blank = compute_toggle_ordered("1. Item", None)
        assert text == "Item"
        assert not blank

    def test_md_toggle_off_preserves_content(self):
        text, _ = compute_toggle_ordered("3. Hello world", None)
        assert text == "Hello world"

    def test_rst_toggle_off(self):
        text, blank = compute_toggle_ordered(
            "2. Next item",
            None,
            auto_number=True,
        )
        assert text == "Next item"
        assert not blank

    # ------- toggle-on — Markdown --------------------------------------------

    def test_md_toggle_on_plain(self):
        text, blank = compute_toggle_ordered("Plain text", None)
        assert text == "1. Plain text"
        assert not blank

    def test_md_toggle_on_no_prev(self):
        _, blank = compute_toggle_ordered("Text", None)
        assert not blank

    def test_md_toggle_on_prev_is_ordered(self):
        _, blank = compute_toggle_ordered("New item", "1. Previous")
        assert not blank

    def test_md_toggle_on_prev_not_ordered(self):
        _, blank = compute_toggle_ordered("New item", "Some text")
        assert blank

    def test_md_toggle_on_prev_empty(self):
        _, blank = compute_toggle_ordered("New item", "")
        assert not blank

    def test_md_toggle_on_strips_block_variant(self):
        text, _ = compute_toggle_ordered(
            "> Quoted text",
            None,
            all_block_variants=_MD_BLOCK_VARIANTS,
        )
        assert text == "1. Quoted text"

    def test_md_toggle_on_strips_header(self):
        text, _ = compute_toggle_ordered(
            "## Header text",
            None,
            all_block_variants=_MD_BLOCK_VARIANTS,
        )
        assert text == "1. Header text"

    # ------- toggle-on — RST -------------------------------------------------

    def test_rst_toggle_on_plain(self):
        text, blank = compute_toggle_ordered("Item", None, auto_number=True)
        assert text == "1. Item"
        assert not blank

    def test_rst_toggle_on_prev_is_ordered_increments(self):
        text, blank = compute_toggle_ordered(
            "Next",
            "1. Previous",
            auto_number=True,
        )
        assert text == "2. Next"
        assert not blank

    def test_rst_toggle_on_prev_ordered_high_number(self):
        text, _ = compute_toggle_ordered("Item", "9. Last", auto_number=True)
        assert text == "10. Item"

    def test_rst_toggle_on_prev_not_ordered_uses_one(self):
        text, blank = compute_toggle_ordered(
            "Item",
            "Some text",
            auto_number=True,
        )
        assert text == "1. Item"
        assert blank

    def test_rst_nested_toggle_on_preserves_indent(self):
        text, _ = compute_toggle_ordered("   Indented", None, auto_number=True)
        assert text == "   1. Indented"

    def test_rst_toggle_off_no_blank(self):
        _, blank = compute_toggle_ordered(
            "4. Item",
            "3. Prev",
            auto_number=True,
        )
        assert not blank

    # ------- invariants ------------------------------------------------------

    def test_toggle_off_then_on_md(self):
        original = "Hello"
        toggled_on, _ = compute_toggle_ordered(original, None)
        toggled_off, _ = compute_toggle_ordered(toggled_on, None)
        assert toggled_off == original

    def test_toggle_off_then_on_rst(self):
        original = "Hello"
        toggled_on, _ = compute_toggle_ordered(
            original,
            None,
            auto_number=True,
        )
        toggled_off, _ = compute_toggle_ordered(
            toggled_on,
            None,
            auto_number=True,
        )
        assert toggled_off == original


# ---------------------------------------------------------------------------
# TestCrossBlockStripping
# ---------------------------------------------------------------------------

_MD_ALL_BLOCK = (
    ("###### ", ""),
    ("##### ", ""),
    ("#### ", ""),
    ("### ", ""),
    ("## ", ""),
    ("# ", ""),
    ("> ", ""),
    ("- ", ""),
)


class TestCrossBlockStripping:
    """Block formats strip each other's markers when toggling on."""

    # ------- blockquote strips others ----------------------------------------

    def test_blockquote_strips_bullet_md(self):
        text = compute_toggle_line_format(
            "- Item",
            "> ",
            all_block_variants=_MD_ALL_BLOCK,
        )
        assert text == "> Item"

    def test_blockquote_strips_header_md(self):
        text = compute_toggle_line_format(
            "## Heading",
            "> ",
            all_block_variants=_MD_ALL_BLOCK,
        )
        assert text == "> Heading"

    def test_blockquote_strips_ordered_md(self):
        text = compute_toggle_line_format(
            "3. Item",
            "> ",
            strip_ordered=True,
        )
        assert text == "> Item"

    def test_blockquote_strips_ordered_and_bullet(self):
        # ordered takes priority (applied first), then variants loop skipped
        text = compute_toggle_line_format(
            "2. Text",
            "> ",
            all_block_variants=_MD_ALL_BLOCK,
            strip_ordered=True,
        )
        assert text == "> Text"

    # ------- header strips others --------------------------------------------

    _MD_HEADER_VARIANTS: ClassVar = [
        ("###### ", ""),
        ("##### ", ""),
        ("#### ", ""),
        ("### ", ""),
        ("## ", ""),
        ("# ", ""),
    ]
    _EXTRA_MD: ClassVar = (("> ", ""), ("- ", ""))

    def test_header_strips_blockquote_md(self):
        text = compute_toggle_line_exclusive(
            "> Text",
            "## ",
            "",
            self._MD_HEADER_VARIANTS,
            extra_strip_variants=self._EXTRA_MD,
        )
        assert text == "## Text"

    def test_header_strips_bullet_md(self):
        text = compute_toggle_line_exclusive(
            "- Item",
            "# ",
            "",
            self._MD_HEADER_VARIANTS,
            extra_strip_variants=self._EXTRA_MD,
        )
        assert text == "# Item"

    def test_header_strips_ordered_md(self):
        text = compute_toggle_line_exclusive(
            "1. Item",
            "# ",
            "",
            self._MD_HEADER_VARIANTS,
            extra_strip_variants=self._EXTRA_MD,
            strip_ordered=True,
        )
        assert text == "# Item"

    # ------- bullet strips others --------------------------------------------

    def test_bullet_strips_header_md(self):
        text, _ = compute_toggle_bullet(
            "## Heading",
            None,
            "- ",
            all_block_variants=_MD_ALL_BLOCK,
        )
        assert text == "- Heading"

    def test_bullet_strips_blockquote_md(self):
        text, _ = compute_toggle_bullet(
            "> Quote",
            None,
            "- ",
            all_block_variants=_MD_ALL_BLOCK,
        )
        assert text == "- Quote"

    def test_bullet_strips_ordered_md(self):
        text, _ = compute_toggle_bullet(
            "2. Item",
            None,
            "- ",
            all_block_variants=_MD_ALL_BLOCK,
            strip_ordered=True,
        )
        assert text == "- Item"

    def test_bullet_nested_preserves_indent(self):
        text, _ = compute_toggle_bullet("   Indented", None, "- ")
        assert text == "   - Indented"

    def test_bullet_strips_ordered_rst(self):
        text, _ = compute_toggle_bullet(
            "3. Item",
            None,
            "- ",
            strip_ordered=True,
        )
        assert text == "- Item"

    # ------- ordered strips others -------------------------------------------

    def test_ordered_strips_header_md(self):
        text, _ = compute_toggle_ordered(
            "## Heading",
            None,
            all_block_variants=_MD_ALL_BLOCK,
        )
        assert text == "1. Heading"

    def test_ordered_strips_blockquote_md(self):
        text, _ = compute_toggle_ordered(
            "> Quote",
            None,
            all_block_variants=_MD_ALL_BLOCK,
        )
        assert text == "1. Quote"

    def test_ordered_strips_bullet_md(self):
        text, _ = compute_toggle_ordered(
            "- Item",
            None,
            all_block_variants=_MD_ALL_BLOCK,
        )
        assert text == "1. Item"

    def test_ordered_strips_bullet_rst(self):
        text, _ = compute_toggle_ordered(
            "- Item",
            None,
            all_block_variants=(("- ", ""),),
            auto_number=True,
        )
        assert text == "1. Item"

    def test_ordered_nested_preserves_indent(self):
        text, _ = compute_toggle_ordered(
            "   Indented",
            None,
            all_block_variants=(("- ", ""),),
            auto_number=True,
        )
        assert text == "   1. Indented"

    def test_nested_bullet_to_ordered(self):
        # indented bullet → indented ordered
        text, _ = compute_toggle_ordered(
            "  - Item",
            None,
            all_block_variants=(("- ", ""),),
            auto_number=True,
        )
        assert text == "  1. Item"

    def test_nested_ordered_to_bullet(self):
        # indented ordered → indented bullet
        text, _ = compute_toggle_bullet(
            "  1. Item",
            None,
            "- ",
            all_block_variants=(("- ", ""),),
            strip_ordered=True,
        )
        assert text == "  - Item"

    def test_nested_ordered_toggle_off_preserves_indent(self):
        text, _ = compute_toggle_ordered("  3. Item", None, auto_number=True)
        assert text == "  Item"

    def test_nested_auto_number_from_indented_prev(self):
        # previous line is also indented
        text, _ = compute_toggle_ordered(
            "  Item",
            "  2. Prev",
            auto_number=True,
        )
        assert text == "  3. Item"

    def test_md_with_text(self):
        from formiko.format_utils import compute_link

        assert (
            compute_link("Python", "https://python.org", "m2r")
            == "[Python](https://python.org)"
        )

    def test_rst_with_text(self):
        from formiko.format_utils import compute_link

        assert (
            compute_link("Python", "https://python.org", "rst")
            == "`Python <https://python.org>`_"
        )

    def test_html_with_text(self):
        from formiko.format_utils import compute_link

        assert (
            compute_link("Python", "https://python.org", "html")
            == '<a href="https://python.org">Python</a>'
        )

    def test_html_no_text_uses_url(self):
        from formiko.format_utils import compute_link

        assert (
            compute_link("", "https://python.org", "html")
            == '<a href="https://python.org">https://python.org</a>'
        )

    def test_no_text_returns_url(self):
        from formiko.format_utils import compute_link

        assert (
            compute_link("", "https://python.org", "m2r")
            == "https://python.org"
        )
        assert (
            compute_link("", "https://python.org", "rst")
            == "https://python.org"
        )

    def test_whitespace_text_returns_url(self):
        from formiko.format_utils import compute_link

        assert (
            compute_link("  ", "https://python.org", "m2r")
            == "https://python.org"
        )


class TestParseLink:
    def test_md_link(self):
        from formiko.format_utils import parse_link

        assert parse_link("[Python](https://python.org)", "m2r") == (
            "Python",
            "https://python.org",
        )

    def test_rst_link(self):
        from formiko.format_utils import parse_link

        assert parse_link("`Python <https://python.org>`_", "rst") == (
            "Python",
            "https://python.org",
        )

    def test_html_link(self):
        from formiko.format_utils import parse_link

        assert parse_link(
            '<a href="https://python.org">Python</a>',
            "html",
        ) == ("Python", "https://python.org")

    def test_bare_url_md(self):
        from formiko.format_utils import parse_link

        assert parse_link("https://python.org", "m2r") == (
            "",
            "https://python.org",
        )

    def test_bare_url_rst(self):
        from formiko.format_utils import parse_link

        assert parse_link("https://python.org", "rst") == (
            "",
            "https://python.org",
        )

    def test_plain_text_md(self):
        from formiko.format_utils import parse_link

        assert parse_link("hello world", "m2r") == ("hello world", "")

    def test_plain_text_rst(self):
        from formiko.format_utils import parse_link

        assert parse_link("hello world", "rst") == ("hello world", "")

    def test_empty_string(self):
        from formiko.format_utils import parse_link

        assert parse_link("", "m2r") == ("", "")
