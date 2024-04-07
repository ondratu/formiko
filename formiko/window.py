"""Gtk.ApplicationWindow implementation."""
import re
from enum import Enum
from os import stat
from os.path import splitext
from threading import Thread
from traceback import print_exc

from gi.repository import Gio, GLib, Gtk

from formiko.dialogs import (
    FileOpenDialog,
    FileSaveDialog,
    QuitDialogWithoutSave,
)
from formiko.editor_actions import EditorActionGroup
from formiko.preferences import Preferences
from formiko.renderer import EXTS, Renderer
from formiko.renderer import WebView as GtkWebView
from formiko.sourceview import SourceView
from formiko.sourceview import View as GtkSourceView
from formiko.status_menu import Statusbar
from formiko.user import UserCache, UserPreferences, View
from formiko.vim import VimEditor
from formiko.widgets import IconButton

NOT_SAVED_NAME = "Untitled Document"
RE_WORD = re.compile(r"([\w]+)", re.U)
RE_CHAR = re.compile(r'[\w \t\.,\?\(\)"\']', re.U)


class SearchWay(Enum):
    NEXT = 0
    PREVIOUS = 1


class AppWindow(Gtk.ApplicationWindow):
    """Gtk.ApplicationWindow implementation."""

    # pylint: disable = too-many-public-methods
    # pylint: disable = too-many-instance-attributes
    # pylint: disable = unused-argument

    def __init__(self, editor, file_name=""):
        """Initor.

        :param str editor:
            One of editor type source, vim or None
        :param str file_name:
            File name path to open.
        """
        assert editor in ("vim", "source", None)
        self.runing = True
        self.editor_type = editor
        self.focused = None
        self.search_way = SearchWay.NEXT
        self.cache = UserCache()
        self.preferences = UserPreferences()
        super().__init__()
        self.create_renderer()
        self.actions()
        self.connect("delete-event", self.on_delete)
        self.set_titlebar(self.create_headerbar())
        self.set_default_icon_name("formiko")
        self.layout(file_name)

        self.__last_changes = 0
        if self.editor_type is None:
            _, ext = splitext(file_name)
            self.on_file_type(None, ext)
        GLib.timeout_add(200, self.check_in_thread)

    def actions(self):
        """Set window actions."""
        action = Gio.SimpleAction.new("open-document", None)
        action.connect("activate", self.on_open_document)
        self.add_action(action)

        action = Gio.SimpleAction.new("save-document", None)
        action.connect("activate", self.on_save_document)
        action.set_enabled(False)
        self.add_action(action)

        action = Gio.SimpleAction.new("save-document-as", None)
        action.connect("activate", self.on_save_document_as)
        action.set_enabled(self.editor_type == "source")
        self.add_action(action)

        action = Gio.SimpleAction.new("export-document-as", None)
        action.connect("activate", self.on_export_document_as)
        action.set_enabled(self.editor_type is not None)
        self.add_action(action)

        action = Gio.SimpleAction.new("print-document", None)
        action.connect("activate", self.on_print_document)
        self.add_action(action)

        action = Gio.SimpleAction.new("close-window", None)
        action.connect("activate", self.on_close_window)
        self.add_action(action)

        action = Gio.SimpleAction.new("find-in-document", None)
        action.connect("activate", self.on_find_in_document)
        self.add_action(action)

        action = Gio.SimpleAction.new("find-next-match", None)
        action.connect("activate", self.on_find_next_match)
        self.add_action(action)

        action = Gio.SimpleAction.new("find-previous-match", None)
        action.connect("activate", self.on_find_previous_match)
        self.add_action(action)

        self.refresh_preview_action = Gio.SimpleAction.new(
            "refresh-preview", None)
        self.refresh_preview_action.connect(
            "activate", self.on_refresh_preview)
        self.add_action(self.refresh_preview_action)

        pref = self.preferences

        self.create_stateful_action(
            "switch-view-toggle", "q", self.cache.view,
            self.on_switch_view_toggle)
        self.create_stateful_action(
            "change-preview", "q", pref.preview, self.on_change_preview)
        self.create_stateful_action(
            "auto-scroll-toggle", "b", pref.auto_scroll,
            self.on_auto_scroll_toggle)
        self.create_stateful_action(
            "change-writer", "s", pref.writer, self.on_change_writer)
        self.create_stateful_action(
            "change-parser", "s", pref.parser, self.on_change_parser)
        self.create_stateful_action(
            "custom-style-toggle", "b", pref.custom_style,
            self.on_custom_style_toggle)
        self.create_stateful_action(
            "change-style", "s", pref.style, self.on_change_style)

    def create_stateful_action(self, name, _type, default_value, method):
        """Support method for creating stateful action."""
        action = Gio.SimpleAction.new_stateful(
            name, GLib.VariantType.new(_type),
            GLib.Variant(_type, default_value))
        action.connect("change-state", method)
        self.add_action(action)

    def on_close_window(self, action, *params):
        """'close-window' action handler."""
        if self.ask_if_modified():
            self.save_win_state()
            self.destroy()

    def open_document(self, file_path):
        """Open document inw actual window."""
        if self.editor_type == "source" and \
                self.get_title() == NOT_SAVED_NAME:
            self.editor.read_from_file(file_path)
        else:
            for window in self.get_application().get_windows():
                if file_path == window.file_path:
                    window.present()
                    return
            self.get_application().new_window(self.editor_type, file_path)

    def on_open_document(self, actions, *params):
        """'on-document' action handler."""
        dialog = FileOpenDialog(self)
        dialog.add_filter_plain()
        dialog.add_filter_rst()
        dialog.add_filter_md()
        dialog.add_filter_html()
        dialog.add_filter_all()

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.open_document(dialog.get_filename())
        dialog.destroy()

    def on_save_document(self, action, *params):
        """'on-save-document' action handler."""
        if self.editor_type == "source":
            self.editor.save()

    def on_save_document_as(self, action, *params):
        """'on-save-document-as' action handler."""
        if self.editor_type == "source":
            self.editor.save_as()

    def on_export_document_as(self, action, *params):
        file_name = self.editor.file_name or None
        dialog = FileSaveDialog(self)
        if self.renderer.get_parser() == "json":
            dialog.add_filter_json()
        else:
            dialog.add_filter_html()
        dialog.add_filter_all()
        dialog.set_do_overwrite_confirmation(True)

        if file_name is None:
            dialog.set_current_folder(GLib.get_home_dir())
        else:
            name, _ = splitext(file_name)
            dialog.set_current_name(name)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            file_name = dialog.get_filename_with_ext()

            with open(file_name, "w+", encoding="utf-8") as output:
                data = self.renderer.render_output()[1].strip()
                output.write(data)
        dialog.destroy()

    def on_print_document(self, action, *params):
        self.renderer.print_page()

    def on_delete(self, *args):
        rv = self.ask_if_modified()
        if rv:
            self.save_win_state()
        return not rv

    def on_switch_view_toggle(self, action, param):
        if action.get_state() != param:
            action.set_state(param)

        state = param.get_uint16()
        self.cache.view = state
        if state == View.BOTH:
            self.editor.show()
            self.renderer.show()
            self.refresh_preview_action.set_enabled(True)
            self.both_toggle_btn.set_active(True)
        elif state == View.EDITOR:
            self.editor.show()
            self.renderer.hide()
            self.refresh_preview_action.set_enabled(False)
            self.editor_toggle_btn.set_active(True)
        else:
            self.editor.hide()
            self.renderer.show()
            self.refresh_preview_action.set_enabled(True)
            self.preview_toggle_btn.set_active(True)

    def on_change_preview(self, action, param):
        if action.get_state() != param:
            action.set_state(param)

        if not getattr(self, "paned", False):
            return
        orientation = param.get_uint16()
        if self.paned.get_orientation() != orientation:
            self.paned.set_orientation(orientation)
            self.preferences.preview = orientation
            self.preferences.save()
            GLib.idle_add(
                lambda: GLib.timeout_add(100, self.set_position) and False)

    def set_position(self):
        """Set position after change orientation.

        This must be do after some timeout. It is HARD FIX of gtk error
        https://gitlab.gnome.org/GNOME/gtk/issues/1959
        """
        if self.paned.get_orientation() == Gtk.Orientation.VERTICAL:
            self.paned.set_position(self.paned.get_allocated_height()/2)
        else:
            self.paned.set_position(self.paned.get_allocated_width()/2)

    def on_auto_scroll_toggle(self, action, param):
        auto_scroll = not self.preferences.auto_scroll
        self.preferences.auto_scroll = auto_scroll
        self.preferences.save()

    def on_change_parser(self, action, param):
        if action.get_state() != param:
            action.set_state(param)
            parser = param.get_string()
            self.renderer.set_parser(parser)
            self.preferences.parser = parser
            self.editor.change_mime_type(parser)
        self.preferences.save()

    def on_file_type(self, widget, ext):
        parser = EXTS.get(ext, self.preferences.parser)
        self.pref_menu.set_parser(parser)

    def on_scroll_changed(self, widget, position):
        if self.preferences.auto_scroll:
            self.renderer.scroll_to_position(position)

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
            self.renderer.set_style("")
        self.preferences.save()

    def on_change_style(self, action, param):
        style = param.get_string()
        self.preferences.style = style
        if self.preferences.custom_style and style:
            self.renderer.set_style(self.preferences.style)
        else:
            self.renderer.set_style("")
        self.preferences.save()

    def on_find_in_document(self, action, *param):
        if self.editor_type != "source" and not self.renderer.props.visible:
            return      # works only with source view or renderer

        if self.search.get_search_mode():
            if self.search_way == SearchWay.NEXT:
                self.on_find_next_match(action, *param)
            else:
                self.on_find_previous_match(action, *param)
        else:
            self.editor.stop_search()
            self.renderer.stop_search()

            self.search_way = SearchWay.NEXT
            self.focused = self.get_focus()
            self.search.set_search_mode(True)
            self.search_entry.grab_focus()
            if self.search_text:
                self.search_entry.set_text(self.search_text)
                self.search_entry.select_region(0, -1)

    def on_search_focus_out(self, search_entry, param):
        # on_search_focus_out is called by on_search_mode_changed
        # so text will be reset
        self.search_text = self.search_entry.get_text()
        # stop searching when click to editor
        if self.search.get_search_mode():
            self.search.set_search_mode(False)

    def on_search_mode_changed(self, search_bar, param):
        if not self.search.get_search_mode():
            if not self.search_text:
                if isinstance(self.focused, GtkSourceView):
                    self.editor.stop_search()
                elif isinstance(self.focused, GtkWebView):
                    self.renderer.stop_search()
                elif self.editor_type == "source" and \
                        self.editor.props.visible:
                    self.editor.stop_search()
                elif self.renderer.props.visible:
                    self.renderer.stop_search()

            self.focused.grab_focus()
            self.focused = None

    def on_search_changed(self, search_entry):
        if self.search_way == SearchWay.NEXT:
            res = self.on_find_next_match(None, None)
        else:
            res = self.on_find_previous_match(None, None)

        ctx = self.search_entry.get_style_context()
        if not res and self.search_entry.get_text():
            Gtk.StyleContext.add_class(ctx, "error")
        else:
            Gtk.StyleContext.remove_class(ctx, "error")

    def on_find_next_match(self, action, *params):
        res = False
        if self.search.get_search_mode():
            text = self.search_entry.get_text()

            if isinstance(self.focused, GtkSourceView):
                res = self.editor.do_next_match(text)
            elif isinstance(self.focused, GtkWebView):
                res = self.renderer.do_next_match(text)
            elif self.editor_type == "source" and self.editor.props.visible:
                res = self.editor.do_next_match(text)
            elif self.renderer.props.visible:
                res = self.renderer.do_next_match(text)
        return res

    def on_find_previous_match(self, action, *params):
        res = False
        if self.search.get_search_mode():
            text = self.search_entry.get_text()

            if isinstance(self.focused, GtkSourceView):
                res = self.editor.do_previous_match(text)
            elif isinstance(self.focused, GtkWebView):
                res = self.renderer.do_previous_match(text)
            elif self.editor_type == "source" and self.editor.props.visible:
                res = self.editor.do_previous_match(text)
            elif self.renderer.props.visible:
                res = self.renderer.do_previous_match(text)
        return res

    def on_refresh_preview(self, action, *params):
        self.check_in_thread(True)

    def ask_if_modified(self):
        if self.editor_type:
            if self.editor.is_modified:
                dialog = QuitDialogWithoutSave(self,
                                               self.editor.file_name)
                if dialog.run() != Gtk.ResponseType.OK:
                    dialog.destroy()
                    return False        # fo not quit
            self.runing = False
            if self.editor_type == "vim":
                self.editor.vim_quit()  # do call destroy_from_vim
        else:
            self.runing = False
        return True                     # do quit

    def destroy_from_vim(self, *args):
        self.runing = False
        self.destroy()

    def save_win_state(self):
        self.cache.width, self.cache.height = self.get_size()
        if getattr(self, "paned", False):
            self.cache.paned = self.paned.get_position()
        self.cache.is_maximized = self.is_maximized()
        self.cache.save()

    def create_headerbar(self):
        headerbar = Gtk.HeaderBar()
        headerbar.set_show_close_button(True)

        headerbar.pack_start(IconButton(symbol="document-new-symbolic",
                             tooltip="New Document",
                             action_name="app.new-window"))
        headerbar.pack_start(IconButton(symbol="document-open-symbolic",
                             tooltip="Open Document",
                             action_name="win.open-document"))

        if self.editor_type == "source":
            headerbar.pack_start(IconButton(symbol="document-save-symbolic",
                                            tooltip="Save Document",
                                            action_name="win.save-document"))

        self.pref_menu = Preferences(self.preferences)

        btn = Gtk.MenuButton(popover=self.pref_menu)
        icon = Gio.ThemedIcon(name="emblem-system-symbolic")
        btn.add(Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON))
        btn.set_tooltip_text("Preferences")
        headerbar.pack_end(btn)

        headerbar.pack_end(IconButton(symbol="view-refresh-symbolic",
                                      tooltip="Refresh preview",
                                      action_name="win.refresh-preview"))

        if self.editor_type:
            btn_box = Gtk.ButtonBox.new(orientation=Gtk.Orientation.HORIZONTAL)
            Gtk.StyleContext.add_class(btn_box.get_style_context(), "linked")

            self.editor_toggle_btn = Gtk.ToggleButton(
                label="_Editor",
                use_underline=True,
                action_name="win.switch-view-toggle",
                action_target=GLib.Variant("q", View.EDITOR))
            self.editor_toggle_btn.set_tooltip_text("Show Editor")
            btn_box.pack_start(self.editor_toggle_btn, True, True, 0)

            self.preview_toggle_btn = Gtk.ToggleButton(
                label="_Preview",
                use_underline=True,
                action_name="win.switch-view-toggle",
                action_target=GLib.Variant("q", View.PREVIEW))
            self.preview_toggle_btn.set_tooltip_text("Show Web Preview")
            btn_box.pack_start(self.preview_toggle_btn, True, True, 0)

            self.both_toggle_btn = Gtk.ToggleButton(
                label="_Both",
                use_underline=True,
                action_name="win.switch-view-toggle",
                action_target=GLib.Variant("q", View.BOTH))
            self.both_toggle_btn.set_tooltip_text(
                "Show Editor and Web Preview")
            btn_box.pack_start(self.both_toggle_btn, True, True, 0)

            headerbar.pack_end(btn_box)
        return headerbar

    def create_renderer(self):
        self.renderer = Renderer(self,
                                 parser=self.preferences.parser,
                                 writer=self.preferences.writer)
        if self.preferences.custom_style and self.preferences.style:
            self.renderer.set_style(self.preferences.style)
        self.renderer.set_tab_width(self.preferences.editor.tab_width)

    def fill_panned(self, file_name):
        if self.editor_type == "vim":
            self.editor = VimEditor(self, file_name)
        else:
            self.editor = SourceView(self,
                                     self.preferences,
                                     "editor.spell-lang")
            self.insert_action_group("editor",
                                     EditorActionGroup(self.editor,
                                                       self.renderer,
                                                       self.preferences))

        self.editor.connect("file-type", self.on_file_type)
        self.editor.connect("scroll-changed", self.on_scroll_changed)

        if file_name:
            self.editor.read_from_file(file_name)

        self.paned.pack1(self.editor, True, False)
        self.paned.pack2(self.renderer, True, False)

        if self.cache.view == View.EDITOR:
            self.renderer.show_all()
            self.renderer.hide()
            self.renderer.set_no_show_all(True)
            self.refresh_preview_action.set_enabled(False)
        elif self.cache.view == View.PREVIEW:
            self.editor.show_all()
            self.editor.hide()
            self.editor.set_no_show_all(True)

    def layout(self, file_name):
        self.set_default_size(self.cache.width, self.cache.height)
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.add(box)

        overlay = Gtk.Overlay()
        box.pack_start(overlay, True, True, 0)

        if self.editor_type:
            self.paned = Gtk.Paned(orientation=self.preferences.preview,
                                   position=self.cache.paned)
            overlay.add_overlay(self.paned)
            self.fill_panned(file_name)
        else:
            self.__file_name = file_name
            self.set_title(file_name)
            overlay.add_overlay(self.renderer)

        if self.cache.is_maximized:
            self.maximize()

        if self.editor_type == "source":
            self.status_bar = Statusbar(self.preferences.editor)
            box.pack_end(self.status_bar, False, True, 0)

        self.search_text = ""
        self.search = Gtk.SearchBar()
        self.search.set_show_close_button(False)
        self.search.set_halign(Gtk.Align.CENTER)
        self.search.set_valign(Gtk.Align.START)
        self.search.connect("notify::search-mode-enabled",
                            self.on_search_mode_changed)
        overlay.add_overlay(self.search)

        sbox = Gtk.Box(Gtk.Orientation.HORIZONTAL, 0)
        Gtk.StyleContext.add_class(sbox.get_style_context(), "linked")
        self.search.add(sbox)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_width_chars(30)
        sbox.pack_start(self.search_entry, True, True, 0)
        self.search.connect_entry(self.search_entry)
        self.search_entry.connect("search-changed",
                                  self.on_search_changed)
        self.search_entry.connect("focus-out-event",
                                  self.on_search_focus_out)
        prev_button = IconButton(
                symbol="go-previous-symbolic",
                tooltip="Previeous search",
                action_name="win.find-previous-match",
                focus_on_click=False)
        sbox.pack_start(prev_button, False, False, 0)
        next_button = IconButton(
                symbol="go-next-symbolic",
                tooltip="Next search",
                action_name="win.find-next-match",
                focus_on_click=False)
        sbox.pack_start(next_button, False, False, 0)

    def check_in_thread(self, force=False):
        if self.runing:
            if self.editor_type == "vim":
                thread = Thread(target=self.refresh_from_vim, args=(force,))
                thread.start()
            elif self.editor_type == "source":
                GLib.idle_add(self.refresh_from_source, force)
            else:   # self.editor = None
                GLib.idle_add(self.refresh_from_file, force)

    def not_running(self):
        if not self.runing:
            raise SystemExit(0)

    def refresh_from_vim(self, force):
        another_file = False
        try:
            star = "*" if self.editor.is_modified else ""
            self.not_running()
            title = star + (self.editor.file_name or NOT_SAVED_NAME)
            if title != self.get_title():
                GLib.idle_add(self.set_title, title)
                another_file = True
            self.not_running()
            last_changes = self.editor.get_vim_changes()

            if force or last_changes > self.__last_changes or another_file:
                self.__last_changes = last_changes
                self.not_running()
                lines = self.editor.get_vim_lines()
                self.not_running()
                buff = self.editor.get_vim_get_buffer(lines)
                self.not_running()
                row, col = self.editor.get_vim_pos()
                pos = 0
                for _i in range(row-1):
                    new_line = buff.find("\n", pos)
                    if new_line < 0:
                        break
                    pos = new_line + 1
                pos += col
                self.renderer.render(buff, self.editor.file_path, pos)
            GLib.timeout_add(300, self.check_in_thread)
        except SystemExit:
            return
        except BaseException:
            print_exc()

    def refresh_from_source(self, force):
        try:
            modified = self.editor.is_modified
            action = self.lookup_action("save-document")
            if action:  # sometimes when closing window action is None
                action.set_enabled(modified)

            star = "*" if modified else ""
            title = star + (self.editor.file_name or NOT_SAVED_NAME)
            if title != self.get_title():
                self.set_title(title)

            last_changes = self.editor.changes
            if force or last_changes > self.__last_changes:
                self.__last_changes = last_changes
                text = self.editor.text

                words_count = 0
                for _w in RE_WORD.finditer(text):
                    words_count += 1
                self.status_bar.set_words_count(words_count)

                chars_count = 0
                for _c in RE_CHAR.finditer(text):
                    chars_count += 1
                self.status_bar.set_chars_count(chars_count)

                self.renderer.render(text, self.editor.file_path,
                                     self.editor.position)
            GLib.timeout_add(100, self.check_in_thread)
        except BaseException:
            print_exc()

    def refresh_from_file(self, force):
        try:
            last_changes = stat(self.__file_name).st_ctime
            if force or last_changes > self.__last_changes:
                self.__last_changes = last_changes
                with open(self.__file_name) as source:
                    buff = source.read()
                    self.renderer.render(buff, self.__file_name,
                                         self.renderer.position)
        except BaseException:
            print_exc()
        GLib.timeout_add(500, self.check_in_thread)

    @property
    def file_path(self):
        return self.editor.file_path if self.editor_type else self.__file_name
