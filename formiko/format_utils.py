"""Pure-Python helpers for text formatting (no GTK dependency).

Low-level building blocks
~~~~~~~~~~~~~~~~~~~~~~~~~

``_strip_markers`` / ``_wrap_markers``
    Atomic operations: detect + strip (or add) a ``(before, after)`` marker
    pair around a piece of text.

``_strip_other_block``
    Strip the first matching *block-level* marker from a line — used by every
    block-formatting function to remove a conflicting format before applying
    the new one.

Public API
~~~~~~~~~~

``compute_toggle_format``
    Inline (selection-based) formatting: bold, italic, strikethrough, code.

``compute_toggle_line_format``
    Simple line-level toggle (blockquote).

``compute_toggle_line_exclusive``
    Exclusive line-level toggle (headers H1-H6).

``compute_toggle_rst_header``
    RST-specific heading underline management.

``compute_toggle_bullet`` / ``compute_toggle_ordered``
    List-item toggles with blank-line separator logic.
"""

import re as _re

# -------------------------------------------------------------------
# Regex for ordered-list prefix (``1. ``, ``12. ``, …).
# Placed at module level so every function can use it.
# -------------------------------------------------------------------
_RE_ORDERED_ITEM = _re.compile(r"^(\d+)\. ")


# ===================================================================
# Building blocks
# ===================================================================

def _strip_markers(
    text: str, before: str, after: str,
) -> "tuple[str, bool]":
    """Strip *before*/*after* markers from *text* if present.

    :returns: ``(stripped_text, True)`` when markers were found and
        removed, ``(text, False)`` otherwise.
    """
    has_before = text.startswith(before)
    has_after = (not after) or text.endswith(after)
    if has_before and has_after:
        result = text[len(before):]
        if after:
            result = result[: len(result) - len(after)]
        return result, True
    return text, False


def _wrap_markers(text: str, before: str, after: str) -> str:
    """Add *before*/*after* markers around *text*."""
    if after:
        return before + text + after
    return before + text


def _strip_other_block(
    text: str,
    variants: "tuple | list" = (),
    strip_ordered: bool = False,
    strip_whitespace: bool = False,
) -> str:
    r"""Strip the first matching block-level marker from *text*.

    Processing order (first match wins):

    1. Leading whitespace (when *strip_whitespace* is ``True``).
    2. Ordered-list regex ``\d+. `` (when *strip_ordered*).
    3. Each ``(before, after)`` pair in *variants*.
    """
    if strip_whitespace:
        text = text.lstrip()
    if strip_ordered:
        m = _RE_ORDERED_ITEM.match(text)
        if m:
            return text[m.end():]
    for v_before, v_after in variants:
        stripped, matched = _strip_markers(text, v_before, v_after)
        if matched:
            return stripped
    return text


# ===================================================================
# Inline formatting
# ===================================================================

def build_known_formats(*markup_dicts):
    """Collect all (before, after) pairs per parser from markup dicts.

    Returns a ``{parser: [(before, after), ...]}`` dict where each list
    is sorted by decreasing length of the opening marker, so that
    longer markers (e.g. ``**``) are tested before shorter ones
    (e.g. ``*``) during stripping.

    :param markup_dicts: ``{parser: (before, after)}`` dicts.
    """
    result = {}
    for d in markup_dicts:
        for parser, fmt in d.items():
            if not callable(fmt):
                result.setdefault(parser, []).append(fmt)
    for lst in result.values():
        lst.sort(key=lambda f: -len(f[0]))
    return result


def compute_toggle_format(
    buf_text: str,
    sel_start: int,
    sel_end: int,
    before: str,
    after: str,
    known_formats: list,
) -> tuple:
    """Compute the result of toggling an inline formatting marker.

    Examines the characters inside and immediately outside the
    selection ``[sel_start, sel_end]`` for any of the *known_formats*
    markers.  Longer markers are tested first so that ``**`` is never
    confused with a pair of ``*`` markers.

    :returns: ``(eff_start, eff_end, result, inner_start, inner_end)``
    """
    sel_text = buf_text[sel_start:sel_end]
    sorted_formats = sorted(known_formats, key=lambda f: -len(f[0]))

    eff_start = sel_start
    eff_end = sel_end
    inner_text = sel_text
    had_format = None

    for fmt_before, fmt_after in sorted_formats:
        # Case 1: markers inside the selection
        inner, found = _strip_markers(sel_text, fmt_before, fmt_after)
        if found:
            inner_text = inner
            had_format = (fmt_before, fmt_after)
            break

        # Case 2: markers just outside the selection
        if (
            sel_start >= len(fmt_before)
            and sel_end + len(fmt_after) <= len(buf_text)
        ):
            pre = buf_text[sel_start - len(fmt_before): sel_start]
            post = buf_text[sel_end: sel_end + len(fmt_after)]
            if pre == fmt_before and post == fmt_after:
                eff_start = sel_start - len(fmt_before)
                eff_end = sel_end + len(fmt_after)
                inner_text = sel_text
                had_format = (fmt_before, fmt_after)
                break

    if had_format == (before, after):
        result = inner_text
        before_len = 0
    else:
        result = before + inner_text + after
        before_len = len(before)

    return (
        eff_start, eff_end, result,
        before_len, before_len + len(inner_text),
    )


# ===================================================================
# Line-level (block) formatting
# ===================================================================

def compute_toggle_line_format(
    line_text: str,
    before: str,
    after: str = "",
    all_block_variants: "tuple | list" = (),
    strip_ordered: bool = False,
) -> str:
    r"""Toggle a simple block marker (e.g. blockquote).

    If the line already has *before*/*after*, strip them (toggle off).
    Otherwise strip any conflicting block format first, then apply.

    :param line_text: Line text without the trailing newline.
    :param before: Prefix marker (e.g. ``"> "``).
    :param after: Suffix marker (e.g. ``"</blockquote>"``).
    :param all_block_variants: Other ``(before, after)`` pairs to
        strip before applying the new format.
    :param strip_ordered: Strip a ``\d+. `` prefix first.
    """
    stripped, had = _strip_markers(line_text, before, after)
    if had:
        return stripped
    return _wrap_markers(
        _strip_other_block(
            line_text, all_block_variants, strip_ordered,
        ),
        before, after,
    )


def compute_toggle_line_exclusive(
    line_text: str,
    before: str,
    after: str,
    all_variants: list,
    extra_strip_variants: "tuple | list" = (),
    strip_ordered: bool = False,
) -> str:
    r"""Toggle exclusive line-level formatting (e.g. header levels).

    First strips non-exclusive block formats (*extra_strip_variants*,
    ordered prefix), then looks for any variant in *all_variants*.
    If the active variant matches *before*/*after* exactly it is
    toggled off; otherwise the active variant is replaced.

    :param line_text: Line text without the trailing newline.
    :param before: Opening marker to apply.
    :param after: Closing marker (empty for prefix-only).
    :param all_variants: Mutually exclusive ``(before, after)`` pairs
        (e.g. all six header levels for a given parser).
    :param extra_strip_variants: Non-exclusive variants to strip first
        (blockquote, bullet list).
    :param strip_ordered: Strip a ``\d+. `` prefix first.
    """
    current = _strip_other_block(
        line_text, extra_strip_variants, strip_ordered,
    )

    for v_before, v_after in all_variants:
        stripped, matched = _strip_markers(current, v_before, v_after)
        if matched:
            if v_before == before and v_after == after:
                return stripped          # toggle off same level
            current = stripped
            break

    return _wrap_markers(current, before, after)


# ===================================================================
# RST heading underline
# ===================================================================

#: RST underline characters for heading levels 1-6.
RST_HEADER_CHARS = '=-^"~.'


def compute_toggle_rst_header(
    line_text: str,
    next_line: "str | None",
    underline_char: str,
    known_chars: str = RST_HEADER_CHARS,
) -> "tuple[str | None, bool]":
    """Compute the RST heading underline operation.

    :param line_text: Title line text (no trailing newline).
    :param next_line: Line immediately after the title, or ``None``.
    :param underline_char: Character for the underline (``"="`` etc.).
    :param known_chars: All recognised underline characters.
    :returns: ``(new_underline, had_underline)``.
    """
    if not line_text.strip():
        return None, False

    target = underline_char * len(line_text)

    def _is_underline(text: str) -> bool:
        return (
            bool(text)
            and len(set(text)) == 1
            and text[0] in known_chars
            and len(text) >= len(line_text)
        )

    had = next_line is not None and _is_underline(next_line)

    if had:
        if next_line[0] == underline_char:  # type: ignore[index]
            return None, True       # same level → toggle off
        return target, True         # different level → replace

    return target, False            # no underline → add


# ===================================================================
# List-item formatting (bullet / ordered)
# ===================================================================

def compute_toggle_bullet(
    line_text: str,
    prev_line_text: "str | None",
    before: str,
    after: str = "",
    all_block_variants: "tuple | list" = (),
    strip_leading_whitespace: bool = False,
    strip_ordered: bool = False,
) -> "tuple[str, bool]":
    r"""Toggle bullet-list formatting on a single line.

    * **Toggle off** — if the line already has *before*/*after*, strip.
    * **Toggle on** — strip conflicting block formats, then prepend the
      bullet marker.  A blank separator line is requested when this is
      the first item in a new list.

    :param line_text: Current line text (no trailing newline).
    :param prev_line_text: Previous line text, or ``None``.
    :param before: Prefix marker (e.g. ``"- "``).
    :param after: Suffix marker (e.g. ``"</li>"``).
    :param all_block_variants: Block markers to strip on toggle-on.
    :param strip_leading_whitespace: Strip leading whitespace (RST).
    :param strip_ordered: Also strip ``\d+. `` prefix.
    :returns: ``(new_line_text, insert_blank_before)``.
    """
    # Toggle off
    stripped, had = _strip_markers(line_text, before, after)
    if had:
        return stripped, False

    # Toggle on
    current = _strip_other_block(
        line_text, all_block_variants,
        strip_ordered=strip_ordered,
        strip_whitespace=strip_leading_whitespace,
    )
    new_text = _wrap_markers(current, before, after)

    insert_blank = (
        prev_line_text is not None
        and bool(prev_line_text.strip())
        and not prev_line_text.startswith(before)
    )
    return new_text, insert_blank


def compute_toggle_ordered(
    line_text: str,
    prev_line_text: "str | None",
    after: str = "",
    all_block_variants: "tuple | list" = (),
    strip_leading_whitespace: bool = False,
    auto_number: bool = False,
) -> "tuple[str, bool]":
    r"""Toggle ordered (numbered) list item formatting.

    Toggle-off is detected by the ``\d+\.\s`` regex.  On toggle-on
    the item number is derived from the previous line when
    *auto_number* is ``True`` (RST), otherwise ``1`` is used (MD).

    For HTML, reuse :func:`compute_toggle_bullet` with ``<li>``
    markers instead.

    :param line_text: Current line text (no trailing newline).
    :param prev_line_text: Previous line text, or ``None``.
    :param after: Suffix marker (empty for MD/RST).
    :param all_block_variants: Block markers to strip on toggle-on.
    :param strip_leading_whitespace: Strip leading whitespace (RST).
    :param auto_number: Derive number from previous line (RST).
    :returns: ``(new_line_text, insert_blank_before)``.
    """
    # Toggle off
    m = _RE_ORDERED_ITEM.match(line_text)
    if m:
        stripped = line_text[m.end():]
        if after and stripped.endswith(after):
            stripped = stripped[: len(stripped) - len(after)]
        return stripped, False

    # Toggle on
    current = _strip_other_block(
        line_text, all_block_variants,
        strip_whitespace=strip_leading_whitespace,
    )

    number = 1
    if auto_number and prev_line_text:
        pm = _RE_ORDERED_ITEM.match(prev_line_text)
        if pm:
            number = int(pm.group(1)) + 1

    before = f"{number}. "
    new_text = _wrap_markers(current, before, after)

    prev_is_ordered = bool(
        prev_line_text and _RE_ORDERED_ITEM.match(prev_line_text),
    )
    insert_blank = (
        prev_line_text is not None
        and bool(prev_line_text.strip())
        and not prev_is_ordered
    )
    return new_text, insert_blank


# ===================================================================
# Link formatting
# ===================================================================

def compute_link(text: str, url: str, parser: str) -> str:
    """Return formatted link markup for *parser*.

    For HTML: uses *text* as inner content when provided, falls back to *url*.
    For RST/Markdown: returns bare *url* when *text* is empty.
    """
    if parser == "html":
        inner = text.strip() or url
        return f'<a href="{url}">{inner}</a>'
    if not text.strip():
        return url
    if parser == "m2r":
        return f"[{text}]({url})"
    if parser == "rst":
        return f"`{text} <{url}>`_"
    return url


def parse_link(selected_text: str, parser: str) -> "tuple[str, str]":
    """Try to parse *selected_text* as an already-formatted link.

    Returns ``(link_text, url)``.  If the text is not recognised as a
    link, returns ``(selected_text, "")`` so the caller can pre-fill the
    *Text* field with the selection and leave *URL* empty.  If the text
    looks like a bare URL it is placed in the *URL* field instead.
    """
    stripped = selected_text.strip()
    if parser == "m2r":
        m = _re.match(r"^\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            return m.group(1), m.group(2)
    elif parser == "rst":
        m = _re.match(r"^`([^<]+) <([^>]+)>`_$", stripped)
        if m:
            return m.group(1).strip(), m.group(2)
    elif parser == "html":
        m = _re.match(
            r'^<a\s+href="([^"]+)"[^>]*>([^<]*)</a>$', stripped,
        )
        if m:
            return m.group(2), m.group(1)
    # Bare URL → pre-fill URL field only
    if _re.match(r"^https?://\S+$", stripped):
        return "", stripped
    return selected_text, ""
