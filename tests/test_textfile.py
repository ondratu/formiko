"""Tests for formiko.textfile."""

import pytest

from formiko.editorconfig import EditorConfigSettings
from formiko.textfile import (
    ENCODING_CHOICES,
    TextFile,
    decode_as,
    decode_text,
    prepare_text,
    save_parameters,
)


def test_decode_utf8_with_lf():
    """Plain UTF-8 text keeps its text and reports LF."""
    assert decode_text("příliš\nžluťoučký\n".encode()) == TextFile(
        "příliš\nžluťoučký\n",
        "utf-8",
        "\n",
    )


@pytest.mark.parametrize(
    ("raw", "newline"),
    [
        (b"a\r\nb\r\n", "\r\n"),
        (b"a\rb\r", "\r"),
        (b"a\nb\n", "\n"),
        (b"a\r\nb\r\nc\n", "\r\n"),
        (b"one line", None),
        (b"", None),
    ],
)
def test_decode_normalizes_and_detects_newline(raw, newline):
    """The buffer text has only LF; the dominant ending is remembered."""
    result = decode_text(raw)
    assert result.newline == newline
    assert "\r" not in result.text


def test_decode_keeps_existing_utf8_bom():
    """A BOM already in the file is stripped from the text and remembered."""
    result = decode_text(b"\xef\xbb\xbfabc")
    assert result.text == "abc"
    assert result.encoding == "utf-8-sig"


def test_decode_uses_editorconfig_charset():
    """The charset from EditorConfig is tried first."""
    assert decode_text("é".encode("utf-16-le"), "utf-16le") == TextFile(
        "é",
        "utf-16-le",
        None,
    )


def test_decode_falls_back_to_latin1():
    """Bytes that are not valid UTF-8 are read as Latin-1."""
    result = decode_text("café\n".encode("latin-1"))
    assert result == TextFile("café\n", "latin-1", "\n", guessed=True)


def test_decode_wrong_charset_falls_back():
    """A charset that can't decode the file doesn't make opening fail."""
    result = decode_text("café".encode(), "utf-16le")
    assert result.text == "café"


def test_save_parameters_prefer_editorconfig():
    """EditorConfig overrides what the file had."""
    original = TextFile("", "latin-1", "\r\n")
    settings = EditorConfigSettings(charset="utf-8-bom", end_of_line="lf")
    assert save_parameters(settings, original) == ("utf-8-sig", "\n")


def test_save_parameters_keep_original():
    """Without EditorConfig the file keeps its encoding and line ending."""
    original = TextFile("", "latin-1", "\r\n")
    assert save_parameters(EditorConfigSettings(), original) == (
        "latin-1",
        "\r\n",
    )


def test_save_parameters_for_new_file():
    """A new file is UTF-8 with the platform line ending."""
    assert save_parameters(EditorConfigSettings()) == ("utf-8", None)


@pytest.mark.parametrize(
    ("charset", "codec"),
    [
        ("latin1", "latin-1"),
        ("utf-8", "utf-8"),
        ("utf-8-bom", "utf-8-sig"),
        ("utf-16be", "utf-16-be"),
        ("utf-16le", "utf-16-le"),
    ],
)
def test_every_editorconfig_charset_is_a_python_codec(charset, codec):
    """All charsets EditorConfig allows map to a working codec."""
    encoding, _ = save_parameters(EditorConfigSettings(charset=charset))
    assert encoding == codec
    "abc".encode(codec)


def test_prepare_text_untouched_by_default():
    """Nothing is changed unless EditorConfig asks for it."""
    text = "a \nb\t\n\n"
    assert prepare_text(text, EditorConfigSettings()) == text


def test_prepare_text_trims_trailing_whitespace():
    """Spaces and tabs at the end of lines are removed, indentation stays."""
    settings = EditorConfigSettings(trim_trailing_whitespace=True)
    assert prepare_text("  a \t\nb  \n  \nc ", settings) == "  a\nb\n\nc"


def test_prepare_text_final_newline():
    """True adds one if missing, false removes the last one."""
    add = EditorConfigSettings(insert_final_newline=True)
    assert prepare_text("a", add) == "a\n"
    assert prepare_text("a\n", add) == "a\n"
    assert prepare_text("", add) == ""
    drop = EditorConfigSettings(insert_final_newline=False)
    assert prepare_text("a\n", drop) == "a"
    assert prepare_text("a\n\n", drop) == "a\n"
    assert prepare_text("a", drop) == "a"


@pytest.mark.parametrize(
    ("charset", "raw"),
    [
        ("utf-8", b"\xef\xbb\xbfabc"),
        ("utf-16le", b"\xff\xfea\x00b\x00c\x00"),
        ("utf-16be", b"\xfe\xff\x00a\x00b\x00c"),
    ],
)
def test_decode_drops_bom_with_explicit_charset(charset, raw):
    """A BOM must not end up as a character in the editor."""
    assert decode_text(raw, charset).text == "abc"


def test_decode_utf16_with_bom_without_charset():
    """A UTF-16 file with a BOM is recognized and kept as UTF-16."""
    result = decode_text("a\nb".encode("utf-16"))
    assert result == TextFile("a\nb", "utf-16", "\n")


def test_decode_marks_fallback_as_guessed():
    """Only the Latin-1 fallback is a guess the user may want to change."""
    assert decode_text("café".encode("latin-1")).guessed
    assert not decode_text("café".encode()).guessed
    assert not decode_text("café".encode("latin-1"), "latin1").guessed
    assert not decode_text(b"abc").guessed


def test_decode_as_other_encoding():
    """A chosen encoding decodes the bytes; unfit bytes give None."""
    raw = "příliš\r\n".encode("cp1250")
    assert decode_as(raw, "cp1250") == TextFile("příliš\n", "cp1250", "\r\n")
    assert decode_as(b"\x81", "cp1250") is None


def test_every_offered_encoding_is_a_python_codec():
    """The dialog choices all work."""
    for codec, label in ENCODING_CHOICES:
        assert label
        assert decode_as(b"abc", codec).text == "abc"
