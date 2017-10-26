from gi.repository import Gtk
from gi.repository.Gio import ThemedIcon


class IconButton(Gtk.Button):
    def __init__(self, symbol, tooltip, **kwargs):
        super(IconButton, self).__init__(**kwargs)
        icon = ThemedIcon(name=symbol)
        self.add(Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON))
        self.set_tooltip_text(tooltip)


class ActionHelper(object):
    def get_action_owner(self):
        if self.action_name:
            prefix, action = self.action_name.split('.')
            win = self.get_toplevel()
            if prefix == "win":     # yust hack :-(
                if win.has_action(action):
                    return action, win
        return '', None
