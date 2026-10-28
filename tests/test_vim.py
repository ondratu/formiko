"""Tests for the Neovim terminal widget logic, with Vte/pynvim stubbed.

The real ``Vte`` and ``pynvim`` are optional; stand-ins are injected so the
module's own logic is exercised on machines that do not have them.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

VIM_SOURCE = Path(__file__).parent.parent / "formiko" / "vim.py"


@pytest.fixture
def vim(monkeypatch):
    """Load ``formiko/vim.py`` as a private module with stubbed imports."""
    import gi.repository

    class _Terminal:
        pass

    fake_vte = types.ModuleType("gi.repository.Vte")
    fake_vte.Terminal = _Terminal
    fake_nvim = types.ModuleType("pynvim")
    fake_nvim.Nvim = object
    monkeypatch.setitem(sys.modules, "gi.repository.Vte", fake_vte)
    monkeypatch.setattr(gi.repository, "Vte", fake_vte, raising=False)
    monkeypatch.setitem(sys.modules, "pynvim", fake_nvim)

    spec = importlib.util.spec_from_file_location(
        "formiko_vim_under_test", VIM_SOURCE,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _editor(vim, alive=True, file_name=""):
    editor = vim.VimEditor.__new__(vim.VimEditor)
    editor._nvim_alive = alive
    editor._VimEditor__file_name = file_name
    editor.nvim = Mock()
    editor.emit = Mock()
    return editor


def test_nvim_call_returns_default_when_dead(vim):
    """A dead Neovim is never called."""
    editor = _editor(vim, alive=False)
    fn = Mock()
    assert editor._nvim_call(fn, default="x") == "x"
    fn.assert_not_called()


def test_nvim_call_returns_result(vim):
    """A living Neovim result is passed through."""
    editor = _editor(vim)
    assert editor._nvim_call(lambda: 42) == 42


def test_nvim_call_marks_dead_on_eof(vim):
    """EOF means Neovim exited; the default is returned and state updated."""
    editor = _editor(vim)

    def broken():
        raise EOFError

    assert editor._nvim_call(broken, default=5) == 5
    assert editor._nvim_alive is False


def test_remote_expr_and_send_use_nvim(vim):
    """Expressions are evaluated and commands run through pynvim."""
    editor = _editor(vim)
    editor.nvim.eval.return_value = 3
    assert editor.vim_remote_expr("x") == 3
    editor.nvim.eval.assert_called_once_with("x")
    editor.vim_remote_send(":w")
    editor.nvim.command.assert_called_once_with(":w")


def test_nvim_exited_marks_dead(vim):
    """The child-exited handler flips the alive flag."""
    editor = _editor(vim)
    editor._on_nvim_exited()
    assert editor._nvim_alive is False


def test_counters_default_to_zero_when_dead(vim):
    """Changes and lines are zero without Neovim."""
    editor = _editor(vim, alive=False)
    assert editor.get_vim_changes() == 0
    assert editor.get_vim_lines() == 0


def test_get_buffer_joins_lines(vim):
    """Buffer lines are joined with newlines."""
    editor = _editor(vim)
    editor.nvim.eval.return_value = ["a", "b", "c"]
    assert editor.get_vim_get_buffer(3) == "a\nb\nc"
    editor.nvim.eval.assert_called_once_with("getline(0, 3)")


def test_get_pos_returns_row_and_column(vim):
    """The cursor position is (row, col) from getpos()."""
    editor = _editor(vim)
    editor.nvim.eval.return_value = [0, 7, 3, 0]
    assert editor.get_vim_pos() == (7, 3)


def test_get_pos_defaults_when_dead(vim):
    """Without Neovim the position is 0, 0."""
    assert _editor(vim, alive=False).get_vim_pos() == (0, 0)


@pytest.mark.parametrize(
    ("row", "total", "expected"),
    [(1, 11, 0.0), (6, 11, 0.5), (11, 11, 1.0), (1, 1, 0.0), (1, 0, 0.0)],
)
def test_scroll_pos_is_row_fraction(vim, row, total, expected):
    """Scroll position is the cursor row as a fraction of the document."""
    editor = _editor(vim)
    editor.nvim.eval.return_value = [0, row, 1, 0]
    assert editor.get_vim_scroll_pos(total) == pytest.approx(expected)


def test_file_path_falls_back_to_stored_name(vim):
    """When Neovim has no path the stored file name is used."""
    editor = _editor(vim, alive=False, file_name="/x.rst")
    assert editor.get_vim_file_path() == "/x.rst"
    assert editor.file_path == "/x.rst"


def test_is_modified(vim):
    """Modified state comes from the buffer option."""
    editor = _editor(vim)
    editor.nvim.eval.return_value = 1
    assert editor.is_modified is True
    assert _editor(vim, alive=False).is_modified is False


def test_file_name_emits_file_type_on_change(vim):
    """A different buffer name announces its extension."""
    editor = _editor(vim, file_name="a.rst")
    editor.nvim.eval.return_value = "b.md"
    assert editor.file_name == "b.md"
    editor.emit.assert_called_once_with("file-type", ".md")


def test_file_name_unchanged_does_not_emit(vim):
    """The same name does not repeat the signal."""
    editor = _editor(vim, file_name="a.rst")
    editor.nvim.eval.return_value = "a.rst"
    assert editor.file_name == "a.rst"
    editor.emit.assert_not_called()


def test_read_from_file_opens_in_nvim(vim):
    """Reading a file announces its type and edits it in Neovim."""
    editor = _editor(vim)
    editor.read_from_file("/d/n.rst")
    editor.emit.assert_called_once_with("file-type", ".rst")
    editor.nvim.command.assert_called_once_with("e /d/n.rst")
    assert editor._VimEditor__file_name == "/d/n.rst"


def test_save_is_logged_as_unsupported(vim, monkeypatch):
    """Saving through the widget is not supported and is logged."""
    logged = []
    monkeypatch.setattr(vim, "error", logged.append)
    editor = _editor(vim)
    editor.save(None)
    editor.save_as()
    assert len(logged) == 2


def test_vim_quit_calls_nvim(vim):
    """Quitting sends quit to Neovim."""
    editor = _editor(vim)
    editor.vim_quit()
    editor.nvim.quit.assert_called_once_with()
