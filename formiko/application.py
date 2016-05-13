from gi.repository import Gtk, GLib, Gio

from traceback import print_exc

from formiko.window import AppWindow


class Application(Gtk.Application):

    def __init__(self, *args, **kwargs):
        super(Application, self).__init__(
            *args, application_id="cz.zeropage.formiko",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            **kwargs)
        self.add_main_option("preview", ord("p"), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE, "Preview only", None)

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

        if options.contains("preview") and last and last != '-':
            self.new_window(last, True)
        elif last and last[0] != '-':
            self.new_window(last)
        else:
            self.new_window()
        return 0

    def on_quit(self, action, *params):
        self.quit()

    def on_new_window(self, action, *params):
        # print self.get_active_window()
        self.new_window()

    def new_window(self, file_name=None, preview=False):
        try:
            win = AppWindow(file_name, preview)
            self.add_window(win)
            win.show_all()
        except:
            print_exc()
            self.quit()
