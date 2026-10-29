r"""Reading and writing text files with encoding and line endings.

No GTK dependency. The editor works with ``"\n"`` only; the original
encoding and line ending are remembered so a save can keep them, unless
EditorConfig asks for others.
"""

import re
from dataclasses import dataclass

# EditorConfig ``charset`` -> Python codec
CODECS = {
    "latin1": "latin-1",
    "utf-8": "utf-8",
    "utf-8-bom": "utf-8-sig",
    "utf-16be": "utf-16-be",
    "utf-16le": "utf-16-le",
}
# Encodings offered when a file is not valid UTF-8: (Python codec, label)
ENCODING_CHOICES = (
    ("latin-1", "Latin-1 (ISO-8859-1)"),
    ("cp1250", "Central European (Windows-1250)"),
    ("iso8859-2", "Central European (ISO-8859-2)"),
    ("cp1252", "Western European (Windows-1252)"),
    ("koi8-r", "Cyrillic (KOI8-R)"),
    ("cp1251", "Cyrillic (Windows-1251)"),
)
# EditorConfig ``end_of_line`` -> line ending
NEWLINES = {"lf": "\n", "cr": "\r", "crlf": "\r\n"}

_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)


@dataclass(frozen=True)
class TextFile:
    r"""Decoded file: *text* uses ``"\n"``; *newline* is the original ending.

    *newline* is ``None`` when the file has no line break. *guessed* is
    ``True`` when the file isn't valid UTF-8 and the encoding was not asked
    for, so Latin-1 was only a fallback and the user may want another one.
    """

    text: str
    encoding: str
    newline: "str | None"
    guessed: bool = False


def _detect_newline(text):
    """Return the most common line ending of *text*, ``None`` if none."""
    crlf = text.count("\r\n")
    counts = {
        "\n": text.count("\n") - crlf,
        "\r\n": crlf,
        "\r": text.count("\r") - crlf,
    }
    newline = max(counts, key=counts.get)
    return newline if counts[newline] else None


def decode_text(raw, charset=None):
    """Decode *raw* bytes; *charset* is the EditorConfig value, if any.

    The EditorConfig charset is tried first, then the encoding of a BOM
    the file already has (kept on save), UTF-8 and finally Latin-1, which
    accepts any bytes. A BOM is never part of the returned text.
    """
    codecs = [
        CODECS[charset] if charset else None,
        "utf-16" if raw.startswith(_UTF16_BOMS) else None,
        "utf-8-sig" if raw.startswith(_UTF8_BOM) else "utf-8",
        "latin-1",
    ]
    codecs = [codec for codec in codecs if codec]
    for i, codec in enumerate(codecs):
        result = decode_as(raw, codec, guessed=i == len(codecs) - 1)
        if result:
            return result
    return None  # unreachable, latin-1 decodes everything


def decode_as(raw, codec, *, guessed=False):
    """Decode *raw* with *codec*; ``None`` if the bytes don't fit it."""
    try:
        text = raw.decode(codec)
    except UnicodeDecodeError:
        return None
    text = text.removeprefix("\ufeff")
    newline = _detect_newline(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return TextFile(text, codec, newline, guessed)


def save_parameters(settings, original=None):
    """Return ``(encoding, newline)`` for ``open(path, "w", ...)``.

    EditorConfig *settings* win over the *original* file; for a new file
    without either, the platform default applies (``newline=None``).
    """
    encoding = (
        CODECS[settings.charset]
        if settings.charset
        else original.encoding
        if original
        else "utf-8"
    )
    newline = (
        NEWLINES[settings.end_of_line]
        if settings.end_of_line
        else original.newline
        if original
        else None
    )
    return encoding, newline


def prepare_text(text, settings):
    """Return *text* as the EditorConfig *settings* want it saved."""
    if settings.trim_trailing_whitespace:
        text = _TRAILING_WHITESPACE.sub("", text)
    if settings.insert_final_newline is True and text and text[-1] != "\n":
        text += "\n"
    elif settings.insert_final_newline is False and text.endswith("\n"):
        text = text[:-1]
    return text
