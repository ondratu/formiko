"""Preferences widget."""

from math import pi
from os.path import commonprefix
from sys import argv

from gi.repository import GLib, GObject, Gtk
from gi.repository.GLib import Variant

from formiko.dialogs import build_css_filters, open_file_dialog
from formiko.renderer import PARSERS, WRITERS, component_available
from formiko.widgets import ActionHelper

PREFIX = commonprefix((argv[0], __file__))


def set_tooltip(item: Gtk.CheckButton, enabled: bool, val: dict):
    """Set right tooltip for parser or writer radio button."""
    tooltip = ""
    if not enabled:
        package = val.get("package", val["title"])
        tooltip = f"Please install {package}."

    if "url" in val:
        tooltip += f" More info at {val['url']}"

    if tooltip:
        item.set_tooltip_text(tooltip)


class ActionableFileButton(Gtk.Button, Gtk.Actionable, ActionHelper):
    """Button that opens a file chooser dialog and supports actions."""

    action_name = GObject.property(type=str)
    action_target = GObject.property(type=GObject.TYPE_VARIANT)

    def __init__(self, action_name=None, filename="", **kwargs):
        Gtk.Button.__init__(
            self,
            label=filename or "Select stylesheet…",
            **kwargs,
        )
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
        filters, css_filter = build_css_filters()
        initial_folder = (
            GLib.path_get_dirname(self._filename) or GLib.get_home_dir()
            if self._filename else None
        )
        open_file_dialog(
            self.get_root(),
            "Select custom stylesheet",
            filters, css_filter,
            initial_folder=initial_folder,
            callback=self._apply_stylesheet,
        )

    def _apply_stylesheet(self, fname):
        """Apply selected stylesheet path."""
        self._set_filename(fname)
        self.action_target = Variant("s", fname)
        root = self.get_root()
        if root:
            root.activate_action(self.action_name, self.action_target)


class ColorSchemeIcon(Gtk.DrawingArea):
    """Draw a symbolic circular icon for a color-scheme choice."""

    def __init__(self, scheme):
        super().__init__(content_width=16, content_height=16)
        self.scheme = scheme
        self.set_draw_func(self._draw)

    def _draw(self, _widget, cr, width, height):
        radius = min(width, height) / 2 - 1
        cx, cy = width / 2, height / 2
        cr.arc(cx, cy, radius, 0, 2 * pi)
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.35)
        cr.fill_preserve()
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.9)
        cr.stroke()
        if self.scheme == "dark":
            cr.arc(cx, cy, radius - 1, 0, 2 * pi)
            cr.set_source_rgba(0.12, 0.12, 0.12, 1)
            cr.fill()
        elif self.scheme == "light":
            cr.arc(cx, cy, radius - 1, 0, 2 * pi)
            cr.set_source_rgba(1, 1, 1, 1)
            cr.fill()
        elif self.scheme == "default":
            cr.move_to(cx, cy - radius)
            cr.arc(cx, cy, radius - 1, -pi / 2, pi / 2)
            cr.close_path()
            cr.set_source_rgba(0.12, 0.12, 0.12, 1)
            cr.fill()


class Preferences(Gtk.Popover):
    """Preferences widget."""

    def __init__(self, user_preferences):  # noqa: C901
        super().__init__()
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.set_child(vbox)

        vbox.append(Gtk.Label(label="Appearance", xalign=0))
        theme_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        theme_box.add_css_class("linked")
        theme_buttons = (
            ("default", "Use system appearance"),
            ("light", "Use light appearance"),
            ("dark", "Use dark appearance"),
        )
        theme_group = None
        theme_box.set_homogeneous(True)
        for scheme, tooltip in theme_buttons:
            button = Gtk.ToggleButton()
            button.set_child(ColorSchemeIcon(scheme))
            button.set_tooltip_text(tooltip)
            button.set_action_name("win.change-color-scheme")
            button.set_action_target_value(Variant("s", scheme))
            if theme_group is not None:
                button.set_group(theme_group)
            else:
                theme_group = button
            button.set_active(user_preferences.color_scheme == scheme)
            button.set_hexpand(True)
            button.set_halign(Gtk.Align.FILL)
            theme_box.append(button)
        theme_box.set_hexpand(True)
        vbox.set_size_request(360, -1)
        vbox.append(theme_box)
        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

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
            enabled = component_available(val)
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
            enabled = component_available(val)
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

        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self.wakatime_btn = Gtk.CheckButton(
            label="Enable WakaTime",
            action_name="win.wakatime-toggle",
        )
        self.wakatime_btn.connect("toggled", self.on_wakatime_toggle)
        vbox.append(self.wakatime_btn)

        self.wakatime_key_entry = Gtk.PasswordEntry(
            show_peek_icon=True,
            placeholder_text="WakaTime API key",
            sensitive=user_preferences.wakatime_enabled,
            text=user_preferences.wakatime_api_key,
        )
        self.wakatime_key_entry.connect(
            "activate", self.on_wakatime_key_activate,
        )
        vbox.append(self.wakatime_key_entry)

    def set_parser(self, parser):
        """Set right parser."""
        btn = self.parser_group
        while btn:
            if getattr(btn, "parser", None) == parser:
                btn.set_active(True)
                break
            btn = (
                btn.get_next_in_group()
                if hasattr(
                    btn,
                    "get_next_in_group",
                )
                else None
            )

    def on_custom_style_toggle(self, widget):
        """Set sensitive for own style."""
        self.style_btn.set_sensitive(widget.get_active())

    def on_wakatime_toggle(self, widget):
        """Set sensitive for the WakaTime API key entry."""
        self.wakatime_key_entry.set_sensitive(widget.get_active())

    def on_wakatime_key_activate(self, entry):
        """Apply WakaTime API key on Enter."""
        root = self.get_root()
        if root:
            root.activate_action(
                "win.change-wakatime-key",
                Variant("s", entry.get_text()),
            )
