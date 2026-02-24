"""Formiko dialog widgets."""
from os.path import splitext

from gi.repository import Adw, GLib, Gtk
from gi.repository.GtkSource import LanguageManager
from gi.repository.Pango import AttrFontDesc, AttrList, FontDescription

from formiko import __author__, __comment__, __copyright__, __version__

default_manager = LanguageManager.get_default()
LANG_BY_EXT = {
    ".rst": default_manager.get_language("rst"),
    ".md": default_manager.get_language("markdown"),
    ".m2r": default_manager.get_language("markdown"),  # parser compatibility
    ".html": default_manager.get_language("html"),
    ".htm": default_manager.get_language("html"),
    ".json": default_manager.get_language("json"),
}


def run_dialog(dialog):
    """Run a GTK4 file-chooser dialog synchronously using a nested loop."""
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


def run_alert_dialog(dialog, parent):
    """Run an Adw.AlertDialog synchronously; returns the string response id."""
    result = [dialog.get_close_response()]
    loop = GLib.MainLoop()

    def on_response(_, response):
        result[0] = response
        loop.quit()

    handler = dialog.connect("response", on_response)
    dialog.present(parent)
    loop.run()
    dialog.disconnect(handler)
    return result[0]


def AboutDialog():  # noqa: N802
    """Create About Formiko dialog."""
    return Adw.AboutDialog(
        application_name="Formiko",
        application_icon="formiko",
        version=__version__,
        copyright=__copyright__ + " The Formiko Team",
        comments=__comment__,
        website="https://github.com/ondratu/formiko",
        license_type=Gtk.License.BSD_3,
        developer_name=__author__,
        developers=[__author__],
        artists=["Petr Šimčík <petrsimi.org@gmail.com>"],
    )


class QuitDialogWithoutSave(Adw.AlertDialog):
    """Quit dialog without save."""

    def __init__(self, file_name):
        name = f"`{file_name}`" if file_name else ""
        super().__init__(
            heading="Quit without saving?",
            body=f"Document {name} is not saved.\n"
            "Are you sure you want to quit without saving?",
        )
        self.add_response("cancel", "Cancel")
        self.add_response("ok", "Quit")
        self.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        self.set_default_response("cancel")
        self.set_close_response("cancel")


class TraceBackDialog(Adw.AlertDialog):
    """Showing traceback dialog."""

    def __init__(self, traceback):
        super().__init__(heading="Traceback error", body="")
        self.add_response("ok", "OK")
        self.set_close_response("ok")
        label = Gtk.Label(label=traceback, selectable=True)
        attrs = AttrList()
        attrs.insert(
            AttrFontDesc.new(FontDescription.from_string("Monospace")),
        )
        label.set_attributes(attrs)
        scroll = Gtk.ScrolledWindow(
            min_content_width=500,
            min_content_height=200,
        )
        scroll.set_child(label)
        self.set_extra_child(scroll)


class FileNotFoundDialog(Adw.AlertDialog):
    """File not found error dialog."""

    def __init__(self, filename):
        super().__init__(
            heading="File not found",
            body=f"Document `{filename}` not found.",
        )
        self.add_response("ok", "OK")
        self.set_close_response("ok")


class FileChangedDialog(Adw.AlertDialog):
    """File changed info dialog."""

    def __init__(self, file_name):
        super().__init__(
            heading="File changed",
            body=f"Document `{file_name}` was changed.\n"
            "Do you want to reload from storage?",
        )
        self.add_response("no", "No")
        self.add_response("yes", "Reload")
        self.set_default_response("yes")
        self.set_close_response("no")


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
        self.add_filter_lang(LANG_BY_EXT[".rst"], ".rst", current)

    def add_filter_md(self, current=False):
        """Add filter for MarkDown."""
        self.add_filter_lang(LANG_BY_EXT[".md"], ".md", current)

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
        self.add_filter_lang(LANG_BY_EXT[".html"], ".html", current)

    def add_filter_json(self, current=False):
        """Add filter for JSON files."""
        self.add_filter_lang(LANG_BY_EXT[".json"], ".json", current)

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
