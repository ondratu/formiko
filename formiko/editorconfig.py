"""EditorConfig support (https://editorconfig.org/), no GTK dependency.

``resolve(path)`` looks up the ``.editorconfig`` files that apply to *path*
and returns the supported properties as an ``EditorConfigSettings``. A value
that is missing, ``unset`` or invalid is ``None``, so the caller keeps its own
default for it.
"""

from dataclasses import dataclass
from logging import getLogger
from os.path import abspath

from editorconfig import EditorConfigError, get_properties

log = getLogger(__name__)

# ``indent_size = tab``: the indent width follows the tab width. It is also
# what GtkSource.View.set_indent_width() takes for "use tab_width".
INDENT_SIZE_TAB = -1

_INDENT_STYLES = ("tab", "space")
_END_OF_LINES = ("lf", "cr", "crlf")
_CHARSETS = ("latin1", "utf-8", "utf-8-bom", "utf-16be", "utf-16le")


@dataclass(frozen=True)
class EditorConfigSettings:
    """Supported EditorConfig properties; ``None`` means not specified."""

    indent_style: "str | None" = None
    indent_size: "int | None" = None
    tab_width: "int | None" = None
    end_of_line: "str | None" = None
    charset: "str | None" = None
    trim_trailing_whitespace: "bool | None" = None
    insert_final_newline: "bool | None" = None
    max_line_length: "int | None" = None


def _choice(value, choices):
    """Return lowercase *value* if it is one of *choices*, else None."""
    value = str(value).lower()
    return value if value in choices else None


def _number(value):
    """Return *value* as a positive int, else None."""
    value = str(value).strip()
    return int(value) if value.isdecimal() and int(value) > 0 else None


def _boolean(value):
    """Return *value* as bool for ``true``/``false``, else None."""
    return {"true": True, "false": False}.get(str(value).lower())


def _indent_size(value):
    if str(value).lower() == "tab":
        return INDENT_SIZE_TAB
    return _number(value)


def resolve(path):
    """Return EditorConfig settings for the file *path*.

    Empty settings are returned for a document without a path and when the
    ``.editorconfig`` files can't be read or parsed.
    """
    if not path:
        return EditorConfigSettings()
    try:
        props = get_properties(abspath(path))
    except (EditorConfigError, OSError, UnicodeDecodeError) as err:
        log.warning("Ignoring EditorConfig for %s: %s", path, err)
        return EditorConfigSettings()

    return EditorConfigSettings(
        indent_style=_choice(props.get("indent_style"), _INDENT_STYLES),
        indent_size=_indent_size(props.get("indent_size")),
        tab_width=_number(props.get("tab_width")),
        end_of_line=_choice(props.get("end_of_line"), _END_OF_LINES),
        charset=_choice(props.get("charset"), _CHARSETS),
        trim_trailing_whitespace=_boolean(
            props.get("trim_trailing_whitespace"),
        ),
        insert_final_newline=_boolean(props.get("insert_final_newline")),
        max_line_length=_number(props.get("max_line_length")),
    )
