from gi.repository.Gtk import Application as GtkApplication
from gi.repository.GLib import OptionFlags, OptionArg, VariantType, \
    log_default_handler, LogLevelFlags
from gi.repository.Gio import ApplicationFlags, SimpleAction

from traceback import print_exc
from os.path import join

from formiko.window import AppWindow
from formiko.dialogs import AboutDialog, TraceBackDialog
from formiko.menu import AppMenu


class Application(GtkApplication):

    def __init__(self, application_id="cz.zeropage.formiko"):
        super(Application, self).__init__(
            application_id=application_id,
            flags=ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("preview", ord("p"), OptionFlags.NONE,
                             OptionArg.NONE, "Preview only", None)
        self.add_main_option("vim", ord("v"), OptionFlags.NONE,
                             OptionArg.NONE, "Use vim as editor", None)
        self.add_main_option("source-view", ord("s"), OptionFlags.NONE,
                             OptionArg.NONE,
                             "Use SourceView as editor (default)", None)

    def do_startup(self):
        GtkApplication.do_startup(self)

        action = SimpleAction.new("new-window", None)
        action.connect("activate", self.on_new_window)
        self.add_action(action)

        action = SimpleAction.new("about", None)
        action.connect("activate", self.on_about)
        self.add_action(action)

        action = SimpleAction.new("traceback", VariantType.new('s'))
        action.connect("activate", self.on_traceback)
        self.add_action(action)

        action = SimpleAction.new("quit", None)
        action.connect("activate", self.on_quit)
        self.add_action(action)

        self.set_app_menu(AppMenu())

    def do_activate(self):
        self.new_window()

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        arguments = command_line.get_arguments()[1:]
        last = arguments[-1:][0] if arguments else ''

        if options.contains("vim"):
            log_default_handler("Application", LogLevelFlags.LEVEL_WARNING,
                                "Use formiko-vim instead", 0)
            editor = 'vim'
        elif options.contains("source-view"):
            log_default_handler("Application", LogLevelFlags.LEVEL_WARNING,
                                "Use formiko instead", 0)
            editor = 'source'
        else:
            editor = 'source'
        if editor == 'source':  # vim have disabled accels for conflict itself
            self.set_accels()

        if self.get_application_id() == "cz.zeropage.formiko.vim":
            editor = 'vim'

        if options.contains("preview") and last and last != '-':
            self.new_window(None, join(command_line.get_cwd(), last))
        elif last and last[0] != '-':
            self.new_window(editor, join(command_line.get_cwd(), last))
        else:
            self.new_window(editor)

        return 0

    def on_quit(self, action, *params):
        self.quit()

    def on_new_window(self, action, *params):
        self.new_window(self.get_active_window().editor_type or 'source')

    def on_about(self, action, param):
        dialog = AboutDialog(None)
        dialog.present()

    def on_traceback(self, action, param):
        dialog = TraceBackDialog(self.get_active_window(), param.get_string())
        dialog.present()

    def new_window(self, editor, file_name=''):
        try:
            win = AppWindow(editor, file_name)
            self.add_window(win)
            win.show_all()
        except:
            print_exc()
            # self.quit()

    def set_accels(self):
        self.set_accels_for_action("app.new-window", ["<Control>n"])
        self.set_accels_for_action("app.quit", ["<Control>q"])

        self.set_accels_for_action("win.open-document", ["<Control>o"])
        self.set_accels_for_action("win.save-document", ["<Control>s"])
        self.set_accels_for_action("win.save-document-as",
                                   ["<Shift><Control>s"])
        self.set_accels_for_action("win.export-document-as",
                                   ["<Shift><Control>e"])
        self.set_accels_for_action("win.close-window", ["<Control>w"])
