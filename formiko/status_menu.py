from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib


class StatusMenuButton(Gtk.MenuButton):
    css = Gtk.CssProvider()
    css.load_from_data(bytes("""
            * {
                border: 0;
                padding: 1px 8px 2px 4px;
                outline-width: 0;
            }
        """, "utf-8"))

    def __init__(self, label, popover):
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
        self.label.set_label(label)
# endclass


class LineColPopover(Gtk.Popover):
    def __init__(self, preferences):
        super(LineColPopover, self).__init__()

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                           border_width=10)
        self.add(self.box)

        self.add_check_button(
            'Display line numbers', "editor.line-numbers-toggle",
            preferences.line_numbers)
        self.add_check_button(
            'Display right margin', "editor.right-margin-toggle",
            preferences.line_numbers)

        self.box.show_all()

    def add_check_button(self, label, action, value):
        btn = Gtk.CheckButton(
            label=label,
            action_name=action,
            action_target=GLib.Variant('b', True))
        btn.set_active(value)
        self.box.pack_start(btn, True, True, 0)
# endclass


class Statusbar(Gtk.Statusbar):
    def __init__(self, preferences):
        super(Statusbar, self).__init__()

        self.editor_popover = self.create_editor_popover(preferences)
        self.editor_btn = StatusMenuButton(
            "Editor",
            self.editor_popover)
        self.pack_start(self.editor_btn, False, False, 1)

        self.tab_popover = self.create_tab_popover(preferences)
        self.width_btn = StatusMenuButton(
            "Tabulator width %d" % preferences.tab_width,
            self.tab_popover)
        self.pack_start(self.width_btn, False, False, 1)

        btn = StatusMenuButton(
            "Line 1, Col 1",
            LineColPopover(preferences))
        self.pack_start(btn, False, False, 1)

    def create_tab_popover(self, preferences):
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
            action_name="editor.tab-width",
            action_target=GLib.Variant('i', 2))
        tab_spaces_2.connect("toggled", self.on_tab_spaces)
        if preferences.tab_width == 2:
            tab_spaces_2.set_active(True)
        box.pack_start(tab_spaces_2, True, True, 0)

        tab_spaces_4 = Gtk.RadioButton(
            label="4",
            action_name="editor.tab-width",
            action_target=GLib.Variant('i', 4),
            group=tab_spaces_2)
        tab_spaces_4.connect("toggled", self.on_tab_spaces)
        if preferences.tab_width == 4:
            tab_spaces_2.set_active(True)
        box.pack_start(tab_spaces_4, True, True, 0)

        tab_spaces_8 = Gtk.RadioButton(
            label="8",
            action_name="editor.tab-width",
            action_target=GLib.Variant('i', 8),
            group=tab_spaces_2)
        tab_spaces_8.connect("toggled", self.on_tab_spaces)
        if preferences.tab_width == 8:
            tab_spaces_2.set_active(True)
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
        if widget.get_active():
            self.width_btn.set_label("Tabulator width %s" %
                                     widget.get_action_target_value())

    def create_editor_popover(self, preferences):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, border_width=10)
        pop.add(box)

        period_btn = Gtk.CheckButton(
            label='Save file each 5 min',
            action_name="editor.period-save-toggle",
            action_target=GLib.Variant('b', True))
        period_btn.set_active(preferences.period_save)
        box.pack_start(period_btn, True, True, 0)

        box.show_all()
        return pop
