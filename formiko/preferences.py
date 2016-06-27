from gi.repository.GLib import Variant
from gi.repository.Gio import ThemedIcon
from gi.repository import GObject, Gtk

from sys import argv
from os.path import commonprefix

from formiko.renderer import PARSERS, WRITERS
from formiko.user import UserPreferences

PREFIX = commonprefix((argv[0], __file__))


class ActionHelper(object):
    def get_action_owner(self):
        if self.action_name:
            prefix, action = self.action_name.split('.')
            win = self.get_toplevel()
            if prefix == "win":     # yust hack :-(
                if win.has_action(action):
                    return action, win
        return '', None


class ActionableFileChooserButton(Gtk.FileChooserButton, Gtk.Actionable,
                                  ActionHelper):

    action_name = GObject.property(type=str)
    action_target = GObject.property(type=GObject.TYPE_VARIANT)

    def __init__(self, action_name=None, filename="", **kwargs):
        Gtk.FileChooserButton.__init__(self, title="Select custom stylesheet",
                                       **kwargs)
        self.add_filter_style()
        self.add_filter_all()
        if filename:
            self.set_filename(filename)
        if action_name:
            self.action_name = action_name

    def do_realize(self):
        Gtk.FileChooserButton.do_realize(self)
        action, go = self.get_action_owner()
        if go:
            self.set_filename(go.get_action_state(action).get_string())

    def set_action_name(self, action_name):
        self.action_name = action_name
        if self.get_realized():
            action, go = self.get_action_owner()
            if go:
                self.set_filename(go.get_action_state(action).get_string())

    def get_action_name(self):
        return self.action_name

    def set_action_target_value(self, target_value):
        self.action_target = target_value

    def get_action_target_value(self):
        return self.action_target

    def add_filter_style(self):
        filter_txt = Gtk.FileFilter()
        filter_txt.set_name("Stylesheet file")
        filter_txt.add_mime_type("text/css")
        self.add_filter(filter_txt)

    def add_filter_all(self):
        filter_all = Gtk.FileFilter()
        filter_all.set_name("all files")
        filter_all.add_pattern("*")
        self.add_filter(filter_all)

    def do_file_set(self):
        self.action_target = Variant("s", self.get_filename() or '')
        action, go = self.get_action_owner()
        if go:
            go.activate_action(action, self.action_target)


class Preferences(Gtk.Popover):
    def __init__(self, user_preferences):
        super(Preferences, self).__init__(border_width=20)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.add(vbox)

        self.vert_btn = Gtk.RadioButton(
            label="Vertical preview",
            action_name="win.change-preview",
            action_target=Variant('q', Gtk.Orientation.VERTICAL))
        if user_preferences.preview == Gtk.Orientation.VERTICAL:
            self.vert_btn.set_active(True)
        vbox.pack_start(self.vert_btn, True, True, 0)
        self.hori_btn = Gtk.RadioButton(
            group=self.vert_btn,
            label="Horizontal preview",
            action_name="win.change-preview",
            action_target=Variant('q', Gtk.Orientation.HORIZONTAL))
        if user_preferences.preview == Gtk.Orientation.HORIZONTAL:
            self.hori_btn.set_active(True)
        vbox.pack_start(self.hori_btn, True, True, 0)
        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                        True, True, 0)

        group = None
        for key, val in sorted(PARSERS.items()):
            enabled = val['class'] is not None
            item = Gtk.RadioButton(
                label=val['title'],
                group=group,
                sensitive=enabled,
                action_name=("win.change-parser" if enabled else None),
                action_target=Variant('s', key))
            if user_preferences.parser == key:
                item.set_active(True)
            item.parser = key
            if group is None:
                group = item
            vbox.pack_start(item, True, True, 0)
        self.parser_group = group.get_group()

        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                        True, True, 0)
        group = None
        for key, val in sorted(WRITERS.items()):
            enabled = val['class'] is not None
            item = Gtk.RadioButton(
                label=val['title'],
                group=group,
                sensitive=enabled,
                action_name=("win.change-writer" if enabled else None),
                action_target=Variant('s', key))
            if user_preferences.writer == key:
                item.set_active(True)
            item.writer = key
            if group is None:
                group = item
            vbox.pack_start(item, True, True, 0)
        self.writer_group = group.get_group()

        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                        True, True, 0)

        self.custom_btn = Gtk.CheckButton(
            label='Custom style',
            action_name="win.custom-style-toggle",
            action_target=Variant('b', True))
        self.custom_btn.set_active(user_preferences.custom_style)
        self.custom_btn.connect("toggled", self.on_custom_style_toggle)
        vbox.pack_start(self.custom_btn, True, True, 0)

        self.style_btn = ActionableFileChooserButton(
            sensitive=user_preferences.custom_style,
            action_name="win.change-style")
        vbox.pack_start(self.style_btn, True, True, 0)

        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                        True, True, 5)

        btn_box = Gtk.StackSwitcher(orientation=Gtk.Orientation.HORIZONTAL)

        sav_btn = Gtk.Button(action_name="win.save-preferences")
        icon = ThemedIcon(name="document-save-symbolic")
        sav_btn.add(Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON))
        sav_btn.set_tooltip_text("Save preferences")
        btn_box.pack_end(sav_btn, False, False, 0)

        rst_btn = Gtk.Button(action_name="win.reset-preferences")
        icon = ThemedIcon(name="view-refresh-symbolic")
        rst_btn.add(Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON))
        rst_btn.set_tooltip_text("Reset preferences")
        btn_box.pack_end(rst_btn, False, False, 0)

        vbox.pack_start(btn_box, True, True, 0)

        vbox.show_all()
    # end def

    def reset(self):
        """Reset dialogs, and preferences states to default values.

        Because actions are not restate widgets."""
        if UserPreferences.preview == Gtk.Orientation.VERTICAL:
            self.vert_btn.set_active(True)
        else:
            self.hori_btn.set_active(True)

        for it in self.parser_group:
            if it.parser == UserPreferences.parser:
                it.set_active(True)
                break

        for it in self.writer_group:
            if it.writer == UserPreferences.writer:
                it.set_active(True)
                break

        self.custom_btn.set_active(UserPreferences.custom_style)
        if not UserPreferences.style:
            self.style_btn.unselect_all()
        else:   # yes, this never happen, but ...
            self.style_btn.set_filename(UserPreferences.style)
        self.style_btn.do_file_set()    # call action

    def set_parser(self, parser):
        for it in self.parser_group:
            if it.parser == parser:
                it.set_active(True)
                break

    def on_custom_style_toggle(self, widget):
        self.style_btn.set_sensitive(widget.get_active())
