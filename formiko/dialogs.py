"""Formiko dialog widgets."""

from importlib.resources import files
from os.path import splitext
from traceback import print_exc

from gi.repository import Adw, GLib, Gtk
from gi.repository.GtkSource import LanguageManager
from gi.repository.Pango import AttrFontDesc, AttrList, FontDescription

from formiko import __author__, __comment__, __copyright__, __version__
from formiko.format_utils import parse_link

default_manager = LanguageManager.get_default()
LANG_BY_EXT = {
    ".rst": default_manager.get_language("rst"),
    ".md": default_manager.get_language("markdown"),
    ".m2r": default_manager.get_language("markdown"),  # parser compatibility
    ".html": default_manager.get_language("html"),
    ".htm": default_manager.get_language("html"),
    ".json": default_manager.get_language("json"),
}


def load_authors():
    """Parse formiko/AUTHORS and return a dict of section → list of entries."""
    sections = {}
    current = None
    try:
        content = (
            files("formiko.data")
            .joinpath("AUTHORS")
            .read_text(encoding="utf-8")
        )
        for line in content.splitlines():
            _line = line.strip()
            if _line.startswith("[") and line.endswith("]"):
                current = line[1:-1]
                sections[current] = []
            elif _line and current is not None:
                sections[current].append(line)
    except Exception:  # pylint: disable=broad-exception-caught
        print_exc()
    return sections


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


def about_dialog():
    """Create About Formiko dialog."""
    authors = load_authors()
    return Adw.AboutDialog(
        application_name="Formiko",
        application_icon="formiko",
        version=__version__,
        copyright=__copyright__ + " The Formiko Team",
        comments=__comment__,
        website="https://github.com/ondratu/formiko",
        license_type=Gtk.License.BSD_3,
        developer_name=__author__.split(" <", maxsplit=1)[0],
        developers=authors.get("developers", [__author__]),
        artists=authors.get("artists", []),
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


class InsertLinkDialog(Adw.Dialog):
    """Two-field dialog for inserting a hyperlink.

    *selected_text* and *parser* are used to pre-fill the fields via
    :func:`~formiko.format_utils.parse_link`.  For HTML, the Text row is
    hidden because the inner text is always the URL itself.

    Pressing Enter in the URL entry or clicking *Insert* calls
    *on_insert(text, url)*.  Closing / cancelling does nothing.
    """

    def __init__(self, on_insert, selected_text: str = "", parser: str = ""):
        super().__init__(title="Insert Link")
        self._on_insert = on_insert
        self._parser = parser
        self.set_content_width(400)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(Adw.HeaderBar())

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )

        group = Adw.PreferencesGroup()

        self._text_row = Adw.EntryRow(title="Text")
        group.add(self._text_row)

        self._url_row = Adw.EntryRow(title="URL")
        self._url_row.connect("entry-activated", self._confirm)
        group.add(self._url_row)

        content.append(group)

        btn_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            halign=Gtk.Align.END,
        )
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        insert_btn = Gtk.Button(label="Insert")
        insert_btn.add_css_class("suggested-action")
        insert_btn.connect("clicked", self._confirm)
        btn_box.append(cancel_btn)
        btn_box.append(insert_btn)
        content.append(btn_box)

        box.append(content)
        self.set_child(box)

        # Pre-fill from selection (detect existing link markup)
        link_text, url = parse_link(selected_text, parser)
        self._text_row.set_text(link_text)
        self._url_row.set_text(url)

    def _confirm(self, *_):
        url = self._url_row.get_text().strip()
        if not url:
            return
        self._on_insert(self._text_row.get_text(), url)
        self.close()

    def present_and_focus(self, parent):
        """Present the dialog focused on the URL entry."""
        self.present(parent)
        self._url_row.grab_focus()
