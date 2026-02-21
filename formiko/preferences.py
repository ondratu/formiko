"""Preferences widget."""
from os.path import commonprefix
from sys import argv

from gi.repository import GLib, GObject, Gtk
from gi.repository.GLib import Variant

from formiko.dialogs import run_dialog
from formiko.renderer import PARSERS, WRITERS
from formiko.widgets import ActionHelper

PREFIX = commonprefix((argv[0], __file__))


def set_tooltip(item: Gtk.CheckButton, enabled: bool, val: dict):
    """Set right tooltip for parser or writer radio button."""
    tooltip = ""
    if not enabled:
        package = val.get("package", val["title"])
        tooltip = f"Please intall {package}."

    if "url" in val:
        tooltip += f" More info at {val['url']}"

    if tooltip:
        item.set_tooltip_text(tooltip)


class ActionableFileButton(Gtk.Button, Gtk.Actionable, ActionHelper):
    """Button that opens a file chooser dialog and supports actions."""

    action_name = GObject.property(type=str)
    action_target = GObject.property(type=GObject.TYPE_VARIANT)

    def __init__(self, action_name=None, filename="", **kwargs):
        Gtk.Button.__init__(self, label=filename or "Select stylesheet…",
                            **kwargs)
        self._filename = filename
        if action_name:
            self.action_name = action_name
        self.connect("clicked", self._on_clicked)

    def do_realize(self):
        """Realize and set filename from action state."""
        Gtk.Button.do_realize(self)
        action, go = self.get_action_owner()
        if go:
            fname = go.get_action_state(action).get_string()
            self._set_filename(fname)

    def _set_filename(self, filename):
        """Update stored filename and button label."""
        self._filename = filename
        label = filename if filename else "Select stylesheet…"
        self.set_label(label)

    def set_action_name(self, action_name):
        """Set action name to widget."""
        self.action_name = action_name
        if self.get_realized():
            action, go = self.get_action_owner()
            if go:
                self._set_filename(go.get_action_state(action).get_string())

    def get_action_name(self):
        """Return action name from widget."""
        return self.action_name

    def set_action_target_value(self, target_value):
        """Set action target."""
        self.action_target = target_value

    def get_action_target_value(self):
        """Get action target."""
        return self.action_target

    def _on_clicked(self, _btn):
        """Open file chooser dialog."""
        root = self.get_root()
        dialog = Gtk.FileChooserDialog(
            title="Select custom stylesheet",
            transient_for=root,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Open", Gtk.ResponseType.ACCEPT)

        css_filter = Gtk.FileFilter()
        css_filter.set_name("Stylesheet file")
        css_filter.add_mime_type("text/css")
        dialog.add_filter(css_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("all files")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

        if self._filename:
            dialog.set_current_folder(
                GLib.get_dirname(self._filename) or GLib.get_home_dir(),
            )

        if run_dialog(dialog) == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            fname = gfile.get_path() if gfile else ""
            self._set_filename(fname)
            self.action_target = Variant("s", fname)
            action, go = self.get_action_owner()
            if go:
                go.activate_action(action, self.action_target)
        dialog.destroy()


class Preferences(Gtk.Popover):
    """Preferences widget."""

    def __init__(self, user_preferences):
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.set_child(vbox)

        self.vert_btn = Gtk.CheckButton(
            label="Vertical preview",
            action_name="win.change-preview",
            action_target=Variant("q", Gtk.Orientation.VERTICAL),
        )
        if user_preferences.preview == Gtk.Orientation.VERTICAL:
            self.vert_btn.set_active(True)
        vbox.append(self.vert_btn)

        self.hori_btn = Gtk.CheckButton(
            label="Horizontal preview",
            group=self.vert_btn,
            action_name="win.change-preview",
            action_target=Variant("q", Gtk.Orientation.HORIZONTAL),
        )
        if user_preferences.preview == Gtk.Orientation.HORIZONTAL:
            self.hori_btn.set_active(True)
        vbox.append(self.hori_btn)

        self.auto_scroll_btn = Gtk.CheckButton(
            label="Auto scroll",
            action_name="win.auto-scroll-toggle",
        )
        vbox.append(self.auto_scroll_btn)

        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        group = None
        for key, val in PARSERS.items():
            enabled = val["class"] is not None
            item = Gtk.CheckButton(
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
            vbox.append(item)
        self.parser_group = group

        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        group = None
        for key, val in WRITERS.items():
            enabled = val["class"] is not None
            item = Gtk.CheckButton(
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
            vbox.append(item)
        self.writer_group = group

        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self.custom_btn = Gtk.CheckButton(
            label="Custom style",
            action_name="win.custom-style-toggle",
        )
        self.custom_btn.connect("toggled", self.on_custom_style_toggle)
        vbox.append(self.custom_btn)

        self.style_btn = ActionableFileButton(
            sensitive=user_preferences.custom_style,
            action_name="win.change-style",
        )
        vbox.append(self.style_btn)

    def set_parser(self, parser):
        """Set right parser."""
        btn = self.parser_group
        while btn:
            if getattr(btn, "parser", None) == parser:
                btn.set_active(True)
                break
            btn = btn.get_next_in_group() if hasattr(
                btn, "get_next_in_group",
            ) else None

    def on_custom_style_toggle(self, widget):
        """Set sensitive for own style."""
        self.style_btn.set_sensitive(widget.get_active())
