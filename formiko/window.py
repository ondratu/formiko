# -*- coding: utf-8 -*-
from gi.repository import Gtk, GLib

from threading import Thread
from uuid import uuid4
from traceback import print_exc
from os import stat

from formiko.vim import VimEditor
from formiko.sourceview import SourceView
from formiko.renderer import Renderer
from formiko.dialogs import QuitDialogWithoutSave, AboutDialog


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, editor, file_name=''):
        assert editor in ('vim', 'source', None)
        self.server_name = str(uuid4())
        self.runing = True
        self.editor = editor
        super(AppWindow, self).__init__()
        self.connect("delete-event", self.on_delete)
        self.set_title("Formiko")
        self.set_icon(self.render_icon(Gtk.STOCK_EDIT, Gtk.IconSize.DIALOG))
        self.layout(file_name)

        self.__last_changes = 0
        self.__file_name = file_name
        GLib.timeout_add(200, self.check_in_thread)

    def __del__(self):
        pass

    def ask_if_modified(self):
        if self.editor:
            if self.editor.is_modified:
                dialog = QuitDialogWithoutSave(self,
                                               self.editor.file_name)
                if dialog.run() != Gtk.ResponseType.OK:
                    dialog.destroy()
                    return False        # fo not quit
            self.runing = False
            if isinstance(self.editor, VimEditor):
                self.editor.vim_quit()  # do call destroy_from_vim
        else:
            self.runing = False
        return True                     # do quit

    def on_delete(self, *args):
        return not self.ask_if_modified()

    def win_destroy(self, *args):
        if self.ask_if_modified():
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
        tb_about.connect("clicked", self.about)
        toolbar.insert(tb_about, -1)
        tb_new = Gtk.ToolButton(Gtk.STOCK_NEW)
        tb_new.set_action_name("app.test")
        toolbar.insert(tb_new, -1)

    def fill_panned(self, file_name):
        self.paned.set_position(400)
        if self.editor == 'vim':
            self.editor = VimEditor(self, self.server_name, file_name)
        else:
            self.editor = SourceView(file_name)
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

        if self.editor:
            self.paned = Gtk.HPaned()
            box.pack_start(self.paned, True, True, 0)
            self.fill_panned(file_name)
        else:
            self.renderer = Renderer()
            box.pack_start(self.renderer, True, True, 0)
    # enddef

    def check_in_thread(self):
        if self.runing:
            if isinstance(self.editor, VimEditor):
                thread = Thread(target=self.refresh_from_vim)
            elif isinstance(self.editor, SourceView):
                thread = Thread(target=self.refresh_from_source)
            else:   # self.editor = None
                thread = Thread(target=self.refresh_from_file)
            thread.start()

    def refresh_from_vim(self):
        try:
            if not self.runing:
                return
            last_changes = self.editor.get_vim_changes()
            if not self.runing:
                return
            file_name = self.editor.file_name
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
                pos = 0
                for i in range(row-1):
                    pos = buff.find('\n', pos)+1
                pos += col
                GLib.idle_add(self.renderer.render, self, buff, pos)
            GLib.timeout_add(100, self.check_in_thread)
        except:
            print_exc()

    def refresh_from_source(self):
        try:
            last_changes = self.editor.changes
            if last_changes > self.__last_changes:
                self.__last_changes = last_changes
                GLib.idle_add(self.renderer.render, self,
                              self.editor.text, self.editor.position)
            GLib.timeout_add(100, self.check_in_thread)
        except:
            print_exc()

    def refresh_from_file(self):
        try:
            last_changes = stat(self.file_name).st_ctime
            if last_changes > self.__last_changes:
                self.__last_changes = last_changes
                with open(self.file_name) as source:
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
            self.get_application().new_window(dialog.get_filename())
        dialog.destroy()

    def about(self, *args):
        dialog = AboutDialog(self)
        dialog.present()
