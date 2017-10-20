# -*- coding: utf-8 -*-
from gi.repository import Gtk, GLib, Gio

from threading import Thread
from traceback import print_exc
from os import stat
from os.path import splitext
from sys import version_info
from io import open

from formiko.vim import VimEditor
from formiko.sourceview import SourceView
from formiko.renderer import Renderer, EXTS
from formiko.dialogs import QuitDialogWithoutSave, FileOpenDialog, \
    FileSaveDialog
from formiko.preferences import Preferences
from formiko.user import UserCache, UserPreferences
from formiko.icons import icon_list
from formiko.status_menu import Statusbar

NOT_SAVED_NAME = 'Not saved document'


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, editor, file_name=''):
        assert editor in ('vim', 'source', None)
        self.runing = True
        self.editor_type = editor
        self.cache = UserCache()
        self.preferences = UserPreferences()
        super(AppWindow, self).__init__()
        self.create_renderer()
        self.actions()
        self.connect("delete-event", self.on_delete)
        self.set_titlebar(self.create_headerbar())
        self.set_icon_list(icon_list)
        self.layout(file_name)

        self.__last_changes = 0
        if self.editor_type is None:
            name, ext = splitext(file_name)
            self.on_file_type(None, ext)
        GLib.timeout_add(200, self.check_in_thread)

    def actions(self):
        action = Gio.SimpleAction.new("open-document", None)
        action.connect("activate", self.on_open_document)
        self.add_action(action)

        action = Gio.SimpleAction.new("save-document", None)
        action.connect("activate", self.on_save_document)
        action.set_enabled(False)
        self.add_action(action)

        action = Gio.SimpleAction.new("save-document-as", None)
        action.connect("activate", self.on_save_document_as)
        action.set_enabled(self.editor_type == 'source')
        self.add_action(action)

        action = Gio.SimpleAction.new("export-document-as", None)
        action.connect("activate", self.on_export_document_as)
        action.set_enabled(self.editor_type is not None)
        self.add_action(action)

        action = Gio.SimpleAction.new("close-window", None)
        action.connect("activate", self.on_close_window)
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "editor-toggle", GLib.VariantType.new('b'),
            GLib.Variant('b', True))
        action.connect("change-state", self.on_change_editor_toogle)
        self.add_action(action)
        self.show_editor = True

        action = Gio.SimpleAction.new_stateful(
            "preview-toggle", GLib.VariantType.new('b'),
            GLib.Variant('b', True))
        action.connect("change-state", self.on_change_preview_toogle)
        self.add_action(action)
        self.show_preview = True

        action = Gio.SimpleAction.new_stateful(
            "change-preview", GLib.VariantType.new('q'),
            GLib.Variant('q', self.preferences.preview))
        action.connect("change-state", self.on_change_preview)
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "change-writer", GLib.VariantType.new("s"),
            GLib.Variant('s', self.preferences.writer))
        action.connect("change-state", self.on_change_writer)
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "change-parser", GLib.VariantType.new('s'),
            GLib.Variant('s', self.preferences.parser))
        action.connect("change-state", self.on_change_parser)
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "custom-style-toggle", GLib.VariantType.new('b'),
            GLib.Variant('b', self.preferences.custom_style))
        action.connect("change-state", self.on_custom_style_toggle)
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "change-style", GLib.VariantType.new('s'),
            GLib.Variant('s', self.preferences.style))
        action.connect("change-state", self.on_change_style)
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "period-save-toggle", GLib.VariantType.new('b'),
            GLib.Variant('b', self.preferences.period_save))
        action.connect("change-state", self.on_period_save_toggle)
        action.set_enabled(self.editor_type == 'source')
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "use-spaces-toggle", GLib.VariantType.new('b'),
            GLib.Variant('b', self.preferences.spaces_instead_of_tabs))
        action.connect("change-state", self.on_use_spaces_toogle)
        action.set_enabled(self.editor_type == 'source')
        self.add_action(action)

        action = Gio.SimpleAction.new_stateful(
            "tab-width", GLib.VariantType.new('i'),
            GLib.Variant('i', self.preferences.tab_width))
        action.connect("change-state", self.on_tab_width)
        action.set_enabled(self.editor_type == 'source')
        self.add_action(action)

    def on_close_window(self, action, *params):
        if self.ask_if_modified():
            self.save_win_state()
            self.destroy()

    def on_open_document(self, actions, *params):
        dialog = FileOpenDialog(self)
        dialog.add_filter_plain()
        dialog.add_filter_rst()
        dialog.add_filter_md()
        dialog.add_filter_html()
        dialog.add_filter_all()

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            if self.editor_type == 'source' and \
                    self.get_title() == NOT_SAVED_NAME:
                self.editor.read_from_file(dialog.get_filename())
            else:
                self.get_application().new_window(self.editor_type,
                                                  dialog.get_filename())
        dialog.destroy()

    def on_save_document(self, action, *params):
        if self.editor_type == 'source':
            self.editor.save(self)

    def on_save_document_as(self, action, *params):
        if self.editor_type == 'source':
            self.editor.save_as(self)

    def on_export_document_as(self, action, *params):
        file_name = self.editor.file_name or None
        dialog = FileSaveDialog(self)
        if self.renderer.get_parser() == 'json':
            dialog.add_filter_json()
        else:
            dialog.add_filter_html()
        dialog.add_filter_all()
        dialog.set_do_overwrite_confirmation(True)

        if file_name is None:
            dialog.set_current_folder(GLib.get_home_dir())
        else:
            dialog.set_current_name(file_name[:file_name.rfind('.')])

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            extensions = getattr(dialog.get_filter(), 'extensions', ())
            file_name = dialog.get_filename()
            ex_ok = False
            for extension in extensions:
                if file_name.lower().endswith(extension):
                    ex_ok = True
                    break
            if not ex_ok and extensions:
                file_name += extensions[0]

            with open(file_name, "w+", encoding="utf-8") as output:
                data = self.renderer.render_output()[1].strip()
                if version_info.major == 2:
                    output.write(data.encode("utf-8"))
                else:   # python 3.x
                    output.write(data)
        dialog.destroy()

    def on_delete(self, *args):
        rv = self.ask_if_modified()
        if rv:
            self.save_win_state()
        return not rv

    def on_change_editor_toogle(self, action, param):
        self.show_editor = not self.show_editor
        if self.show_editor:
            self.editor.show()
            return
        elif not self.show_preview:
            self.preview_toggle_btn.set_active(True)
        self.editor.hide()

    def on_change_preview_toogle(self, action, param):
        self.show_preview = not self.show_preview
        if self.show_preview:
            self.renderer.show()
            return
        elif not self.show_editor:
            self.editor_toggle_btn.set_active(True)
        self.renderer.hide()

    def on_change_preview(self, action, param):
        if action.get_state() != param:
            action.set_state(param)

        if not getattr(self, 'paned', False):
            return
        orientation = param.get_uint16()
        if self.paned.get_orientation() != orientation:
            self.paned.set_orientation(orientation)
            if orientation == Gtk.Orientation.HORIZONTAL:
                self.paned.set_position(self.paned.get_allocated_width()/2)
            else:
                self.paned.set_position(self.paned.get_allocated_height()/2)
            self.preferences.preview = orientation
            self.preferences.save()

    def on_change_parser(self, action, param):
        if action.get_state() != param:
            action.set_state(param)
            parser = param.get_string()
            self.renderer.set_parser(parser)
            self.preferences.parser = parser
        self.preferences.save()

    def on_file_type(self, widget, ext):
        parser = EXTS.get(ext, self.preferences.parser)
        self.pref_menu.set_parser(parser)

    def on_change_writer(self, action, param):
        if action.get_state() != param:
            action.set_state(param)
            writer = param.get_string()
            self.renderer.set_writer(writer)
            self.preferences.writer = writer
            self.preferences.save()

    def on_custom_style_toggle(self, action, param):
        custom_style = not self.preferences.custom_style
        self.preferences.custom_style = custom_style
        if custom_style and self.preferences.style:
            self.renderer.set_style(self.preferences.style)
        else:
            self.renderer.set_style('')
        self.preferences.save()

    def on_change_style(self, action, param):
        style = param.get_string()
        self.preferences.style = style
        if self.preferences.custom_style and style:
            self.renderer.set_style(self.preferences.style)
        else:
            self.renderer.set_style('')
        self.preferences.save()

    def on_period_save_toggle(self, action, param):
        period_save = not self.preferences.period_save
        self.preferences.period_save = period_save
        self.editor.set_period_save(period_save)
        self.preferences.save()

    def on_use_spaces_toogle(self, action, param):
        use_spaces = not self.preferences.spaces_instead_of_tabs
        self.preferences.spaces_instead_of_tabs = use_spaces
        self.editor.set_spaces_instead_of_tabs(use_spaces)
        self.preferences.save()

    def on_tab_width(self, action, param):
        width = param.get_int32()
        self.preferences.tab_width = width
        self.editor.set_tab_width(width)
        self.renderer.set_tab_width(width)
        self.preferences.save()

    def ask_if_modified(self):
        if self.editor_type:
            if self.editor.is_modified:
                dialog = QuitDialogWithoutSave(self,
                                               self.editor.file_name)
                if dialog.run() != Gtk.ResponseType.OK:
                    dialog.destroy()
                    return False        # fo not quit
            self.runing = False
            if self.editor_type == 'vim':
                self.editor.vim_quit()  # do call destroy_from_vim
        else:
            self.runing = False
        return True                     # do quit

    def destroy_from_vim(self, *args):
        self.runing = False
        self.destroy()

    def save_win_state(self):
        self.cache.width, self.cache.height = self.get_size()
        if getattr(self, 'paned', False):
            self.cache.paned = self.paned.get_position()
        self.cache.is_maximized = self.is_maximized()
        self.cache.save()

    def create_headerbar(self):
        headerbar = Gtk.HeaderBar()
        headerbar.set_show_close_button(True)

        btn = Gtk.Button(label="Open", action_name="win.open-document")
        headerbar.pack_start(btn)

        if self.editor_type == 'source':
            btn = Gtk.Button(label="Save", action_name="win.save-document")
            headerbar.pack_start(btn)

        self.pref_menu = Preferences(self.preferences)

        btn = Gtk.MenuButton(popover=self.pref_menu)
        icon = Gio.ThemedIcon(name="emblem-system-symbolic")
        btn.add(Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON))
        btn.set_tooltip_text("Preferences")
        headerbar.pack_end(btn)

        if self.editor_type != 'preview':
            btn_box = Gtk.ButtonBox.new(orientation=Gtk.Orientation.HORIZONTAL)
            Gtk.StyleContext.add_class(btn_box.get_style_context(), "linked")

            self.editor_toggle_btn = Gtk.ToggleButton(
                label="Editor",
                action_name="win.editor-toggle",
                action_target=GLib.Variant('b', True))
            btn_box.pack_start(self.editor_toggle_btn, True, True, 0)

            self.preview_toggle_btn = Gtk.ToggleButton(
                label="Preview",
                action_name="win.preview-toggle",
                action_target=GLib.Variant('b', True))
            btn_box.pack_start(self.preview_toggle_btn, True, True, 0)

            headerbar.pack_end(btn_box)
        return headerbar

    def create_renderer(self):
        self.renderer = Renderer(self,
                                 parser=self.preferences.parser,
                                 writer=self.preferences.writer)
        if self.preferences.custom_style and self.preferences.style:
            self.renderer.set_style(self.preferences.style)
        self.renderer.set_tab_width(self.preferences.tab_width)

    def fill_panned(self, file_name):
        if self.editor_type == 'vim':
            self.editor = VimEditor(self, file_name)
            self.editor.connect("file_type", self.on_file_type)
        else:
            self.editor = SourceView(self.preferences)
            self.editor.connect("file_type", self.on_file_type)
            if file_name:
                self.editor.read_from_file(file_name)
        self.paned.add1(self.editor)
        self.paned.add2(self.renderer)

    def layout(self, file_name):
        self.set_default_size(self.cache.width, self.cache.height)
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.add(box)

        if self.editor_type:
            self.paned = Gtk.Paned(orientation=self.preferences.preview,
                                   position=self.cache.paned)
            box.pack_start(self.paned, True, True, 0)
            self.fill_panned(file_name)
        else:
            self.file_name = file_name
            self.set_title(file_name)
            box.pack_start(self.renderer, True, True, 0)

        if self.cache.is_maximized:
            self.maximize()

        if self.editor_type == 'source':
            box.pack_end(Statusbar(self.preferences), False, True, 0)

    def check_in_thread(self):
        if self.runing:
            if self.editor_type == 'vim':
                thread = Thread(target=self.refresh_from_vim)
            elif self.editor_type == 'source':
                thread = Thread(target=self.refresh_from_source)
            else:   # self.editor = None
                thread = Thread(target=self.refresh_from_file)
            thread.start()

    def not_running(self):
        if not self.runing:
            raise SystemExit(0)

    def refresh_from_vim(self):
        another_file = False
        try:
            star = '*' if self.editor.is_modified else ''
            self.not_running()
            title = star + (self.editor.file_name or NOT_SAVED_NAME)
            if title != self.get_title():
                GLib.idle_add(self.set_title, title)
                another_file = True
            self.not_running()
            last_changes = self.editor.get_vim_changes()

            if last_changes > self.__last_changes or another_file:
                self.__last_changes = last_changes
                self.not_running()
                lines = self.editor.get_vim_lines()
                self.not_running()
                buff = self.editor.get_vim_get_buffer(lines)
                self.not_running()
                row, col = self.editor.get_vim_pos()
                pos = 0
                for i in range(row-1):
                    new_line = buff.find('\n', pos)
                    if new_line < 0:
                        break
                    pos = new_line + 1
                pos += col
                self.renderer.render(buff, self.editor.file_path, pos)
            GLib.timeout_add(300, self.check_in_thread)
        except SystemExit:
            return
        except:
            print_exc()

    def refresh_from_source(self):
        try:
            modified = self.editor.is_modified
            self.lookup_action("save-document").set_enabled(modified)

            star = '*' if modified else ''
            title = star + (self.editor.file_name or NOT_SAVED_NAME)
            if title != self.get_title():
                GLib.idle_add(self.set_title, title)

            last_changes = self.editor.changes
            if last_changes > self.__last_changes:
                self.__last_changes = last_changes
                self.renderer.render(self.editor.text, self.editor.file_path,
                                     self.editor.position)
            GLib.timeout_add(100, self.check_in_thread)
        except:
            print_exc()

    def refresh_from_file(self):
        try:
            last_changes = stat(self.file_name).st_ctime
            if last_changes > self.__last_changes:
                self.__last_changes = last_changes
                with open(self.file_name) as source:
                    buff = source.read()
                    self.renderer.render(buff, self.file_name)
        except:
            print_exc()
        GLib.timeout_add(500, self.check_in_thread)
