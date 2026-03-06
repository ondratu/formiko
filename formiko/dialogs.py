"""Formiko dialog widgets."""

from importlib.resources import files
from traceback import print_exc

from gi.repository import Adw, Gio, GLib, Gtk
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


def open_file_dialog(
    parent,
    title,
    filters,
    default_filter,
    initial_folder=None,
    callback=None,
):
    """Open Gtk.FileDialog for selecting a file.

    Call *callback(path)* on accept.
    """
    dialog = Gtk.FileDialog(
        title=title,
        filters=filters,
        default_filter=default_filter,
    )
    if initial_folder:
        dialog.set_initial_folder(Gio.File.new_for_path(initial_folder))

    def _finish(d, result):
        try:
            gfile = d.open_finish(result)
        except GLib.Error:
            return
        if gfile and callback:
            path = gfile.get_path()
            if not path:
                try:
                    path, _ = GLib.filename_from_uri(gfile.get_uri())
                except (GLib.Error, TypeError):
                    path = ""
            callback(path or "")

    dialog.open(parent, None, _finish)


def _apply_initial_name(dialog, name, default_suffix):
    """Set initial filename in a save dialog, appending suffix if missing."""
    if name and default_suffix and "." not in name:
        name = f"{name}.{default_suffix}"
    if name:
        dialog.set_current_name(name)


def _connect_filter_extension_updater(dialog, filter_suffixes):
    """Connect notify::filter to keep the filename extension in sync."""

    def _on_filter_changed(d, _pspec):
        f = d.get_filter()
        if f is None:
            return
        new_suffix = filter_suffixes.get(f.get_name(), "")
        current = d.get_current_name() or ""
        if not current:
            return
        base = current.rsplit(".", 1)[0] if "." in current else current
        d.set_current_name(f"{base}.{new_suffix}" if new_suffix else base)

    dialog.connect("notify::filter", _on_filter_changed)


def save_file_dialog(
    parent,
    title,
    filters,
    default_filter,
    default_suffix=None,
    filter_suffixes=None,
    initial_folder=None,
    initial_name=None,
    callback=None,
):
    """Open a save dialog and call *callback(path)* on accept.

    *default_suffix* — extension appended when the saved name has none.
    *filter_suffixes* — ``{filter_name: suffix}`` dict for live extension
        updates.
    """
    dialog = Gtk.FileChooserDialog(
        title=title,
        transient_for=parent,
        action=Gtk.FileChooserAction.SAVE,
    )
    dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
    dialog.add_button("_Save", Gtk.ResponseType.ACCEPT)
    dialog.set_default_response(Gtk.ResponseType.ACCEPT)

    for i in range(filters.get_n_items()):
        dialog.add_filter(filters.get_item(i))
    if default_filter:
        dialog.set_filter(default_filter)
    if initial_folder:
        dialog.set_current_folder(Gio.File.new_for_path(initial_folder))
    _apply_initial_name(dialog, initial_name or "", default_suffix)
    if filter_suffixes:
        _connect_filter_extension_updater(dialog, filter_suffixes)

    def _on_response(d, response):
        if response == Gtk.ResponseType.ACCEPT:
            gfile = d.get_file()
            if gfile and callback:
                path = gfile.get_path() or ""
                if (
                    path
                    and default_suffix
                    and "." not in path.rsplit("/", 1)[-1]
                ):
                    path += "." + default_suffix
                callback(path)
        d.destroy()

    dialog.connect("response", _on_response)
    dialog.present()


def make_filter_markup_text():
    """Return Gtk.FileFilter for markup and plain-text documents."""
    f = Gtk.FileFilter()
    f.set_name("Markup & Text files")
    for pattern in ("*.rst", "*.md", "*.markdown", "*.txt", "*.text"):
        f.add_pattern(pattern)
    for name in (
        "INSTALL",
        "AUTHORS",
        "AUTHOR",
        "LICENSE",
        "LICENCE",
        "COPYING",
        "README",
        "TODO",
        "HOWTO",
        "CHANGES",
        "CHANGELOG",
        "ChangeLog",
        "NEWS",
        "CONTRIBUTORS",
        "NOTICE",
        "CREDITS",
        "BUGS",
        "HACKING",
    ):
        f.add_pattern(name)
    return f


def make_filter_all():
    """Return Gtk.FileFilter for all files."""
    f = Gtk.FileFilter()
    f.set_name("All File Types")
    f.add_pattern("*")
    return f


def build_css_filters():
    """Return (Gio.ListStore, default_filter) for CSS stylesheet picker."""
    css = Gtk.FileFilter()
    css.set_name("Stylesheet file (*.css)")
    css.add_mime_type("text/css")
    css.add_pattern("*.css")
    store = Gio.ListStore.new(Gtk.FileFilter)
    store.append(css)
    store.append(make_filter_all())
    return store, css


def _make_lang_filter(lang_key):
    """Return Gtk.FileFilter for a GtkSource language (open dialogs)."""
    lang = LANG_BY_EXT[lang_key]
    f = Gtk.FileFilter()
    f.set_name(lang.get_name())
    for p in lang.get_globs():
        f.add_pattern(p)
    return f


def build_open_filters():
    """Return (Gio.ListStore, default_filter) for Gtk.FileDialog open."""
    markup = make_filter_markup_text()
    txt = Gtk.FileFilter()
    txt.set_name("Plain text")
    txt.add_pattern("*.txt")

    store = Gio.ListStore.new(Gtk.FileFilter)
    for f in (
        markup,
        _make_lang_filter(".rst"),
        _make_lang_filter(".md"),
        txt,
        _make_lang_filter(".html"),
        _make_lang_filter(".json"),
        make_filter_all(),
    ):
        store.append(f)
    return store, markup


def _make_save_filter(name, suffixes):
    """Return Gtk.FileFilter with add_suffix()."""
    f = Gtk.FileFilter()
    f.set_name(name)
    for s in suffixes:
        f.add_suffix(s)
    return f


def build_save_filters(lang_id):
    """Return (store, default_filter, default_suffix, filter_suffixes).

    *lang_id* is the GtkSource language id (e.g. 'rst', 'markdown', 'html').
    *filter_suffixes* maps filter name → primary suffix for live filename
        updates.
    """
    rst_f = _make_save_filter(LANG_BY_EXT[".rst"].get_name(), ["rst"])
    md_f = _make_save_filter(LANG_BY_EXT[".md"].get_name(), ["md", "markdown"])
    html_f = _make_save_filter(
        LANG_BY_EXT[".html"].get_name(),
        ["html", "htm"],
    )
    json_f = _make_save_filter(LANG_BY_EXT[".json"].get_name(), ["json"])
    txt_f = _make_save_filter("Plain text", ["txt"])

    filter_suffixes = {
        rst_f.get_name(): "rst",
        md_f.get_name(): "md",
        html_f.get_name(): "html",
        json_f.get_name(): "json",
        txt_f.get_name(): "txt",
    }

    lang_to_filter = {
        "rst": (rst_f, "rst"),
        "markdown": (md_f, "md"),
        "html": (html_f, "html"),
        "json": (json_f, "json"),
        "text": (txt_f, "txt"),
    }
    default, suffix = lang_to_filter.get(lang_id, (rst_f, "rst"))

    store = Gio.ListStore.new(Gtk.FileFilter)
    for f in (rst_f, md_f, html_f, json_f, txt_f, make_filter_all()):
        store.append(f)
    return store, default, suffix, filter_suffixes


def build_export_filters(parser):
    """Return tuple for export.

    Returns (store, default_filter, default_suffix, filter_suffixes)
    """
    if parser == "json":
        default = _make_save_filter(LANG_BY_EXT[".json"].get_name(), ["json"])
        suffix = "json"
    else:
        default = _make_save_filter(
            LANG_BY_EXT[".html"].get_name(),
            ["html", "htm"],
        )
        suffix = "html"

    filter_suffixes = {default.get_name(): suffix}

    store = Gio.ListStore.new(Gtk.FileFilter)
    store.append(default)
    store.append(make_filter_all())
    return store, default, suffix, filter_suffixes


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
