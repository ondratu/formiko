"""Tests for the direct Markdown-to-HTML mistune preview."""

from importlib.util import find_spec

import pytest

from formiko.mistune_preview import MistunePreview

pytestmark = pytest.mark.skipif(
    find_spec("mistune") is None,
    reason="Mistune is an optional dependency",
)


def test_to_html_renders_basic_markdown():
    """Headings and inline emphasis are converted to HTML."""
    html = MistunePreview().to_html("# Title\n\nSome *text*.\n")
    assert "<h1>Title</h1>" in html
    assert "<em>text</em>" in html


def test_to_html_renders_gfm_table():
    """GFM pipe tables are rendered as ``<table>``."""
    text = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"
    html = MistunePreview().to_html(text)
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_to_html_renders_strikethrough():
    """``~~text~~`` is rendered as ``<del>``."""
    html = MistunePreview().to_html("~~gone~~\n")
    assert "<del>gone</del>" in html


def test_to_html_renders_task_list_checkboxes():
    """GFM task-list items become disabled checkboxes."""
    html = MistunePreview().to_html("- [ ] todo\n- [x] done\n")
    assert 'type="checkbox"' in html
    assert "checked" in html


def test_to_html_autolinks_bare_url():
    """A bare URL is turned into a clickable link."""
    html = MistunePreview().to_html("See https://example.com for more.\n")
    assert '<a href="https://example.com">' in html


def test_to_html_honors_tab_width():
    """Leading tabs are expanded using the configured tab width.

    A single leading tab only forms an indented code block once it
    expands to at least 4 columns; a narrow tab width should leave the
    line as a plain paragraph instead.
    """
    text = "\tcode\n"
    assert "<pre><code>" in MistunePreview().to_html(text, tab_width=8)
    assert "<pre><code>" not in MistunePreview().to_html(text, tab_width=1)


def test_to_html_renders_builtin_plugins_without_extra_dependencies():
    """Mistune's dependency-free built-in plugins are enabled."""
    mistune = pytest.importorskip("mistune")
    if not hasattr(mistune, "create_markdown"):
        pytest.skip("Mistune 2 or newer is required for optional plugins")
    text = (
        "HTML and W3C\n\n"
        "*[HTML]: Hyper Text Markup Language\n"
        "*[W3C]: World Wide Web Consortium\n\n"
        "Term\n: Definition\n\n"
        "Footnote[^1]\n\n"
        "[^1]: Note\n\n"
        "==marked== ^^inserted^^ 2^10^ H~2~O\n\n"
        "$x + y$\n\n"
        "[漢字(ㄏㄢˋㄗˋ)]\n\n"
        "A >!hidden!< spoiler\n"
    )
    html = MistunePreview().to_html(text)
    assert '<abbr title="Hyper Text Markup Language">HTML</abbr>' in html
    assert '<abbr title="World Wide Web Consortium">W3C</abbr>' in html
    assert "<dt>Term</dt>" in html
    assert "<dd>Definition</dd>" in html
    assert 'class="footnote-ref"' in html
    assert "<mark>marked</mark>" in html
    assert "<ins>inserted</ins>" in html
    assert "<sup>10</sup>" in html
    assert "<sub>2</sub>" in html
    assert '<span class="math">\\(x + y\\)</span>' in html
    assert "<ruby>漢字<rt>ㄏㄢˋㄗˋ</rt></ruby>" in html
    assert '<span class="spoiler">hidden</span>' in html
