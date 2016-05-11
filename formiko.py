#!/usr/bin/python
# -*- coding: utf-8 -*-

from docutils.core import publish_string
# from docutils_tinyhtml import Writer
from docutils.writers.html4css1 import Writer

from gi import require_version
from gi.repository import Gtk, Gdk, GLib, WebKit, Gio

from subprocess import Popen, PIPE, check_output
from threading import Thread
from uuid import uuid4
from io import StringIO
from traceback import print_exc
from sys import argv
from os import stat

__version__ = "0.1.0"
__author__ = "Ondřej Tůma <mcbig@zeropage.cz>"
require_version('Gtk', '3.0')


class VimEditor(Gtk.Socket):
    def __init__(self, app_window, server_name, file_name=None):
        super(VimEditor, self).__init__()
        self.server_name = server_name
        self.file_name = file_name
        self.connect("plug-removed", app_window.destroy_from_vim)
        self.connect("hierarchy-changed", self.hierarchy_changed)

    def hierarchy_changed(self, widget, previous_toplevel, *args):
        if previous_toplevel is None:
            self.vim_start_server()

    def vim_start_server(self):
        args = [
            "/usr/bin/gvim",
            "--socketid", str(self.get_id()),
            "--servername", self.server_name,
            "--echo-wid",
            # no menu (m) a no toolbar (T)
            "-c", "set go-=m go-=T filetype=rst"]
        if self.file_name:
            args.append(self.file_name)
        server = Popen(args, stdout=PIPE)
        server.stdout.readline()    # read wid, so server was started
        self.show()

    def vim_remote_expr(self, command):
        out = check_output([
            "/usr/bin/vim",
            "--servername", self.server_name,
            "--remote-expr", command
            ])
        return out.decode('utf-8').strip()

    def vim_remote_send(self, command):
        check_output([
            "/usr/bin/vim",
            "--servername", self.server_name,
            "--remote-send", command
            ])

    def get_vim_changes(self):
        try:
            return int(self.vim_remote_expr("b:changedtick"))
        except:
            return 0

    def get_vim_lines(self):
        return int(self.vim_remote_expr("line('$')"))

    def get_vim_get_buffer(self, count):
        return self.vim_remote_expr("getline(0, %d)" % count)

    def get_vim_pos(self):
        buff, row, col, off = self.vim_remote_expr("getpos('.')").split('\n')
        return int(row), int(col)

    def get_vim_file_path(self):
        return self.vim_remote_expr("expand('%:p')")

    def get_vim_file_name(self):
        return self.vim_remote_expr("@%")

    def get_vim_is_modified(self):
        return bool(int(self.vim_remote_expr("&l:modified")))

    def get_vim_encoding(self):
        return self.vim_remote_expr("&l:encoding")

    def get_vim_filetype(self):
        return self.vim_remote_expr("&l:filetype")

    def vim_quit(self):
        self.vim_remote_send("<ESC>:q! <CR>")


class Renderer(Gtk.ScrolledWindow):
    def __init__(self):
        super(Renderer, self).__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC,
                        Gtk.PolicyType.AUTOMATIC)
        self.webview = WebKit.WebView()
        self.sb = self.get_vscrollbar()
        self.add(self.webview)
        self.writer = Writer()

    def render(self, app_win, rst, row=0, col=0):
        try:
            k = 0
            for i in range(row-1):
                k = rst.find('\n', k)+1
            k += col
            a, b = len(rst[:k]), len(rst[k:])
            position = (float(a)/(a+b)) if a or b else 0
            html = publish_string(
                source=rst,
                writer=self.writer,
                writer_name='html',
                settings_overrides={
                    'warning_stream': StringIO()
                }).decode('utf-8')
            html += """
                <script>
                  window.scrollTo(
                     0,
                     (document.documentElement.scrollHeight-window.innerHeight)*%f)
                </script>
            """ % position
            if not app_win.runing:
                return
            self.webview.load_string(html, "text/html", "UTF-8", "file:///")
        except:
            print_exc()


class AboutDialog(Gtk.AboutDialog):
    def __init__(self):
        super(AboutDialog, self).__init__()
        self.set_program_name("Formiko")
        self.set_version(__version__)
        self.set_copyright("(c) 2016 Ondřej Tůma")
        # self.set_website("https://github.com/ondratu/formiko")
        # self.set_website("https://formiko.zeropage.cz")
        self.set_authors([__author__])
        # self.set_logo("formiko.svg")


class QuitDialogWithoutSave(Gtk.MessageDialog):
    def __init__(self, parent, file_name):
        super(QuitDialogWithoutSave, self).__init__(
            parent,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK_CANCEL,
            "File %s not saved.\n"
            "Are you sure to quite without save ?" % file_name)


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, application, file_name=None, preview=False):
        self.server_name = str(uuid4())
        self.runing = True
        self.preview = file_name if preview else None
        self.__application = application
        application.hold()
        super(AppWindow, self).__init__()
        self.connect("delete-event", self.on_delete)
        self.set_title("Formiko")
        self.set_icon(self.render_icon(Gtk.STOCK_EDIT, Gtk.IconSize.DIALOG))
        self.layout(file_name)

        self.__last_changes = 0
        self.__file_name = ''
        GLib.timeout_add(200, self.check_in_thread)

    def __del__(self):
        self.__application.release()

    def on_delete(self, *args):
        if not self.preview:
            # TODO: move next code to extra method...
            if self.editor.get_vim_is_modified():
                dialog = QuitDialogWithoutSave(self,
                                               self.editor.get_vim_file_name())
                if dialog.run() != Gtk.ResponseType.OK:
                    dialog.destroy()
                    return True
            self.runing = False
            self.editor.vim_quit()
        else:
            self.runing = False

    def win_destroy(self, *args):
        if not self.preview:
            if self.editor.get_vim_is_modified():
                dialog = QuitDialogWithoutSave(self,
                                               self.editor.get_vim_file_name())
                if dialog.run() != Gtk.ResponseType.OK:
                    dialog.destroy()
                    return
            self.runing = False
            self.editor.vim_quit()  # do call destroy_from_vim
        else:
            self.runing = False
            self.destroy()

    def destroy_from_vim(self, *args):
        self.runing = False
        self.destroy()

    def fill_toolbar(self, toolbar):
        tb_quit = Gtk.ToolButton(Gtk.STOCK_QUIT)
        tb_quit.connect("clicked", self.win_destroy)
        toolbar.insert(tb_quit, -1)
        tb_new = Gtk.ToolButton(Gtk.STOCK_NEW)
        tb_new.set_action_name("app.new-window")
        toolbar.insert(tb_new, -1)
        tb_open = Gtk.ToolButton(Gtk.STOCK_OPEN)
        tb_open.connect("clicked", self.open_file)
        toolbar.insert(tb_open, -1)
        tb_about = Gtk.ToolButton(Gtk.STOCK_ABOUT)
        toolbar.insert(tb_about, -1)
        tb_about.set_action_name("app.about")

    def fill_panned(self, file_name):
        self.paned.set_position(400)
        self.editor = VimEditor(self, self.server_name, file_name)
        self.paned.add1(self.editor)
        self.renderer = Renderer()
        self.paned.add2(self.renderer)

    def layout(self, file_name):
        self.set_default_size(800, 600)
        box = Gtk.VBox()
        self.add(box)

        toolbar = Gtk.Toolbar()
        box.pack_start(toolbar, False, False, 0)
        self.fill_toolbar(toolbar)

        if not self.preview:
            self.paned = Gtk.HPaned()
            box.pack_start(self.paned, True, True, 0)
            self.fill_panned(file_name)
        else:
            self.renderer = Renderer()
            box.pack_start(self.renderer, True, True, 0)
    # enddef

    def check_in_thread(self):
        if self.runing:
            if not self.preview:
                thread = Thread(target=self.refresh_from_vim)
            else:
                thread = Thread(target=self.refresh_from_file)
            thread.start()

    def refresh_from_vim(self):
        try:
            if not self.runing:
                return
            last_changes = self.editor.get_vim_changes()
            if not self.runing:
                return
            file_name = self.editor.get_vim_file_name()
            if last_changes > self.__last_changes \
                    or file_name != self.__file_name:
                self.set_title(("%s - " % file_name if file_name else '') +
                               "Formiko")
                self.__file_name = file_name
                self.__last_changes = last_changes
                if not self.runing:
                    return
                lines = self.editor.get_vim_lines()
                if not self.runing:
                    return
                buff = self.editor.get_vim_get_buffer(lines)
                if not self.runing:
                    return
                row, col = self.editor.get_vim_pos()
                GLib.idle_add(self.renderer.render, self, buff, row, col)
            GLib.timeout_add(100, self.check_in_thread)
        except:
            print_exc()

    def refresh_from_file(self):
        try:
            last_changes = stat(self.preview).st_ctime
            if last_changes > self.__last_changes:
                self.__last_changes = last_changes
                with open(self.preview) as source:
                    buff = source.read()
                    GLib.idle_add(self.renderer.render, self, buff)
        except:
            print_exc()
        GLib.timeout_add(500, self.check_in_thread)

    def open_file(self, *args):
        dialog = Gtk.FileChooserDialog(
            "Open file",
            self,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.REJECT,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        filter_rst = Gtk.FileFilter()
        filter_rst.set_name("reSructuredText")
        filter_rst.add_pattern("*.rst")
        filter_rst.add_pattern("*.RST")
        dialog.add_filter(filter_rst)

        filter_txt = Gtk.FileFilter()
        filter_txt.set_name("plain text")
        filter_txt.add_mime_type("plain/text")
        dialog.add_filter(filter_txt)

        filter_all = Gtk.FileFilter()
        filter_all.set_name("all files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        if dialog.run() == Gtk.ResponseType.OK:
            self.__application.new_window(dialog.get_filename())
        dialog.destroy()


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

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self.on_about)
        self.add_action(action)

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
        elif last and last != '-':
            self.new_window(last)
        else:
            self.new_window()
        return 0

    def on_about(self, action, *params):
        dialog = AboutDialog()
        dialog.present()
        # print(action, param)
        # about_dialog = Gtk.AboutDialog(transient_for=self.window, modal=True)
        # about_dialog.present()

    def on_quit(self, action, *params):
        self.quit()

    def on_new_window(self, action, *params):
        self.new_window()

    def new_window(self, file_name=None, preview=False):
        win = AppWindow(self, file_name, preview)
        win.show_all()
        self.add_window(win)


if __name__ == "__main__":
    Gdk.threads_init()
    app = Application()
    exit(app.run(argv))
