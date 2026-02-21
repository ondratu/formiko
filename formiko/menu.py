"""Application menu definition."""
from gi.repository.Gio import Menu

from formiko.editor import EditorType


class AppMenu(Menu):
    """Formiko primary menu combining document and application actions."""

    def __init__(self, editor_type=EditorType.SOURCE):
        super().__init__()
        sec = Menu()
        sec.append("Open…", "win.open-document")
        if editor_type == EditorType.SOURCE:
            sec.append("Save As…", "win.save-document-as")
        self.append_section(None, sec)
        if editor_type != EditorType.PREVIEW:
            sec = Menu()
            sec.append("Export As…", "win.export-document-as")
            self.append_section(None, sec)
        sec = Menu()
        sec.append("Print…", "win.print-document")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("New Window", "app.new-window")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("Keyboard Shortcuts", "app.shortcuts")
        sec.append("About Formiko", "app.about")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("Quit", "app.quit")
        self.append_section(None, sec)
