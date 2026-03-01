"""Shortcuts widgets."""

from gi.repository import Gtk
from gi.repository.Gtk import (
    ShortcutsGroup,
    ShortcutsSection,
    ShortcutsShortcut,
)

from formiko.editor import EditorType


class SourceGroup(ShortcutsGroup):
    """Shortcut group for SourceView."""

    def __init__(self):
        super().__init__(title="Editor")

        self.append(ShortcutsShortcut(accelerator="<Control>c", title="Copy"))
        self.append(ShortcutsShortcut(accelerator="<Control>x", title="Cut"))
        self.append(ShortcutsShortcut(accelerator="<Control>v", title="Paste"))
        self.append(
            ShortcutsShortcut(accelerator="<Control>a", title="Select All"),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Control>Home",
                title="Go to Begin of Document",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Control>End",
                title="Go to End of Document",
            ),
        )


class FindGroup(ShortcutsGroup):
    """Shortcuts group for searching."""

    def __init__(self):
        super().__init__(title="Find")

        self.append(
            ShortcutsShortcut(
                accelerator="<Control>f",
                title="Find in Document / Find another match in same way",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Control>g",
                title="Find next match",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Shift><Control>g",
                title="Find previous match",
            ),
        )


class VimGroup(ShortcutsGroup):
    """Vim shortcuts group."""

    def __init__(self):
        super().__init__(title="Vim")

        self.append(ShortcutsShortcut(accelerator="y", title="Copy"))
        self.append(ShortcutsShortcut(accelerator="x", title="Cut"))
        self.append(ShortcutsShortcut(accelerator="p", title="Paste"))
        self.append(
            ShortcutsShortcut(
                accelerator="Escape+g+g",
                title="Go to Begin of Document",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="Escape+<Shift>G",
                title="Go to End of Document",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="Escape+g+g+<Shift>v+<Shift>G",
                title="Select All",
            ),
        )


class PreviewGroup(ShortcutsGroup):
    """Preview shortcuts group."""

    def __init__(self):
        super().__init__(title="Preview")

        self.append(
            ShortcutsShortcut(
                accelerator="<Control>r",
                title="Refresh preview",
            ),
        )
        self.append(
            ShortcutsShortcut(accelerator="<Alt>e", title="Show editor only"),
        )
        self.append(
            ShortcutsShortcut(accelerator="<Alt>p", title="Show preview only"),
        )
        self.append(ShortcutsShortcut(accelerator="<Alt>b", title="Show both"))


class GeneralGroup(ShortcutsGroup):
    """General application shortcuts group."""

    def __init__(self, editor_type):
        super().__init__(title="Genaral")

        self.append(
            ShortcutsShortcut(accelerator="<Control>n", title="New Document"),
        )
        self.append(
            ShortcutsShortcut(accelerator="<Control>o", title="Open Document"),
        )

        if editor_type == "source":
            self.append(
                ShortcutsShortcut(
                    accelerator="<Control>s",
                    title="Save Document",
                ),
            )
            self.append(
                ShortcutsShortcut(
                    accelerator="<Shift><Control>s",
                    title="Save Document As",
                ),
            )

        elif editor_type == "vim":
            self.append(
                ShortcutsShortcut(
                    accelerator="Escape+colon+w",
                    title="Save Document Vim",
                ),
            )

        self.append(
            ShortcutsShortcut(
                accelerator="<Shift><Control>e",
                title="Export Document As",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Control>p",
                title="Print Document",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Control>w",
                title="Close Document",
            ),
        )
        self.append(
            ShortcutsShortcut(accelerator="<Control>q", title="Quit Formiko"),
        )


class FormattingGroup(ShortcutsGroup):
    """Shortcuts group for formatting actions."""

    def __init__(self):
        super().__init__(title="Formatting")

        self.append(
            ShortcutsShortcut(accelerator="<Control>b", title="Bold"),
        )
        self.append(
            ShortcutsShortcut(accelerator="<Control>i", title="Italic"),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Shift><Control>c", title="Inline Code",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Control>k", title="Insert Link",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Shift><Control>q", title="Blockquote",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Shift><Control>b", title="Bullet List",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Shift><Control>n", title="Numbered List",
            ),
        )
        self.append(
            ShortcutsShortcut(
                accelerator="<Control>1 <Control>2 <Control>3 "
                            "<Control>4 <Control>5 <Control>6",
                title="Header 1-6",
            ),
        )


class ShortcutsWindow(Gtk.ShortcutsWindow):
    """Shortcuts window widget."""

    def __init__(self, editor_type: EditorType):
        # view_name and view does not work. Don't know why
        super().__init__(modal=True)
        sec = ShortcutsSection(title="Formiko", visible=True, max_height=12)

        sec.add_group(GeneralGroup(editor_type))
        sec.add_group(PreviewGroup())
        sec.add_group(FindGroup())

        if editor_type == EditorType.SOURCE:
            sec.add_group(SourceGroup())
            sec.add_group(FormattingGroup())

        elif editor_type == EditorType.VIM:
            sec.add_group(VimGroup())

        self.add_section(sec)
