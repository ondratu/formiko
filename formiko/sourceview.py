from gi.repository import Gtk, GtkSource, Pango

default_manager = GtkSource.LanguageManager.get_default()
rst_lang = default_manager.get_language('rst')
markdown_lang = default_manager.get_language('markdown')


class SourceView(Gtk.ScrolledWindow):
    def __init__(self, file_name=None):
        self.__last_changes = 0
        super(Gtk.ScrolledWindow, self).__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.text_buffer = GtkSource.Buffer()
        self.text_buffer.connect("changed", self.inc_changes)
        self.text_buffer.set_language(rst_lang)
        self.source_view = GtkSource.View.new_with_buffer(self.text_buffer)
        self.source_view.set_auto_indent(True)
        self.source_view.set_show_line_numbers(True)
        self.source_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.source_view.override_font(
            Pango.FontDescription.from_string('Monospace'))
        # self.source_view.set_monospace(True) since 3.16
        self.add(self.source_view)

    def inc_changes(self, text_buffer):
        self.__last_changes += 1

    @property
    def changes(self):
        return self.__last_changes

    @property
    def is_modified(self):
        return False

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
        return 'NO FILE'
