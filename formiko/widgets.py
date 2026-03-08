"""Gtk Widgets extensions."""

from gi.repository import GObject, Gtk
from gi.repository.GLib import Variant


def connect_accel_tooltip(widget, tooltip_text, accel_action=None):
    """Set a tooltip that includes the registered keyboard shortcut.

    The tooltip is initially set to *tooltip_text*.  When the widget is
    realised the handler looks up the accelerators registered with the
    application for *accel_action* (or the widget's own action_name when
    *accel_action* is ``None``) and appends the shortcut in parentheses,
    e.g. ``"Save Document (Ctrl+S)"``.
    """
    widget.set_tooltip_text(tooltip_text)

    def on_realize(_w):
        action = accel_action
        if action is None:
            get_name = getattr(_w, "get_action_name", None)
            if get_name:
                action = get_name()
        if not action:
            return
        app = Gtk.Application.get_default()
        if not app:
            return
        accels = app.get_accels_for_action(action)
        if not accels:
            return
        result = Gtk.accelerator_parse(accels[0])
        if not result[0]:
            return
        label = Gtk.accelerator_get_label(
            result.accelerator_key, result.accelerator_mods,
        )
        _w.set_tooltip_text(f"{tooltip_text} ({label})")

    widget.connect("realize", on_realize)


class ImutableDict(dict):
    """Imutable dict implementation."""

    def __hash__(self):
        """Return hash."""
        return id(self)

    def _immutable(self, *args, **kws):
        raise TypeError

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    update = _immutable
    setdefault = _immutable
    pop = _immutable
    popitem = _immutable


class IconButton(Gtk.Button):
    """Icon button with themed icon."""

    def __init__(self, symbol, tooltip, **kwargs):
        super().__init__(**kwargs)
        self.set_icon_name(symbol)
        connect_accel_tooltip(self, tooltip)


class ActionHelper:
    """Support class for own Actionable widgets."""

    # pylint: disable=too-few-public-methods
    def get_action_owner(self):
        """Get action owner."""
        action_name = self.action_name
        if action_name:
            prefix, action = action_name.split(".")
            root = self.get_root()
            top = root.get_action_group(prefix) if root else None
            if top and top.has_action(action):
                return action, top
        return "", None


class ActionableSpinButton(Gtk.SpinButton, Gtk.Actionable, ActionHelper):
    """Gtk.SpinButton with action support."""

    action_name = GObject.Property(type=str)
    action_target = GObject.Property(type=GObject.TYPE_VARIANT)

    def __init__(self, action_name=None, **kwargs):
        Gtk.SpinButton.__init__(self, **kwargs)

        if action_name:
            self.action_name = action_name

    def do_realize(self):
        """Realize SpinButton and set the action."""
        Gtk.SpinButton.do_realize(self)
        action, top = self.get_action_owner()
        if top:
            self.set_value(top.get_action_state(action).get_double())

    def set_action_name(self, action_name):
        """Set action name to widget."""
        self.action_name = action_name
        if self.get_realized():
            action, top = self.get_action_owner()
            if top:
                self.set_value(top.get_action_state(action).get_double())

    def get_action_name(self):
        """Return action name from widget."""
        return self.action_name

    def set_action_target_value(self, target_value):
        """Set action target."""
        self.action_target = target_value

    def get_action_target_value(self):
        """Get action target."""
        return self.action_target

    def do_value_changed(self):
        """Activate action if value was changed."""
        self.action_target = Variant("d", self.get_value() or 0.0)
        root = self.get_root()
        if root:
            root.activate_action(self.action_name, self.action_target)
