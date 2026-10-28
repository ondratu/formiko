"""Display-less tests for command line handling and entry points."""

import contextlib
from unittest.mock import Mock

import gi
import pytest

gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")
with contextlib.suppress(ValueError):
    gi.require_version("Spelling", "1")

from formiko import __main__ as entry  # noqa: E402
from formiko import application  # noqa: E402
from formiko.application import Application  # noqa: E402
from formiko.editor import EditorType  # noqa: E402


class _Options:
    def __init__(self, *names):
        self.names = names

    def contains(self, name):
        return name in self.names


def _command_line(arguments, *options, cwd="/work"):
    return Mock(
        **{
            "get_options_dict.return_value": _Options(*options),
            "get_arguments.return_value": ["formiko", *arguments],
            "get_cwd.return_value": cwd,
        },
    )


@pytest.fixture
def app():
    """Application with window creation replaced by mocks."""
    obj = Application()
    obj.new_window = Mock()
    obj.open_files_in_new_window = Mock()
    obj.open_files_in_new_tab = Mock()
    obj.set_accels = Mock()
    obj.show_missing_dependency = Mock()
    return obj


def test_set_accels_registers_unique_shortcuts():
    """Every accelerator is bound once and the header levels 1-6 exist."""
    bound = {}
    obj = Application()
    obj.set_accels_for_action = lambda action, accels: bound.update(
        {action: list(accels)},
    )
    obj.set_accels()

    assert bound["app.quit"] == ["<Control>q"]
    assert bound["win.new-tab"] == ["<Control>t"]
    assert bound["fmt.bold-text"] == ["<Control>b"]
    for level in range(1, 7):
        assert bound[f"fmt.header-{level}"] == [f"<Control>{level}"]

    all_accels = [a for accels in bound.values() for a in accels]
    assert len(all_accels) == len(set(all_accels)), "duplicate shortcut"


def test_default_command_line_opens_last_file(app):
    """Without mode flags the last file opens in a new window."""
    result = app.do_command_line(_command_line(["a.rst", "b.rst"]))

    assert result == 0
    app.set_accels.assert_called_once_with()
    app.new_window.assert_called_once_with(EditorType.SOURCE, "/work/b.rst")


def test_command_line_without_files_opens_empty_window(app):
    """No files means an empty window."""
    app.do_command_line(_command_line([]))
    app.new_window.assert_called_once_with(EditorType.SOURCE)


def test_command_line_skips_options_and_stdin_marker(app):
    """Dashes and empty arguments are not file names."""
    app.do_command_line(_command_line(["-", "--x", "", "a.rst"]))
    app.new_window.assert_called_once_with(EditorType.SOURCE, "/work/a.rst")


def test_absolute_path_is_kept(app):
    """An absolute argument ignores the working directory."""
    app.do_command_line(_command_line(["/abs/a.rst"]))
    app.new_window.assert_called_once_with(EditorType.SOURCE, "/abs/a.rst")


def test_source_view_option_warns_and_uses_source_editor(app):
    """The deprecated --source-view still opens the normal editor."""
    app.do_command_line(_command_line([], "source-view"))
    app.new_window.assert_called_once_with(EditorType.SOURCE)


def test_vim_without_vte_fails(app, monkeypatch):
    """The vim editor needs the Vte typelib."""
    monkeypatch.setattr(application, "get_required_version", lambda _n: None)
    assert app.do_command_line(_command_line([], "vim")) == 1
    app.new_window.assert_not_called()


def test_vim_without_pynvim_reports_dependency(app, monkeypatch):
    """The vim editor needs pynvim, otherwise the user is told."""
    monkeypatch.setattr(application, "get_required_version", lambda _n: "3.91")
    monkeypatch.setattr(application, "find_spec", lambda _n: None)
    assert app.do_command_line(_command_line([], "vim")) == 0
    app.show_missing_dependency.assert_called_once_with("pynvim")
    app.new_window.assert_not_called()


def test_vim_application_id_selects_vim_editor(monkeypatch):
    """The formiko-vim application id forces the vim editor, no accels."""
    monkeypatch.setattr(application, "get_required_version", lambda _n: "3.91")
    monkeypatch.setattr(application, "find_spec", lambda _n: object())
    obj = Application(application_id="cz.zeropage.Formiko.vim")
    obj.set_accels = Mock()
    obj.new_window = Mock()
    obj.do_command_line(_command_line([]))
    obj.set_accels.assert_not_called()
    obj.new_window.assert_called_once_with(EditorType.VIM)


def test_preview_option_overrides_editor_type(app):
    """--preview opens the preview-only editor."""
    app._open_command_line_files(_Options("preview"), EditorType.SOURCE, [])
    app.new_window.assert_called_once_with(EditorType.PREVIEW)


def test_new_window_option_uses_single_window(app):
    """--new-window delegates all files to one window."""
    app._open_command_line_files(
        _Options("new-window"), EditorType.SOURCE, ["a", "b"],
    )
    app.open_files_in_new_window.assert_called_once_with(
        EditorType.SOURCE, ["a", "b"],
    )


def test_new_tab_option_uses_tabs(app):
    """--new-tab delegates to the tab opener."""
    app._open_command_line_files(
        _Options("new-tab"), EditorType.SOURCE, ["a"],
    )
    app.open_files_in_new_tab.assert_called_once_with(
        EditorType.SOURCE, ["a"],
    )


def test_new_window_takes_precedence_over_new_tab(app):
    """When both flags are given, new-window wins."""
    app._open_command_line_files(
        _Options("new-window", "new-tab"), EditorType.SOURCE, ["a"],
    )
    app.open_files_in_new_window.assert_called_once()
    app.open_files_in_new_tab.assert_not_called()


def test_new_window_returns_none_when_window_fails(monkeypatch, capsys):
    """A crash while creating the window is printed and swallowed."""
    monkeypatch.setattr(
        application, "AppWindow", Mock(side_effect=RuntimeError("boom")),
    )
    obj = Application()
    assert obj.new_window(EditorType.SOURCE) is None
    assert "RuntimeError" in capsys.readouterr().err


def test_open_files_in_new_window_survives_failed_window():
    """No tabs are opened when the window could not be created."""
    obj = Application()
    obj.new_window = Mock(return_value=None)
    assert obj.open_files_in_new_window(EditorType.SOURCE, ["a", "b"]) is None


def test_open_files_in_new_window_without_files():
    """No files means an empty first window."""
    obj = Application()
    obj.new_window = Mock(return_value=Mock())
    obj.open_files_in_new_window(EditorType.SOURCE, [])
    obj.new_window.assert_called_once_with(EditorType.SOURCE, "")


@pytest.mark.parametrize(
    ("func", "app_id"),
    [
        (entry.main, "cz.zeropage.Formiko"),
        (entry.main_vim, "cz.zeropage.Formiko.vim"),
    ],
)
def test_entry_points_run_application(monkeypatch, func, app_id):
    """Both entry points create the right application and run it."""
    created = {}

    class _App:
        def __init__(self, **kwargs):
            created["kwargs"] = kwargs

        def run(self, argv):
            created["argv"] = argv
            return 7

    handlers = []
    monkeypatch.setattr(entry, "Application", _App)
    monkeypatch.setattr(entry, "signal", lambda *a: handlers.append(a))
    monkeypatch.setattr(entry.sys, "argv", ["formiko", "x"])

    assert func() == 7
    assert created["argv"] == ["formiko", "x"]
    assert handlers[0][0] == entry.SIGINT
    if func is entry.main_vim:
        assert created["kwargs"] == {"application_id": app_id}
    else:
        assert created["kwargs"] == {}


def test_sigint_handler_exits_with_error():
    """Ctrl+C terminates with exit code 1."""
    with pytest.raises(SystemExit) as info:
        entry.handler_exit()
    assert info.value.code == 1


@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="on_traceback() passes (window, text) but TraceBackDialog "
    "only accepts the traceback text",
)
def test_on_traceback_shows_dialog(monkeypatch):
    """The traceback action presents a dialog with the given text."""
    dialog = Mock()

    def real_signature(traceback):  # mirrors TraceBackDialog.__init__
        assert traceback == "tb"
        return dialog

    monkeypatch.setattr(application, "TraceBackDialog", real_signature)
    obj = Application()
    obj.get_active_window = Mock(return_value=None)
    obj.on_traceback(None, Mock(**{"get_string.return_value": "tb"}))
    dialog.present.assert_called_once_with()
