# -*- coding: utf-8 -*-
from gi.repository.Pango import FontDescription
from gi.repository.GtkSource import LanguageManager
from gi.repository import Gtk

from os.path import splitext

from formiko import __version__, __author__, __copyright__, __comment__
from formiko.icons import icon_list, icon_128

default_manager = LanguageManager.get_default()
LANGS = {
    '.rst': default_manager.get_language('rst'),
    '.md': default_manager.get_language('markdown'),
    '.cm': default_manager.get_language('markdown'),    # parser compatibility
    '.m2r': default_manager.get_language('markdown'),   # parser compatibility
    '.html': default_manager.get_language('html'),
    '.htm': default_manager.get_language('html'),
    '.json': default_manager.get_language('json'),
}


class AboutDialog(Gtk.AboutDialog):
    def __init__(self, transient_for):
        super(AboutDialog, self).__init__(transient_for=transient_for,
                                          modal=False)
        self.set_icon_list(icon_list)
        self.set_program_name("Formiko")
        self.set_version(__version__)
        self.set_copyright(__copyright__ + ' The Formiko Team')
        self.set_comments(__comment__)
        self.set_website("https://github.com/ondratu/formiko")
        self.set_license_type(Gtk.License.BSD)
        self.set_authors([__author__])
        self.set_artists(["Petr Šimčík <petrsimi.org@gmail.com>"])
        self.set_logo(icon_128)


class QuitDialogWithoutSave(Gtk.MessageDialog):
    def __init__(self, parent, file_name):
        name = "`%s`" % file_name if file_name else ""
        super(QuitDialogWithoutSave, self).__init__(
            parent,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK_CANCEL,
            "Document %s not saved.\n"
            "Are you sure to quite without save?" % name)


class TraceBackDialog(Gtk.Dialog):
    def __init__(self, parent, traceback):
        super(TraceBackDialog, self).__init__(
            "Traceback error",
            parent,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            use_header_bar=True)
        box = self.get_content_area()
        label = Gtk.Label(traceback)
        label.override_font(FontDescription.from_string('Monospace'))
        label.show_all()
        box.add(label)


class FileNotFoundDialog(Gtk.MessageDialog):
    def __init__(self, parent, filename):
        super(FileNotFoundDialog, self).__init__(
            parent,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CANCEL,
            "Document `%s` not found" % filename)


class FileChangedDialog(Gtk.MessageDialog):
    def __init__(self, parent, file_name):
        super(FileChangedDialog, self).__init__(
            parent,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.INFO,
            Gtk.ButtonsType.YES_NO,
            "Document `%s` was changed.\n"
            "Do you want to load from storage?" % file_name)


class FileChooserDialog(Gtk.FileChooserDialog):
    def __init__(self, title, parent, action):
        if action == Gtk.FileChooserAction.SAVE:
            label = Gtk.STOCK_SAVE
        else:
            label = Gtk.STOCK_OPEN
        super(FileChooserDialog, self).__init__(
            title,
            parent,
            action,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             label, Gtk.ResponseType.ACCEPT))

    def get_filename_with_ext(self):
        file_name = self.get_filename()
        name, ext = splitext(file_name)
        if ext:
            return file_name

        filter_ = self.get_filter()
        for extension in getattr(filter_, 'extensions', ()):
            if file_name.lower().endswith(extension):
                return file_name
        return file_name + filter_.default

    def add_filter_lang(self, lang, default, current=False):
        filter_ = Gtk.FileFilter()
        filter_.set_name(lang.get_name())
        for pattern in lang.get_globs():
            filter_.add_pattern(pattern)
        for mime_type in lang.get_mime_types():
            filter_.add_mime_type(mime_type)
        filter_.extensions = tuple(it[1:] for it in lang.get_globs())
        filter_.default = default
        self.add_filter(filter_)
        if current:
            self.set_filter(filter_)

    def add_filter_rst(self, current=False):
        self.add_filter_lang(LANGS[".rst"], ".rst", current)

    def add_filter_md(self, current=False):
        self.add_filter_lang(LANGS[".md"], ".md", current)

    def add_filter_plain(self, current=False):
        filter_ = Gtk.FileFilter()
        filter_.set_name("Plain text")
        filter_.add_pattern("*.txt")
        filter_.add_mime_type("text/plain")
        filter_.default = ".txt"
        self.add_filter(filter_)
        if current:
            self.set_filter(filter_)

    def add_filter_html(self, current=False):
        self.add_filter_lang(LANGS[".html"], ".html", current)

    def add_filter_json(self, current=False):
        self.add_filter_lang(LANGS[".json"], ".json", current)

    def add_filter_all(self, current=False):
        filter_ = Gtk.FileFilter()
        filter_.set_name("All File Types")
        filter_.add_pattern("*")
        filter_.default = ""
        self.add_filter(filter_)
        if current:
            self.set_filter(filter_)


class FileOpenDialog(FileChooserDialog):
    def __init__(self, parent):
        super(FileOpenDialog, self).__init__(
            "Open Document", parent, Gtk.FileChooserAction.OPEN
        )


class FileSaveDialog(FileChooserDialog):
    def __init__(self, parent):
        super(FileSaveDialog, self).__init__(
            "Save As Document", parent, Gtk.FileChooserAction.SAVE
        )
