from gi.repository.Gio import Menu


class AppMenu(Menu):
    def __init__(self):
        super(AppMenu, self).__init__()
        sec = Menu()
        sec.append("New document", "app.new-window")
        sec.append("Open document", "win.open-document")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("Save document", "win.save-document")
        sec.append("Save document as", "win.save-document-as")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("About Formiko", "app.about")
        self.append_section(None, sec)
        sec = Menu()
        sec.append("Close document", "win.close-window")
        sec.append("Quit", "app.quit")
        self.append_section(None, sec)
