"""Tests for file browser state and file discovery."""

from formiko.filebrowser_model import FileBrowserModel


def _make_model(default_directory="/documents"):
    return FileBrowserModel(
        default_directory=default_directory,
        file_filter=lambda name: name.endswith((".md", ".rst")),
    )


def test_set_directory_only_records_the_directory():
    """set_directory() never loads files."""
    model = _make_model()
    model.set_directory("/project")
    assert model.directory == "/project"
    assert model.files == ()


def test_set_directory_falls_back_to_default_for_empty_directory():
    """An empty directory uses the default one."""
    model = _make_model()
    model.set_directory("")
    assert model.directory == "/documents"


def test_refresh_lists_known_files_only(tmp_path):
    """refresh() loads known files from the current directory."""
    (tmp_path / "doc.md").write_text("hi")
    (tmp_path / "notes.bin").write_bytes(b"\x00")
    model = _make_model()
    model.set_directory(str(tmp_path))
    model.refresh()
    assert model.files == ("doc.md",)


def test_refresh_clears_previous_rows_first(tmp_path):
    """A second refresh() replaces stale files instead of appending."""
    (tmp_path / "a.md").write_text("a")
    model = _make_model()
    model.set_directory(str(tmp_path))
    model.refresh()
    (tmp_path / "a.md").unlink()
    (tmp_path / "b.md").write_text("b")
    model.refresh()
    assert model.files == ("b.md",)


def test_refresh_does_nothing_without_a_directory():
    """refresh() is a no-op before any directory is set."""
    model = _make_model(default_directory="")
    model.refresh()
    assert model.files == ()


def test_clear_empties_the_list_without_touching_the_directory(tmp_path):
    """clear() removes files but keeps the current directory."""
    (tmp_path / "a.md").write_text("a")
    model = _make_model()
    model.set_directory(str(tmp_path))
    model.refresh()
    model.clear()
    assert model.files == ()
    assert model.directory == str(tmp_path)
