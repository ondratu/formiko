"""Tests for custom RST directives: file-tree and mdinclude."""

from io import StringIO

import pytest
from docutils.core import publish_string

import formiko.directives  # noqa: F401 — registers custom directives

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def render(rst: str, source_path: str, writer: str = "pseudoxml") -> str:
    """Render *rst* with docutils and return the string output.

    ``halt_level=5`` prevents SEVERE errors from raising exceptions so that
    error cases can be asserted on the returned document tree.
    """
    return publish_string(
        source=rst,
        source_path=source_path,
        writer=writer,
        settings_overrides={
            "warning_stream": StringIO(),
            "halt_level": 5,
        },
    ).decode()


# ---------------------------------------------------------------------------
# file-tree directive
# ---------------------------------------------------------------------------


@pytest.fixture
def filetree(tmp_path):
    """Create a sample directory tree used by file-tree tests.

    Structure::

        tmp_path/
          docs/
            guide.md
            readme.md
            images/
              logo.png
          notes.txt
          .hidden
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide")
    (docs / "readme.md").write_text("# Readme")
    images = docs / "images"
    images.mkdir()
    (images / "logo.png").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("notes")
    (tmp_path / ".hidden").write_text("hidden")
    return tmp_path


def source(tmp_path):
    """Return a fake RST source path located inside *tmp_path*."""
    return str(tmp_path / "source.rst")


class TestFileTreeBasic:
    def test_lists_files_and_dirs(self, filetree):
        out = render(".. file-tree:: .", source(filetree))
        assert "docs" in out
        assert "notes.txt" in out

    def test_hidden_entries_skipped(self, filetree):
        out = render(".. file-tree:: .", source(filetree))
        assert ".hidden" not in out

    def test_dirs_sorted_before_files(self, filetree):
        out = render(".. file-tree:: .", source(filetree))
        assert out.index("docs") < out.index("notes.txt")

    def test_files_sorted_alphabetically(self, filetree):
        out = render(".. file-tree:: docs", source(filetree))
        assert out.index("guide.md") < out.index("readme.md")

    def test_nested_subdir_appears(self, filetree):
        out = render(".. file-tree:: .", source(filetree))
        assert "images" in out
        # logo.png is at depth 3 — hidden with default depth=2
        assert "logo.png" not in out

    def test_empty_dir_yields_no_output(self, tmp_path):
        (tmp_path / "empty").mkdir()
        out = render(".. file-tree:: empty", source(tmp_path))
        assert "bullet_list" not in out

    def test_nonexistent_dir_produces_error(self, filetree):
        out = render(".. file-tree:: no_such_dir", source(filetree))
        assert "system_message" in out
        assert "ERROR" in out


class TestFileTreeDepth:
    def test_depth_zero_returns_empty(self, filetree):
        out = render(".. file-tree:: .\n   :depth: 0", source(filetree))
        assert "bullet_list" not in out

    def test_depth_one_lists_top_level_only(self, filetree):
        out = render(".. file-tree:: .\n   :depth: 1", source(filetree))
        assert "docs" in out
        assert "notes.txt" in out
        # files inside docs/ must not appear
        assert "readme.md" not in out
        assert "guide.md" not in out

    def test_default_depth_shows_direct_children(self, filetree):
        out = render(".. file-tree:: .", source(filetree))
        assert "readme.md" in out
        assert "guide.md" in out
        # images/ contents are at depth 3 — must not appear with depth=2
        assert "logo.png" not in out

    def test_depth_two_explicit_matches_default(self, filetree):
        default = render(".. file-tree:: .", source(filetree))
        explicit = render(".. file-tree:: .\n   :depth: 2", source(filetree))
        assert default == explicit

    def test_depth_three_shows_all(self, filetree):
        out = render(".. file-tree:: .\n   :depth: 3", source(filetree))
        assert "logo.png" in out


class TestFileTreeIncludeFilter:
    def test_matching_files_shown(self, filetree):
        out = render(".. file-tree:: .\n   :include: *.md", source(filetree))
        assert "readme.md" in out
        assert "guide.md" in out

    def test_non_matching_files_hidden(self, filetree):
        out = render(".. file-tree:: .\n   :include: *.md", source(filetree))
        assert "notes.txt" not in out

    def test_dir_with_no_matching_files_hidden(self, filetree):
        # images/ contains only .png — must be hidden when filtering for *.md
        out = render(".. file-tree:: .\n   :include: *.md", source(filetree))
        assert "images" not in out
        assert "logo.png" not in out

    def test_dir_with_matching_files_shown(self, filetree):
        out = render(".. file-tree:: .\n   :include: *.md", source(filetree))
        assert "docs" in out

    def test_include_combined_with_max_depth(self, filetree):
        out = render(
            ".. file-tree:: .\n   :include: *.md\n   :depth: 1",
            source(filetree),
        )
        # docs/ would have matches at depth 2, but max-depth cuts the scan
        assert "readme.md" not in out


class TestFileTreeLinks:
    def test_links_off_by_default(self, filetree):
        out = render(".. file-tree:: .", source(filetree))
        assert "refuri" not in out

    def test_links_adds_refuri_to_files(self, filetree):
        out = render(".. file-tree:: .\n   :links:", source(filetree))
        assert 'refuri="notes.txt"' in out

    def test_links_path_includes_subdirectory(self, filetree):
        out = render(".. file-tree:: .\n   :links:", source(filetree))
        assert 'refuri="docs/readme.md"' in out

    def test_links_dirs_have_no_refuri(self, filetree):
        out = render(".. file-tree:: .\n   :links:", source(filetree))
        # directory names appear as plain text, not as references
        lines_with_docs = [
            ln for ln in out.splitlines() if "docs" in ln
        ]
        assert any("refuri" not in ln for ln in lines_with_docs)

    def test_links_text_is_filename_only(self, filetree):
        out = render(".. file-tree:: .\n   :links:", source(filetree))
        assert ">notes.txt<" in out or "notes.txt" in out
        # full path must not appear as link text
        assert ">docs/readme.md<" not in out

    def test_links_combined_with_subdir_argument(self, filetree):
        # when scanning docs/ directly, paths are relative to source dir
        out = render(".. file-tree:: docs\n   :links:", source(filetree))
        assert 'refuri="docs/guide.md"' in out


class TestFileTreeExclude:
    def test_exclude_hides_matching_files(self, filetree):
        out = render(".. file-tree:: .\n   :exclude: *.txt", source(filetree))
        assert "notes.txt" not in out

    def test_exclude_keeps_non_matching_files(self, filetree):
        out = render(".. file-tree:: .\n   :exclude: *.txt", source(filetree))
        assert "readme.md" in out

    def test_exclude_hides_dir_when_all_files_excluded(self, filetree):
        # images/ contains only .png — hidden when all its files are excluded
        out = render(
            ".. file-tree:: .\n   :include: *.md\n   :exclude: *.png",
            source(filetree),
        )
        assert "images" not in out

    def test_include_and_exclude_combined(self, filetree):
        # include all .md, then exclude readme.md specifically
        out = render(
            ".. file-tree:: .\n   :include: *.md\n   :exclude: readme.md",
            source(filetree),
        )
        assert "guide.md" in out
        assert "readme.md" not in out
        assert "notes.txt" not in out

    def test_exclude_alone_keeps_dirs_with_remaining_files(self, filetree):
        # docs/ has .md files; excluding .txt keeps docs/ visible
        out = render(".. file-tree:: .\n   :exclude: *.txt", source(filetree))
        assert "docs" in out

    def test_exclude_hides_dir_when_all_children_excluded(self, filetree):
        # exclude both .md and .png → docs/ and images/ should disappear
        out = render(
            ".. file-tree:: .\n   :exclude: *.md\n   :depth: 1",
            source(filetree),
        )
        # notes.txt should still be present
        assert "notes.txt" in out


# ---------------------------------------------------------------------------
# mdinclude directive
# ---------------------------------------------------------------------------

pytest.importorskip("m2r2", reason="m2r2 not installed")


class TestStandaloneMdInclude:
    def test_basic_md_content_included(self, tmp_path):
        (tmp_path / "content.md").write_text("Hello **world**")
        out = render(
            ".. mdinclude:: content.md", source(tmp_path), writer="html5",
        )
        assert "Hello" in out
        assert "<strong>world</strong>" in out

    def test_heading_included(self, tmp_path):
        (tmp_path / "doc.md").write_text("# My Title\n\nSome text.")
        out = render(".. mdinclude:: doc.md", source(tmp_path))
        assert "My Title" in out
        assert "Some text." in out

    def test_relative_path_resolved_from_source_dir(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text("Nested content")
        out = render(".. mdinclude:: sub/nested.md", source(tmp_path))
        assert "Nested content" in out

    def test_nonexistent_file_produces_error(self, tmp_path):
        out = render(".. mdinclude:: missing.md", source(tmp_path))
        assert "system_message" in out

    def test_no_sphinx_env_attribute_error_not_raised(self, tmp_path):
        """Directive must work without Sphinx env on document settings."""
        (tmp_path / "simple.md").write_text("Plain text")
        # publish_string does not set settings.env — must not raise
        out = render(".. mdinclude:: simple.md", source(tmp_path))
        assert "Plain text" in out

    def test_start_line_option(self, tmp_path):
        content = "\n".join(f"Line {i}" for i in range(5))
        (tmp_path / "lines.md").write_text(content)
        rst = ".. mdinclude:: lines.md\n   :start-line: 3"
        out = render(rst, source(tmp_path))
        assert "Line 3" in out
        assert "Line 0" not in out

    def test_end_line_option(self, tmp_path):
        content = "\n".join(f"Line {i}" for i in range(5))
        (tmp_path / "lines.md").write_text(content)
        rst = ".. mdinclude:: lines.md\n   :end-line: 2"
        out = render(rst, source(tmp_path))
        assert "Line 0" in out
        assert "Line 4" not in out
