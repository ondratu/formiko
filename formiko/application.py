"""Gtk.Application implementation."""

from os.path import join
from traceback import print_exc

from gi import get_required_version
from gi.repository import Adw
from gi.repository.Gio import ApplicationFlags, SimpleAction
from gi.repository.GLib import (
    LogLevelFlags,
    OptionArg,
    OptionFlags,
    VariantType,
    log_default_handler,
)
from gi.repository.Gtk import Application as GtkApplication  # noqa: F401

from formiko.dialogs import TraceBackDialog, about_dialog
from formiko.editor import EditorType
from formiko.shortcuts import ShortcutsWindow
from formiko.window import AppWindow

# pylint: disable = unused-argument


class Application(Adw.Application):
    """Formiko Application."""

    def __init__(self, application_id="cz.zeropage.Formiko"):
        """Initor."""
        super().__init__(
            application_id=application_id,
            flags=ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.add_main_option(
            "preview",
            ord("p"),
            OptionFlags.NONE,
            OptionArg.NONE,
            "Preview only",
            None,
        )
        self.add_main_option(
            "vim",
            ord("v"),
            OptionFlags.NONE,
            OptionArg.NONE,
            "Use vim as editor",
            None,
        )
        self.add_main_option(
            "source-view",
            ord("s"),
            OptionFlags.NONE,
            OptionArg.NONE,
            "Use SourceView as editor (default)",
            None,
        )

    def do_startup(self):
        """'do_startup' application handler."""
        Adw.Application.do_startup(self)

        action = SimpleAction.new("new-window", None)
        action.connect("activate", self.on_new_window)
        self.add_action(action)

        action = SimpleAction.new("shortcuts", None)
        action.connect("activate", self.on_shortcuts)
        self.add_action(action)

        action = SimpleAction.new("about", None)
        action.connect("activate", self.on_about)
        self.add_action(action)

        action = SimpleAction.new("traceback", VariantType.new("s"))
        action.connect("activate", self.on_traceback)
        self.add_action(action)

        action = SimpleAction.new("quit", None)
        action.connect("activate", self.on_quit)
        self.add_action(action)

        self.set_accels_for_action("app.shortcuts", ["<Control>question"])

    def do_activate(self):
        """'do_activate' application handler."""
        self.new_window(None)

    def do_command_line(self, command_line):
        """'do_command_line' application handler."""
        options = command_line.get_options_dict()
        arguments = command_line.get_arguments()[1:]
        last = arguments[-1:][0] if arguments else ""

        if options.contains("vim"):
            log_default_handler(
                "Application",
                LogLevelFlags.LEVEL_WARNING,
                "Use formiko-vim instead",
                None,
            )
            editor_type = EditorType.VIM
        elif options.contains("source-view"):
            log_default_handler(
                None,
                LogLevelFlags.LEVEL_WARNING,
                "Use formiko instead",
                None,
            )
            editor_type = EditorType.SOURCE
        else:
            editor_type = EditorType.SOURCE

        if self.get_application_id() == "cz.zeropage.Formiko.vim":
            editor_type = EditorType.VIM

        if editor_type == EditorType.VIM and not get_required_version("Vte"):
            log_default_handler(
                None,
                LogLevelFlags.LEVEL_CRITICAL,
                "Vim version needs Vte 2.91 gir!",
                None,
            )
            return 1

        if editor_type == EditorType.SOURCE:
            # vim have disabled accels for conflict itself
            self.set_accels()

        if options.contains("preview") and last and last != "-":
            self.new_window(
                EditorType.PREVIEW,
                join(command_line.get_cwd(), last),
            )
        elif last and last[0] != "-":
            self.new_window(editor_type, join(command_line.get_cwd(), last))
        else:
            self.new_window(editor_type)

        return 0

    def on_quit(self, action, *params):
        """'quit' action handler."""
        self.quit()

    def on_new_window(self, action, *params):
        """'new-window' action handler."""
        self.new_window(
            getattr(
                self.get_active_window(),
                "editor_type",
                EditorType.SOURCE,
            ),
        )

    def on_shortcuts(self, action, param):
        """'shortcuts' action handler."""
        win = ShortcutsWindow(
            getattr(
                self.get_active_window(),
                "editor_type",
                EditorType.SOURCE,
            ),
        )
        self.add_window(win)
        win.present()

    def on_about(self, action, param):
        """'about' action handler."""
        dialog = about_dialog()
        dialog.present(self.get_active_window())

    def on_traceback(self, action, param):
        """'traceback' action handler."""
        dialog = TraceBackDialog(self.get_active_window(), param.get_string())
        dialog.present()

    def new_window(self, editor_type: EditorType, file_name=""):
        """Create new application window."""
        try:
            win = AppWindow(editor_type, file_name)
            self.add_window(win)
            win.present()
        except Exception:  # pylint: disable=broad-exception-caught
            print_exc()

    def set_accels(self):
        """Pair keyboard shorts to actions."""
        self.set_accels_for_action("app.new-window", ["<Control>n"])
        self.set_accels_for_action("app.quit", ["<Control>q"])

        self.set_accels_for_action("win.open-document", ["<Control>o"])
        self.set_accels_for_action("win.save-document", ["<Control>s"])
        self.set_accels_for_action(
            "win.save-document-as",
            ["<Shift><Control>s"],
        )
        self.set_accels_for_action(
            "win.export-document-as",
            ["<Shift><Control>e"],
        )
        self.set_accels_for_action("win.print-document", ["<Control>p"])
        self.set_accels_for_action("win.close-window", ["<Control>w"])
        self.set_accels_for_action("win.find-in-document", ["<Control>f"])
        self.set_accels_for_action("win.find-next-match", ["<Control>g"])
        self.set_accels_for_action(
            "win.find-previous-match",
            ["<Shift><Control>g"],
        )
        self.set_accels_for_action("win.refresh-preview", ["<Control>r"])
        self.set_accels_for_action("win.toggle-sidebar", ["F9"])
        self.set_accels_for_action("win.show-editor", ["<Alt>e"])
        self.set_accels_for_action("win.show-preview", ["<Alt>p"])
        self.set_accels_for_action("win.show-both", ["<Alt>b"])

        # Formatting actions (SOURCE editor only)
        self.set_accels_for_action("fmt.bold-text", ["<Control>b"])
        self.set_accels_for_action("fmt.italic-text", ["<Control>i"])
        self.set_accels_for_action(
            "fmt.strikethrough-text",
            ["<Shift><Control>x"],
        )
        self.set_accels_for_action("fmt.insert-link", ["<Control>k"])
        self.set_accels_for_action("fmt.code-text", ["<Shift><Control>c"])
        self.set_accels_for_action("fmt.blockquote", ["<Shift><Control>q"])
        self.set_accels_for_action("fmt.bullet", ["<Shift><Control>b"])
        self.set_accels_for_action("fmt.ordered", ["<Shift><Control>n"])
        for _level in range(1, 7):
            self.set_accels_for_action(
                f"fmt.header-{_level}",
                [f"<Control>{_level}"],
            )
