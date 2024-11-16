"""Gtk Widgets extensions."""

from gi.repository import GObject, Gtk
from gi.repository.Gio import ThemedIcon
from gi.repository.GLib import Variant


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
        icon = ThemedIcon(name=symbol)
        self.set_image(Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON))
        self.set_tooltip_text(tooltip)


class ActionHelper:
    """Support class for own Actionable widgets."""

    # pylint: disable=too-few-public-methods
    def get_action_owner(self):
        """Get action owner."""
        action_name = self.action_name
        if action_name:
            prefix, action = action_name.split(".")
            toplevel = self.get_toplevel
            top = toplevel().get_action_group(prefix)
            if top and top.has_action(action):
                return action, top
        return "", None


class ActionableSpinButton(Gtk.SpinButton, Gtk.Actionable, ActionHelper):
    """Gtk.SpinButton with action support."""

    action_name = GObject.property(type=str)
    action_target = GObject.property(type=GObject.TYPE_VARIANT)

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
        action, top = self.get_action_owner()
        if top:
            top.activate_action(action, self.action_target)
