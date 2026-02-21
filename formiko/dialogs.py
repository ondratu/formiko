"""Formiko dialog widgets."""
from os.path import splitext

from gi.repository import GLib, Gtk
from gi.repository.GtkSource import LanguageManager
from gi.repository.Pango import AttrFontDesc, AttrList, FontDescription

from formiko import __author__, __comment__, __copyright__, __version__

default_manager = LanguageManager.get_default()
LANGS = {
    ".rst": default_manager.get_language("rst"),
    ".md": default_manager.get_language("markdown"),
    ".m2r": default_manager.get_language("markdown"),  # parser compatibility
    ".html": default_manager.get_language("html"),
    ".htm": default_manager.get_language("html"),
    ".json": default_manager.get_language("json"),
}


def run_dialog(dialog):
    """Run a GTK4 dialog synchronously using a nested main loop."""
    result = [Gtk.ResponseType.NONE]
    loop = GLib.MainLoop()

    def on_response(_, response):
        result[0] = response
        loop.quit()

    handler = dialog.connect("response", on_response)
    dialog.present()
    loop.run()
    dialog.disconnect(handler)
    return result[0]


class AboutDialog(Gtk.AboutDialog):
    """About Formiko dialog."""

    def __init__(self, transient_for):
        super().__init__(transient_for=transient_for, modal=False)
        self.set_program_name("Formiko")
        self.set_version(__version__)
        self.set_copyright(__copyright__ + " The Formiko Team")
        self.set_comments(__comment__)
        self.set_website("https://github.com/ondratu/formiko")
        self.set_license_type(Gtk.License.BSD_3)
        self.set_authors([__author__])
        self.set_artists(["Petr Šimčík <petrsimi.org@gmail.com>"])
        self.set_logo_icon_name("formiko")


class QuitDialogWithoutSave(Gtk.MessageDialog):
    """Quit dialog without save."""

    def __init__(self, parent, file_name):
        name = f"`{file_name}`" if file_name else ""
        super().__init__(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Document {name} not saved.\n"
            "Are you sure you want to quit without saving?",
        )


class TraceBackDialog(Gtk.Dialog):
    """Showing traceback dialog."""

    def __init__(self, parent, traceback):
        super().__init__(
            title="Traceback error",
            transient_for=parent,
            modal=True,
            use_header_bar=True,
        )
        box = self.get_content_area()
        label = Gtk.Label(label=traceback)
        attrs = AttrList()
        attrs.insert(
            AttrFontDesc.new(FontDescription.from_string("Monospace")),
        )
        label.set_attributes(attrs)
        box.append(label)


class FileNotFoundDialog(Gtk.MessageDialog):
    """File not found error dialog."""

    def __init__(self, parent, filename):
        super().__init__(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CANCEL,
            text=f"Document `{filename}` not found",
        )


class FileChangedDialog(Gtk.MessageDialog):
    """File changed info dialog."""

    def __init__(self, parent, file_name):
        super().__init__(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Document `{file_name}` was changed.\n"
            "Do you want to load from storage?",
        )


class FileChooserDialog(Gtk.FileChooserDialog):
    """File chooser dialog."""

    def __init__(self, title, parent, action):
        super().__init__(title=title, transient_for=parent, action=action)
        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        if action == Gtk.FileChooserAction.SAVE:
            self.add_button("_Save", Gtk.ResponseType.ACCEPT)
        else:
            self.add_button("_Open", Gtk.ResponseType.ACCEPT)

    def get_filename_with_ext(self):
        """Return filename with right extension."""
        gfile = self.get_file()
        if gfile is None:
            return ""
        file_name = gfile.get_path()
        _, ext = splitext(file_name)
        if ext:
            return file_name

        filter_ = self.get_filter()
        for extension in getattr(filter_, "extensions", ()):
            if file_name.lower().endswith(extension):
                return file_name
        return file_name + filter_.default

    def add_filter_lang(self, lang, default, current=False):
        """Add filter for supported extensions."""
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
        """Add filter for reStructuredText."""
        self.add_filter_lang(LANGS[".rst"], ".rst", current)

    def add_filter_md(self, current=False):
        """Add filter for MarkDown."""
        self.add_filter_lang(LANGS[".md"], ".md", current)

    def add_filter_plain(self, current=False):
        """Add plain text filter."""
        filter_ = Gtk.FileFilter()
        filter_.set_name("Plain text")
        filter_.add_pattern("*.txt")
        filter_.add_mime_type("text/plain")
        filter_.default = ".txt"
        self.add_filter(filter_)
        if current:
            self.set_filter(filter_)

    def add_filter_html(self, current=False):
        """Add filter for HTML files."""
        self.add_filter_lang(LANGS[".html"], ".html", current)

    def add_filter_json(self, current=False):
        """Add filter for JSON files."""
        self.add_filter_lang(LANGS[".json"], ".json", current)

    def add_filter_all(self, current=False):
        """Add filter for all files type."""
        filter_ = Gtk.FileFilter()
        filter_.set_name("All File Types")
        filter_.add_pattern("*")
        filter_.default = ""
        self.add_filter(filter_)
        if current:
            self.set_filter(filter_)


class FileOpenDialog(FileChooserDialog):
    """Open file dialog."""

    def __init__(self, parent):
        super().__init__("Open Document", parent, Gtk.FileChooserAction.OPEN)


class FileSaveDialog(FileChooserDialog):
    """Save File As dialog."""

    def __init__(self, parent):
        super().__init__(
            "Save As Document",
            parent,
            Gtk.FileChooserAction.SAVE,
        )
