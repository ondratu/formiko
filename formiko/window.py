# -*- coding: utf-8 -*-
from gi.repository import Gtk, GLib

from threading import Thread
from uuid import uuid4
from traceback import print_exc
from os import stat

from formiko.vim import VimEditor
from formiko.renderer import Renderer
from formiko.dialogs import QuitDialogWithoutSave, AboutDialog


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, file_name=None, preview=False):
        self.server_name = str(uuid4())
        self.runing = True
        self.preview = file_name if preview else None
        super(AppWindow, self).__init__()
        self.connect("delete-event", self.on_delete)
        self.set_title("Formiko")
        self.set_icon(self.render_icon(Gtk.STOCK_EDIT, Gtk.IconSize.DIALOG))
        self.layout(file_name)

        self.__last_changes = 0
        self.__file_name = ''
        GLib.timeout_add(200, self.check_in_thread)

    def __del__(self):
        pass

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
        tb_about.connect("clicked", self.about)
        toolbar.insert(tb_about, -1)
        tb_new = Gtk.ToolButton(Gtk.STOCK_NEW)
        tb_new.set_action_name("app.test")
        toolbar.insert(tb_new, -1)

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
            self.get_application().new_window(dialog.get_filename())
        dialog.destroy()

    def about(self, *args):
        dialog = AboutDialog(self)
        dialog.present()
