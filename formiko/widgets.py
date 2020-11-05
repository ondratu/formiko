from gi.repository import Gtk
from gi.repository.Gio import ThemedIcon


class IconButton(Gtk.Button):
    def __init__(self, symbol, tooltip, **kwargs):
        """
        Initializes a gtk widget.

        Args:
            self: (todo): write your description
            symbol: (str): write your description
            tooltip: (todo): write your description
        """
        super(IconButton, self).__init__(**kwargs)
        icon = ThemedIcon(name=symbol)
        self.add(Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON))
        self.set_tooltip_text(tooltip)


class ActionHelper(object):
    def get_action_owner(self):
        """
        Returns the action name for the action.

        Args:
            self: (todo): write your description
        """
        if self.action_name:
            prefix, action = self.action_name.split('.')
            go = self.get_toplevel().get_action_group(prefix)
            if go and go.has_action(action):
                return action, go
        return '', None
