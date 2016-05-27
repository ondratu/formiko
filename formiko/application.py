from gi.repository import Gtk, GLib, Gio

from traceback import print_exc

from formiko.window import AppWindow

EDITOR = 'source'       # will be configurable


class Application(Gtk.Application):

    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(
            *args, application_id="cz.zeropage.formiko",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            **kwargs)
        self.add_main_option("preview", ord("p"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Preview only", None)
        self.add_main_option("vim", ord("v"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Use vim as editor", None)
        self.add_main_option("source-view", ord("s"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             "Use SourceView as editor", None)

    def do_startup(self):
        Gtk.Application.do_startup(self)

        action = Gio.SimpleAction.new("new-window", None)
        action.connect("activate", self.on_new_window)
        self.add_action(action)

        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.on_quit)
        self.add_action(action)

    def do_activate(self):
        self.new_window()

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        arguments = command_line.get_arguments()[1:]
        last = arguments[-1:][0] if arguments else ''

        if options.contains("vim"):
            editor = 'vim'
        elif options.contains("source-view"):
            editor = 'source'
        else:
            editor = EDITOR

        if options.contains("preview") and last and last != '-':
            self.new_window(None, last)
        elif last and last[0] != '-':
            self.new_window(editor, last)
        else:
            self.new_window(editor)
        return 0

    def on_quit(self, action, *params):
        self.quit()

    def on_new_window(self, action, *params):
        self.new_window(self.get_active_window().editor_type)

    def new_window(self, editor, file_name=''):
        try:
            win = AppWindow(editor, file_name)
            self.add_window(win)
            win.show_all()
        except:
            print_exc()
            # self.quit()
