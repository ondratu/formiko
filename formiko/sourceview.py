from gi.repository.GObject import SIGNAL_RUN_FIRST
from gi.repository.Pango import FontDescription
from gi.repository.GtkSource import LanguageManager, Buffer, View
from gi.repository.GLib import get_home_dir

from gi.repository import Gtk

from os.path import splitext, basename, isfile
from io import open
from traceback import format_exc
from sys import version_info

from formiko.dialogs import FileSaveDialog, TraceBackDialog

default_manager = LanguageManager.get_default()
LANGS = {
    '.rst': default_manager.get_language('rst'),
    '.md': default_manager.get_language('markdown'),
    '.html': default_manager.get_language('html'),
    '.htm': default_manager.get_language('html'),
}


class SourceView(Gtk.ScrolledWindow):
    __file_name = ''
    __last_changes = 0

    __gsignals__ = {
        'file_type': (SIGNAL_RUN_FIRST, None, (str,))
    }

    def __init__(self, default_parser):
        super(Gtk.ScrolledWindow, self).__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.text_buffer = Buffer.new_with_language(
            LANGS['.%s' % default_parser])
        self.text_buffer.connect("changed", self.inc_changes)
        self.source_view = View.new_with_buffer(self.text_buffer)
        self.source_view.set_auto_indent(True)
        self.source_view.set_show_line_numbers(True)
        self.source_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.source_view.override_font(
            FontDescription.from_string('Monospace'))
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

    @property
    def file_ext(self):
        name, ext = splitext(self.__file_name)
        return ext

    def inc_changes(self, text_buffer):
        self.__last_changes += 1

    def read_from_file(self, file_name):
        self.__file_name = file_name
        self.emit("file_type", self.file_ext)

        if isfile(file_name):
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
        except Exception:
            md = TraceBackDialog(window, format_exc())
            md.run()
            md.destroy()

    def save(self, window):
        if not self.__file_name:
            self.__file_name = self.get_new_file_name(window)
            self.emit("file_type", self.file_ext)
        if self.__file_name:
            self.save_to_file(window)

    def save_as(self, window):
        new_file_name = self.get_new_file_name(window)
        if new_file_name:
            self.__file_name = new_file_name
            self.emit("file_type", self.file_ext)
            self.save_to_file(window)

    def get_new_file_name(self, window):
        ret_val = ''
        dialog = FileSaveDialog(window)
        # TODO: set default filtry by select parser
        dialog.add_filter_rst()
        dialog.add_filter_md()
        dialog.add_filter_html()
        dialog.set_do_overwrite_confirmation(True)

        if not self.__file_name:
            dialog.set_current_folder(get_home_dir())

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            ret_val = dialog.get_filename()
        dialog.destroy()
        return ret_val

    def do_file_type(self, ext):
        language = LANGS.get(ext, LANGS['.rst'])
        if self.text_buffer.get_language() != language:
            self.text_buffer.set_language(language)
