from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib


class StatusMenuButton(Gtk.MenuButton):
    css = Gtk.CssProvider()
    css.load_from_data(b"""
            * {
                border: 0;
                padding: 1px 8px 2px 4px;
                outline-width: 0;
            }
        """)

    def __init__(self, label, popover):
        """
        Initializes a gtk gtk gtk gtk.

        Args:
            self: (todo): write your description
            label: (str): write your description
            popover: (todo): write your description
        """
        super(StatusMenuButton, self).__init__(popover=popover)
        self.set_relief(Gtk.ReliefStyle.NONE)
        ctx = self.get_style_context()
        ctx.add_provider(StatusMenuButton.css,
                         Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self.add(box)
        self.label = Gtk.Label(label)
        box.pack_start(self.label, True, True, 0)

        icon = Gio.ThemedIcon(name="pan-down-symbolic")
        box.pack_start(Gtk.Image.new_from_gicon(icon, Gtk.IconSize.MENU),
                       True, True, 0)

    def set_label(self, label):
        """
        Set the label for the given label.

        Args:
            self: (todo): write your description
            label: (str): write your description
        """
        self.label.set_label(label)
# endclass


class LineColPopover(Gtk.Popover):
    def __init__(self, preferences):
        """
        Initialize the layout.

        Args:
            self: (todo): write your description
            preferences: (list): write your description
        """
        super(LineColPopover, self).__init__()

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                           border_width=10)
        self.add(self.box)

        self.add_check_button(
            'Display line numbers', "editor.line-numbers-toggle",
            preferences.line_numbers)
        self.add_check_button(
            'Display right margin', "editor.right-margin-toggle",
            preferences.right_margin)
        self.add_check_button(
            'Highlight current line', "editor.current-line-toggle",
            preferences.current_line)
        self.add_check_button(
            'Text wrapping', "editor.text-wrapping-toggle",
            preferences.text_wrapping)
        self.add_check_button(
            'Draw white chars', "editor.white-chars-toggle",
            preferences.white_chars)

        self.box.show_all()

    def add_check_button(self, label, action, value):
        """
        Function to enable button

        Args:
            self: (todo): write your description
            label: (str): write your description
            action: (str): write your description
            value: (todo): write your description
        """
        btn = Gtk.CheckButton(
            label=label,
            action_name=action,
            action_target=GLib.Variant('b', True))
        btn.set_active(value)
        self.box.pack_start(btn, True, True, 0)
# endclass


class Statusbar(Gtk.Box):
    css = Gtk.CssProvider()
    css.load_from_data(b"* {border-top: 1px solid #91918c; padding: 1px;}")

    def __init__(self, preferences):
        """
        Initialize widgets

        Args:
            self: (todo): write your description
            preferences: (list): write your description
        """
        super(Statusbar, self).__init__(orientation=Gtk.Orientation.HORIZONTAL)
        ctx = self.get_style_context()
        ctx.add_provider(Statusbar.css,
                         Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.info_bar = self.create_info_bar()
        self.pack_start(self.info_bar, False, False, 10)

        btn = StatusMenuButton(
            "Line 1, Col 1",
            LineColPopover(preferences))
        self.pack_end(btn, False, False, 1)

        self.tab_popover = self.create_tab_popover(preferences)
        self.width_btn = StatusMenuButton(
            "Tabulator width %d" % preferences.tab_width,
            self.tab_popover)
        self.pack_end(self.width_btn, False, False, 1)

        self.editor_popover = self.create_editor_popover(preferences)
        self.editor_btn = StatusMenuButton(
            "Editor",
            self.editor_popover)
        self.pack_end(self.editor_btn, False, False, 1)

    def create_tab_popover(self, preferences):
        """
        Create gtk tabs.

        Args:
            self: (todo): write your description
            preferences: (todo): write your description
        """
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, border_width=10)
        pop.add(box)

        auto_indent = Gtk.CheckButton(
            label="Auto indent",
            action_name="editor.auto-indent-toggle",
            action_target=GLib.Variant('b', True))
        box.pack_start(auto_indent, True, True, 0)

        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                       True, True, 5)

        tab_spaces_2 = Gtk.RadioButton(
            label="2",
            active=(preferences.tab_width == 2),
            action_name="editor.tab-width",
            action_target=GLib.Variant('i', 2))
        tab_spaces_2.connect("toggled", self.on_tab_spaces)
        box.pack_start(tab_spaces_2, True, True, 0)

        tab_spaces_4 = Gtk.RadioButton(
            label="4",
            active=(preferences.tab_width == 4),
            action_name="editor.tab-width",
            action_target=GLib.Variant('i', 4),
            group=tab_spaces_2)
        tab_spaces_4.connect("toggled", self.on_tab_spaces)
        box.pack_start(tab_spaces_4, True, True, 0)

        tab_spaces_8 = Gtk.RadioButton(
            label="8",
            active=(preferences.tab_width == 8),
            action_name="editor.tab-width",
            action_target=GLib.Variant('i', 8),
            group=tab_spaces_2)
        tab_spaces_8.connect("toggled", self.on_tab_spaces)
        box.pack_start(tab_spaces_8, True, True, 0)

        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                       True, True, 5)

        self.tab_use_space = Gtk.CheckButton(
            label="Use spaces",
            action_name="editor.use-spaces-toggle",
            action_target=GLib.Variant('b', True))
        box.pack_start(self.tab_use_space, True, True, 0)

        box.show_all()
        return pop

    def on_tab_spaces(self, widget):
        """
        Set the value of the selected tab.

        Args:
            self: (todo): write your description
            widget: (todo): write your description
        """
        if widget.get_active():
            self.width_btn.set_label("Tabulator width %s" %
                                     widget.get_action_target_value())

    def create_editor_popover(self, preferences):
        """
        Creates a new preferences.

        Args:
            self: (todo): write your description
            preferences: (todo): write your description
        """
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, border_width=10)
        pop.add(box)

        period_btn = Gtk.CheckButton(
            label='Save file each 5 min',
            action_name="editor.period-save-toggle",
            action_target=GLib.Variant('b', True))
        period_btn.set_active(preferences.period_save)
        box.pack_start(period_btn, True, True, 0)

        spell_btn = Gtk.CheckButton(
            label='Check Spelling',
            action_name="editor.check-spelling-toggle",
            action_target=GLib.Variant('b', True))
        spell_btn.set_active(preferences.check_spelling)
        box.pack_start(spell_btn, True, True, 0)

        box.show_all()
        return pop

    def create_info_bar(self):
        """
        Create a gtk bar object.

        Args:
            self: (todo): write your description
        """
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.words_count = Gtk.Label("0")
        bar.pack_start(bar.words_count, True, True, 0)
        bar.pack_start(Gtk.Label("words,"), True, True, 5)
        bar.chars_count = Gtk.Label("0")
        bar.pack_start(bar.chars_count, True, True, 0)
        bar.pack_start(Gtk.Label("characters"), True, True, 5)

        bar.show_all()
        return bar

    def set_words_count(self, count):
        """
        Set the number of words.

        Args:
            self: (todo): write your description
            count: (todo): write your description
        """
        self.info_bar.words_count.set_label(str(count))

    def set_chars_count(self, count):
        """
        Set the number of times in the number of times.

        Args:
            self: (todo): write your description
            count: (str): write your description
        """
        self.info_bar.chars_count.set_label(str(count))
