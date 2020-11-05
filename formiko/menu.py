from gi.repository.Gio import Menu


class AppMenu(Menu):
    def __init__(self):
        """
        Initialize menu.

        Args:
            self: (todo): write your description
        """
        super(AppMenu, self).__init__()
        sec = Menu()
        sec.append("New Document", "app.new-window")
        sec.append("Open Document", "win.open-document")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("Save Document", "win.save-document")
        sec.append("Save Document As...", "win.save-document-as")
        sec.append("Export Document As...", "win.export-document-as")
        sec.append("Print Document", "win.print-document")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("Keyboard Shortcuts", "app.shortcuts")
        sec.append("About Formiko", "app.about")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("Close Document", "win.close-window")
        sec.append("Quit", "app.quit")
        self.append_section(None, sec)
