from gi.repository import Gtk, GtkSource, Pango, GLib

from os.path import splitext, basename
from io import open
from traceback import print_exc
from sys import version_info

from formiko.dialogs import FileSaveDialog

default_manager = GtkSource.LanguageManager.get_default()
rst_lang = default_manager.get_language('rst')
markdown_lang = default_manager.get_language('markdown')


class SourceView(Gtk.ScrolledWindow):
    __file_name = ''
    __last_changes = 0

    def __init__(self, file_name=''):
        super(Gtk.ScrolledWindow, self).__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.text_buffer = GtkSource.Buffer.new_with_language(rst_lang)
        if file_name:
            self.read_from_file(file_name)
        self.text_buffer.connect("changed", self.inc_changes)
        self.source_view = GtkSource.View.new_with_buffer(self.text_buffer)
        self.source_view.set_auto_indent(True)
        self.source_view.set_show_line_numbers(True)
        self.source_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.source_view.override_font(
            Pango.FontDescription.from_string('Monospace'))
        # self.source_view.set_monospace(True) since 3.16
        self.add(self.source_view)

    @property
    def changes(self):
        return self.__last_changes

    @property
    def is_modified(self):
        return self.text_buffer.get_modified()

    @property
    def text(self):
        return self.text_buffer.get_text(self.text_buffer.get_start_iter(),
                                         self.text_buffer.get_end_iter(),
                                         True)

    @property
    def position(self):
        cursor = self.text_buffer.get_insert()
        return self.text_buffer.get_iter_at_mark(cursor).get_offset()

    @property
    def file_name(self):
        return basename(self.__file_name)

    def inc_changes(self, text_buffer):
        self.__last_changes += 1

    def read_from_file(self, file_name):
        self.__file_name = file_name
        name, ext = splitext(file_name)
        language = markdown_lang if ext == '.md' else rst_lang
        if self.text_buffer.get_language() != language:
            self.text_buffer.set_language(language)

        with open(file_name, 'r', encoding="utf-8") as src:
            self.text_buffer.set_text(src.read())
            self.__last_changes += 1
        self.text_buffer.set_modified(False)

    def save_to_file(self, window):
        try:
            with open(self.__file_name, 'w', encoding="utf-8") as src:
                if version_info.major == 2:
                    src.write(unicode(self.text, 'utf-8'))
                else:   # python version 3.x
                    src.write(self.text)
            self.text_buffer.set_modified(False)
        except Exception as e:
            print_exc()
            md = Gtk.MessageDialog(
                window,
                Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.ERROR,
                Gtk.ButtonsType.OK,
                str(e))
            md.run()
            md.destroy()

    def save(self, window):
        if not self.__file_name:
            self.__file_name = self.get_new_file_name(window)
        if self.__file_name:
            self.save_to_file(window)

    def save_as(self, window):
        new_file_name = self.get_new_file_name(window)
        if new_file_name:
            self.__file_name = new_file_name
            self.save_to_file(window)

    def get_new_file_name(self, window):
        ret_val = ''
        dialog = FileSaveDialog(window)
        dialog.add_filter_rst()
        dialog.set_do_overwrite_confirmation(True)

        if not self.__file_name:
            dialog.set_current_folder(GLib.get_home_dir())

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            ret_val = dialog.get_filename()
        dialog.destroy()
        return ret_val
