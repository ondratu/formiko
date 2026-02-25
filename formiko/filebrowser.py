"""File browser sidebar widget."""

from os import listdir
from os.path import basename, isdir, join, splitext

from gi.repository import GObject, Gtk
from gi.repository.GLib import UserDirectory, get_user_special_dir

from formiko.widgets import ImutableDict

SUPPORTED_EXTS = frozenset(
    {
        ".md",
        ".m2r",
        ".rst",
        ".json",
        ".html",
        ".htm",
        ".txt",
    },
)


class FileListBoxRow(Gtk.ListBoxRow):
    """A single row in the file browser list representing one file.

    Displays the file name left-aligned and stores the full path in
    :attr:`file_path` for use when the row is activated.
    """

    def __init__(self, name: str, directory: str):
        label = Gtk.Label(label=name, xalign=0, halign=Gtk.Align.START)
        super().__init__()
        self.set_child(label)
        self.file_path = join(directory, name)


class FileBrowser(Gtk.Box):
    """Sidebar showing filtered file list for the current directory."""

    __gsignals__ = ImutableDict(
        {
            "file-activated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        },
    )

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=False)
        self.add_css_class("sidebar")
        self._directory = ""

        self._dir_label = Gtk.Label()
        self._dir_label.add_css_class("caption")
        self._dir_label.add_css_class("dim-label")
        self.append(self._dir_label)

        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )
        self._list_box = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            activate_on_single_click=True,
        )
        self._list_box.add_css_class("navigation-sidebar")
        self._list_box.connect("row-activated", self._on_row_activated)
        scroll.set_child(self._list_box)
        self.append(scroll)

        docs = get_user_special_dir(UserDirectory.DIRECTORY_DOCUMENTS)
        if docs and isdir(docs):
            self.set_directory(docs)

    def set_directory(self, directory):
        """Switch the browser to show contents of *directory*."""
        if not directory or directory == self._directory:
            return
        self._directory = directory
        self._refresh()

    def _refresh(self):
        """Reload the file list from the current directory."""
        while child := self._list_box.get_first_child():
            self._list_box.remove(child)

        self._dir_label.set_text(
            basename(self._directory) or self._directory,
        )
        self._dir_label.set_tooltip_text(self._directory)

        try:
            names = sorted(
                name
                for name in listdir(self._directory)
                if splitext(name)[1].lower() in SUPPORTED_EXTS
            )
        except OSError:
            return

        for name in names:
            row = FileListBoxRow(name, self._directory)
            self._list_box.append(row)

    def _on_row_activated(self, _list_box, row):
        self.emit("file-activated", row.file_path)
