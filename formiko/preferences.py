"""Preferences widget."""
from os.path import commonprefix
from sys import argv

from gi.repository import GObject, Gtk
from gi.repository.GLib import Variant

from formiko.renderer import PARSERS, WRITERS
from formiko.widgets import ActionHelper

PREFIX = commonprefix((argv[0], __file__))


def set_tooltip(item: Gtk.RadioButton, enabled: bool, val: dict):
    """Set right tooltip for parser or writer radio button."""
    tooltip = ""
    if not enabled:
        package = val.get("package", val["title"])
        tooltip = f"Please intall {package}."

    if "url" in val:
        tooltip += f" More info at {val['url']}"

    if tooltip:
        item.set_tooltip_text(tooltip)


class ActionableFileChooserButton(
    Gtk.FileChooserButton,
    Gtk.Actionable,
    ActionHelper,
):
    """FileChooserButton with actions."""

    action_name = GObject.property(type=str)
    action_target = GObject.property(type=GObject.TYPE_VARIANT)

    def __init__(self, action_name=None, filename="", **kwargs):
        Gtk.FileChooserButton.__init__(
            self,
            title="Select custom stylesheet",
            **kwargs,
        )
        self.add_filter_style()
        self.add_filter_all()
        if filename:
            self.set_filename(filename)
        if action_name:
            self.action_name = action_name

    def do_realize(self):
        """Realize and set filename."""
        Gtk.FileChooserButton.do_realize(self)
        action, go = self.get_action_owner()
        if go:
            self.set_filename(go.get_action_state(action).get_string())

    def set_action_name(self, action_name):
        """Set action name."""
        self.action_name = action_name
        if self.get_realized():
            action, go = self.get_action_owner()
            if go:
                self.set_filename(go.get_action_state(action).get_string())

    def get_action_name(self):
        """Return action name."""
        return self.action_name

    def set_action_target_value(self, target_value):
        """Set action target."""
        self.action_target = target_value

    def get_action_target_value(self):
        """Get action target."""
        return self.action_target

    def add_filter_style(self):
        """Add filter for style sheets files."""
        filter_txt = Gtk.FileFilter()
        filter_txt.set_name("Stylesheet file")
        filter_txt.add_mime_type("text/css")
        self.add_filter(filter_txt)

    def add_filter_all(self):
        """Add filter for all files."""
        filter_all = Gtk.FileFilter()
        filter_all.set_name("all files")
        filter_all.add_pattern("*")
        self.add_filter(filter_all)

    def do_file_set(self):
        """Set the file and emit the action."""
        self.action_target = Variant("s", self.get_filename() or "")
        action, go = self.get_action_owner()
        if go:
            go.activate_action(action, self.action_target)


class Preferences(Gtk.Popover):
    """Preferences widget."""

    def __init__(self, user_preferences):
        super().__init__(border_width=20)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.add(vbox)

        self.vert_btn = Gtk.RadioButton(
            label="Vertical preview",
            action_name="win.change-preview",
            action_target=Variant("q", Gtk.Orientation.VERTICAL),
        )
        if user_preferences.preview == Gtk.Orientation.VERTICAL:
            self.vert_btn.set_active(True)
        vbox.pack_start(self.vert_btn, True, True, 0)
        self.hori_btn = Gtk.RadioButton(
            group=self.vert_btn,
            label="Horizontal preview",
            action_name="win.change-preview",
            action_target=Variant("q", Gtk.Orientation.HORIZONTAL),
        )
        if user_preferences.preview == Gtk.Orientation.HORIZONTAL:
            self.hori_btn.set_active(True)
        vbox.pack_start(self.hori_btn, True, True, 0)

        self.auto_scroll_btn = Gtk.CheckButton(
            label="Auto scroll",
            action_name="win.auto-scroll-toggle",
            action_target=Variant("b", True),
        )
        self.auto_scroll_btn.set_active(user_preferences.auto_scroll)
        vbox.pack_start(self.auto_scroll_btn, True, True, 0)

        vbox.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            True,
            True,
            0,
        )

        group = None
        for key, val in PARSERS.items():
            enabled = val["class"] is not None
            item = Gtk.RadioButton(
                label=val["title"],
                group=group,
                sensitive=enabled,
                action_name=("win.change-parser" if enabled else None),
                action_target=Variant("s", key),
            )
            if user_preferences.parser == key:
                item.set_active(True)
            item.parser = key
            set_tooltip(item, enabled, val)
            if group is None:
                group = item
            vbox.pack_start(item, True, True, 0)
        self.parser_group = group.get_group()

        vbox.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            True,
            True,
            0,
        )
        group = None
        for key, val in WRITERS.items():
            enabled = val["class"] is not None
            item = Gtk.RadioButton(
                label=val["title"],
                group=group,
                sensitive=enabled,
                action_name=("win.change-writer" if enabled else None),
                action_target=Variant("s", key),
            )
            if user_preferences.writer == key:
                item.set_active(True)
            item.writer = key
            set_tooltip(item, enabled, val)
            if group is None:
                group = item
            vbox.pack_start(item, True, True, 0)
        self.writer_group = group.get_group()

        vbox.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
            True,
            True,
            0,
        )

        self.custom_btn = Gtk.CheckButton(
            label="Custom style",
            action_name="win.custom-style-toggle",
            action_target=Variant("b", True),
        )
        self.custom_btn.set_active(user_preferences.custom_style)
        self.custom_btn.connect("toggled", self.on_custom_style_toggle)
        vbox.pack_start(self.custom_btn, True, True, 0)

        self.style_btn = ActionableFileChooserButton(
            sensitive=user_preferences.custom_style,
            action_name="win.change-style",
        )
        vbox.pack_start(self.style_btn, True, True, 0)

        vbox.show_all()

    def set_parser(self, parser):
        """Set right parser."""
        for it in self.parser_group:
            if it.parser == parser:
                it.set_active(True)
                break

    def on_custom_style_toggle(self, widget):
        """Set sensitive for own style."""
        self.style_btn.set_sensitive(widget.get_active())
