# -*- coding: utf-8 -*-
from gi.repository.Pango import FontDescription
from gi.repository import Gtk

from formiko import __version__, __author__, __copyright__, __comment__
from formiko.icons import icon_list, icon_128


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
        super(QuitDialogWithoutSave, self).__init__(
            parent,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK_CANCEL,
            "File %s not saved.\n"
            "Are you sure to quite without save ?" % file_name)


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

    def add_filter_rst(self):
        filter_rst = Gtk.FileFilter()
        filter_rst.set_name("reSructuredText")
        filter_rst.add_pattern("*.rst")
        filter_rst.add_pattern("*.RST")
        self.add_filter(filter_rst)

    def add_filter_md(self):
        filter_md = Gtk.FileFilter()
        filter_md.set_name("MarkDown")
        filter_md.add_pattern("*.md")
        filter_md.add_pattern("*.MD")
        filter_md.add_pattern("*.markdown")
        self.add_filter(filter_md)

    def add_filter_plain(self):
        filter_txt = Gtk.FileFilter()
        filter_txt.set_name("Plain text")
        filter_txt.add_mime_type("text/plain")
        self.add_filter(filter_txt)

    def add_filter_html(self):
        filter_html = Gtk.FileFilter()
        filter_html.set_name("Hypertext files")
        filter_html.add_mime_type("text/html")
        self.add_filter(filter_html)

    def add_filter_all(self):
        filter_all = Gtk.FileFilter()
        filter_all.set_name("all files")
        filter_all.add_pattern("*")
        self.add_filter(filter_all)


class FileOpenDialog(FileChooserDialog):
    def __init__(self, parent):
        super(FileOpenDialog, self).__init__(
            "Open file", parent, Gtk.FileChooserAction.OPEN
        )


class FileSaveDialog(FileChooserDialog):
    def __init__(self, parent):
        super(FileSaveDialog, self).__init__(
            "Save as file", parent, Gtk.FileChooserAction.SAVE
        )
