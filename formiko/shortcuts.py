# -*- coding: utf-8 -*-
from gi.repository.Gtk import ShortcutsWindow, ShortcutsSection, \
    ShortcutsGroup, ShortcutsShortcut


class SourceGroup(ShortcutsGroup):
    def __init__(self):
        super(SourceGroup, self).__init__(title="Editor")

        self.add(ShortcutsShortcut(
            accelerator="<Control>c", title="Copy"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>x", title="Cut"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>v", title="Paste"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>a", title="Select All"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>Home", title="Go to Begin of Document"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>End", title="Go to End of Document"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>f",
            title="Find in Document / Find another match in same way"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>g", title="Find next match"))
        self.add(ShortcutsShortcut(
            accelerator="<Shift><Control>g", title="Find previous match"))


class VimGroup(ShortcutsGroup):
    def __init__(self):
        super(VimGroup, self).__init__(title="Vim")

        self.add(ShortcutsShortcut(
            accelerator="y", title="Copy"))
        self.add(ShortcutsShortcut(
            accelerator="x", title="Cut"))
        self.add(ShortcutsShortcut(
            accelerator="p", title="Paste"))
        self.add(ShortcutsShortcut(
            accelerator="Escape+g+g", title="Go to Begin of Document"))
        self.add(ShortcutsShortcut(
            accelerator="Escape+<Shift>G", title="Go to End of Document"))
        self.add(ShortcutsShortcut(
            accelerator="Escape+g+g+<Shift>v+<Shift>G", title="Select All"))


class GeneralGroup(ShortcutsGroup):
    def __init__(self, editor_type):
        super(GeneralGroup, self).__init__(title="Genaral")

        self.add(ShortcutsShortcut(
            accelerator="<Control>n", title="New Document"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>o", title="Open Document"))

        if editor_type == "source":
            self.add(ShortcutsShortcut(
                accelerator="<Control>s", title="Save Document"))
            self.add(ShortcutsShortcut(
                accelerator="<Shift><Control>s", title="Save Document As"))

        elif editor_type == "vim":
            self.add(ShortcutsShortcut(
                accelerator="Escape+colon+w", title="Save Document Vim"))

        self.add(ShortcutsShortcut(
            accelerator="<Shift><Control>e", title="Export Document As"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>p", title="Print Document"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>w", title="Close Document"))
        self.add(ShortcutsShortcut(
            accelerator="<Control>q", title="Quit Formiko"))


class ShortcutsWindow(ShortcutsWindow):
    def __init__(self, editor_type):
        # view_name and view does not work. Don't know why
        super(ShortcutsWindow, self).__init__(modal=1)
        sec = ShortcutsSection(title="Formiko", visible=True)

        general = GeneralGroup(editor_type)
        sec.add(general)

        if editor_type == "source":
            source = SourceGroup()
            sec.add(source)

        elif editor_type == "vim":
            vim = VimGroup()
            sec.add(vim)

        self.add(sec)
