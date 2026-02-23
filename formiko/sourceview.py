"""SourceView based editor widget.."""
from os import fstat, rename, stat
from os.path import basename, dirname, exists, isfile, splitext
from sys import stderr
from traceback import format_exc

from gi.repository import Adw, Gio, GObject, Gtk, GtkSource
from gi.repository.GLib import (
    UserDirectory,
    Variant,
    get_user_special_dir,
    idle_add,
    timeout_add,
    timeout_add_seconds,
)
from gi.repository.GtkSource import (
    Buffer,
    SearchContext,
    SearchSettings,
    View,
)

from formiko.dialogs import (
    LANGS,
    FileChangedDialog,
    FileSaveDialog,
    TraceBackDialog,
    run_alert_dialog,
    run_dialog,
)
from formiko.widgets import ActionHelper, ImutableDict

try:
    from gi.repository import Spelling
    _SPELLING_AVAILABLE = True
except ImportError:
    _SPELLING_AVAILABLE = False

PERIOD_SAVE_TIME = 300  # 5min


class SourceView(Gtk.ScrolledWindow, ActionHelper):
    """Widget containted SourceView."""

    __file_name = ""
    __last_changes = 0
    __last_ctime = 0
    __pause_period = False

    __gsignals__ = ImutableDict({
        "file-type": (GObject.SIGNAL_RUN_FIRST, None, (str,)),
        "scroll-changed": (GObject.SIGNAL_RUN_LAST, None, (float,)),
    })

    action_name = GObject.property(type=str)
    action_target = GObject.property(type=GObject.TYPE_VARIANT)

    def __init__(self, win, preferences, action_name=None):
        GtkSource.init()
        if _SPELLING_AVAILABLE:
            Spelling.init()
        super().__init__()
        if action_name:
            self.action_name = action_name

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.text_buffer = Buffer.new_with_language(
            LANGS["."+preferences.parser],
        )
        self.text_buffer.connect("changed", self.inc_changes)
        self.source_view = View.new_with_buffer(self.text_buffer)

        adj = self.get_vadjustment()
        adj.connect("value-changed", self.on_scroll_changed)

        # Set monospace font via CSS provider
        css = Gtk.CssProvider()
        css.load_from_string("textview { font-family: Monospace; }")
        self.source_view.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.set_child(self.source_view)

        # Follow Adwaita dark/light mode for syntax highlighting scheme
        self._apply_color_scheme(self._is_dark())
        Adw.StyleManager.get_default().connect(
            "notify::dark", self.on_style_scheme_changed,
        )
        Gtk.Settings.get_default().connect(
            "notify::gtk-theme-name", self.on_style_scheme_changed,
        )

        # Initialize spell checker
        self.spell_adapter = None
        self.checker = None
        if _SPELLING_AVAILABLE:
            self.checker = Spelling.Checker.get_default()
            self.spell_adapter = Spelling.TextBufferAdapter.new(
                self.text_buffer, self.checker,
            )
            self.spell_adapter.set_enabled(False)  # off until user enables
            self.source_view.insert_action_group(
                "spelling", self.spell_adapter,
            )
            self.source_view.set_extra_menu(
                self.spell_adapter.get_menu_model(),
            )
            # Connect to checker (not adapter) — context menu's language action
            # calls spelling_checker_set_language() directly, bypassing the
            # adapter's own notify::language signal.
            self.checker.connect(
                "notify::language",
                self.on_language_changed,
            )

        editor_pref = preferences.editor
        self.set_period_save(editor_pref.period_save)
        self.set_check_spelling(
            editor_pref.check_spelling,
            editor_pref.spell_lang,
        )
        self.set_spaces_instead_of_tabs(editor_pref.spaces_instead_of_tabs)
        self.source_view.set_tab_width(editor_pref.tab_width)
        self.source_view.set_auto_indent(editor_pref.auto_indent)
        self.source_view.set_show_line_numbers(editor_pref.line_numbers)
        self.source_view.set_right_margin_position(
            editor_pref.right_margin_value,
        )
        self.source_view.set_show_right_margin(editor_pref.right_margin)
        self.source_view.set_highlight_current_line(editor_pref.current_line)
        self.set_text_wrapping(editor_pref.text_wrapping)
        self.set_white_chars(editor_pref.white_chars)

        self.search_settings = SearchSettings(wrap_around=True)
        self.search_context = SearchContext.new(
            self.text_buffer,
            self.search_settings,
        )
        self.search_mark = None

        self.__win = win
        timeout_add(200, self.check_in_thread)

    @property
    def changes(self):
        """Return number of changes."""
        return self.__last_changes

    @property
    def is_modified(self):
        """Return if text is modified."""
        return self.text_buffer.get_modified()

    @property
    def text(self):
        """Return text."""
        return self.text_buffer.props.text

    @property
    def position(self):
        """Return cursor position."""
        adj = self.source_view.get_vadjustment()
        hight = self.get_height()
        value = adj.get_value()
        if value:
            return adj.get_value() / (adj.get_upper() - hight)
        return 0

    @property
    def file_name(self):
        """Return opened file name."""
        return basename(self.__file_name)

    @property
    def file_path(self):
        """Return opened file name with path."""
        return self.__file_name

    @property
    def file_ext(self):
        """Returned opened file extension."""
        _, ext = splitext(self.__file_name)
        return ext

    def inc_changes(self, text_buffer):
        """Incrace changes from last storing to storage."""
        self.__last_changes += 1

    @staticmethod
    def _is_dark():
        """Return True if dark mode is active.

        Checks both Adwaita StyleManager and the GTK theme name so that
        the correct colour scheme is applied regardless of whether the
        user switches via GNOME Settings (color-scheme) or GNOME Tweaks
        (gtk-theme-name).
        """
        if Adw.StyleManager.get_default().get_dark():
            return True
        theme = Gtk.Settings.get_default().get_property("gtk-theme-name")
        return "dark" in theme.lower()

    def _apply_color_scheme(self, is_dark):
        """Apply Adwaita or Adwaita-dark source view color scheme."""
        scheme_id = "Adwaita-dark" if is_dark else "Adwaita"
        manager = GtkSource.StyleSchemeManager.get_default()
        scheme = manager.get_scheme(scheme_id)
        if scheme:
            self.text_buffer.set_style_scheme(scheme)

    def on_style_scheme_changed(self, *_):
        """React to dark/light mode change (Adwaita or GTK theme name)."""
        self._apply_color_scheme(self._is_dark())

    def change_mime_type(self, parser):
        """Change internal mime type for right syntax highlighting."""
        language = LANGS.get("."+parser, LANGS[".rst"])
        if self.text_buffer.get_language() != language:
            self.text_buffer.set_language(language)

    def on_language_changed(self, checker, pspec):
        """Proxy the language change action and re-check the buffer."""
        if self.spell_adapter is not None:
            self.spell_adapter.invalidate_all()
        action, go = self.get_action_owner()
        if go:
            code = checker.get_language() or ""
            go.activate_action(action, Variant("s", code))

    def on_scroll_changed(self, *_):
        """Emit scroll event."""
        self.emit("scroll-changed", self.position)

    def set_period_save(self, save):
        """Set period save and start save thread."""
        self.period_save = bool(save) * PERIOD_SAVE_TIME
        if save:
            self.period_save_thread()

    def set_check_spelling(self, check_spelling, spell_lang):
        """Set spell check."""
        if self.spell_adapter is None:
            return
        if check_spelling:
            if spell_lang:
                self.spell_adapter.set_language(spell_lang)
            else:
                # No saved language: save the system default (GTK3 behaviour)
                self.on_language_changed(self.checker, None)
            self.spell_adapter.set_enabled(True)
        else:
            self.spell_adapter.set_enabled(False)

    def set_spaces_instead_of_tabs(self, use_spaces):
        """Set spaces instead of tabs."""
        self.source_view.set_insert_spaces_instead_of_tabs(use_spaces)
        self.source_view.set_smart_backspace(use_spaces)

    def set_text_wrapping(self, text_wrapping):
        """Set text wrapping mode."""
        if text_wrapping:
            self.source_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        else:
            self.source_view.set_wrap_mode(Gtk.WrapMode.NONE)

    def set_white_chars(self, white_chars):
        """Set white chars showing."""
        space_drawer = self.source_view.get_space_drawer()
        space_drawer.set_enable_matrix(white_chars)

    def check_in_thread(self):
        """Check source file time.

        This function is called from GLib.timeout_add
        """
        if not self.__file_name:
            return
        if not self.__win.get_realized():
            return  # window was closed, stop the loop
        if not self.__win.is_active():
            timeout_add(200, self.check_in_thread)
            return
        try:
            last_ctime = stat(self.__file_name).st_ctime
            if last_ctime > self.__last_ctime:
                self.__pause_period = True
                dialog = FileChangedDialog(self.__file_name)
                if run_alert_dialog(dialog, self.__win) == "yes":
                    cursor = self.text_buffer.get_insert()
                    offset = self.text_buffer.get_iter_at_mark(
                        cursor,
                    ).get_offset()

                    self.read_from_file(self.__file_name, offset)
                else:
                    self.__last_ctime = last_ctime

                dialog.destroy()
                self.__pause_period = False
        except OSError:
            pass  # file switching when modify by another software
        timeout_add(200, self.check_in_thread)

    def period_save_thread(self):
        """Create timeouted save."""
        if self.period_save:
            if (
                self.__file_name
                and self.is_modified
                and not self.__pause_period
            ):
                idle_add(self.save_to_file)
            timeout_add_seconds(self.period_save, self.period_save_thread)

    def read_from_file(self, file_name, offset=0):
        """Read file and set all states."""
        self.__file_name = file_name
        self.emit("file_type", self.file_ext)

        if isfile(file_name):
            with open(file_name, encoding="utf-8") as src:
                self.text_buffer.set_text(src.read())
                self.__last_changes += 1
                self.__last_ctime = fstat(src.fileno()).st_ctime

        self.text_buffer.set_modified(False)
        if offset > -1:
            cursor = self.text_buffer.get_iter_at_offset(offset)
            self.text_buffer.place_cursor(cursor)
            idle_add(self.scroll_to_cursor, cursor)

    def scroll_to_cursor(self, cursor):
        """Scroll to cursor position."""
        self.source_view.scroll_to_iter(cursor, 0, 1, 1, 1)

    def save_to_file(self):
        """Save text to file."""
        try:
            if exists(self.__file_name):
                rename(self.__file_name, self.__file_name+"~")
            with open(self.__file_name, "w", encoding="utf-8") as src:
                src.write(self.text)
                self.__last_ctime = fstat(src.fileno()).st_ctime
            self.text_buffer.set_modified(False)
        except Exception:
            error = format_exc()
            if self.__win:
                md = TraceBackDialog(error)
                run_alert_dialog(md, self.__win)
            stderr.write(error)
            stderr.flush()

    def save(self):
        """Save the file."""
        if not self.__file_name:
            self.__file_name = self.get_new_file_name()
            self.emit("file_type", self.file_ext)
        if self.__file_name:
            self.save_to_file()

    def save_as(self):
        """Save the file as another."""
        new_file_name = self.get_new_file_name()
        if new_file_name:
            self.__file_name = new_file_name
            self.emit("file_type", self.file_ext)
            self.save_to_file()

    def get_new_file_name(self):
        """Get new file name and destionation."""
        lang = self.text_buffer.get_language()
        dialog = FileSaveDialog(self.__win)
        dialog.add_filter_rst(lang.get_id() == "rst")
        dialog.add_filter_md(lang.get_id() == "markdown")
        dialog.add_filter_html(lang.get_id() == "html")
        dialog.add_filter_json(lang.get_id() == "json")
        dialog.add_filter_plain(lang.get_id() == "text")

        if not self.__file_name:
            dialog.set_current_folder(
                Gio.File.new_for_path(
                    get_user_special_dir(UserDirectory.DIRECTORY_DOCUMENTS),
                ),
            )
            dialog.set_current_name("Untitled document")
        else:
            dialog.set_current_folder(
                Gio.File.new_for_path(dirname(self.file_path)),
            )
            dialog.set_current_name(self.file_name)

        file_name = ""
        if run_dialog(dialog) == Gtk.ResponseType.ACCEPT:
            file_name = dialog.get_filename_with_ext()
        dialog.destroy()
        return file_name

    def do_file_type(self, ext):
        """Set file type for right syntax highlighting."""
        if ext:
            language = LANGS.get(ext, LANGS[".rst"])
            if self.text_buffer.get_language() != language:
                self.text_buffer.set_language(language)

    def do_next_match(self, text):
        """Find next search match."""
        if self.search_settings.get_search_text() != text:
            self.search_settings.set_search_text(text)
            self.search_mark = self.text_buffer.get_insert()
            search_iter = self.text_buffer.get_iter_at_mark(self.search_mark)
        elif self.search_mark:
            search_iter = self.text_buffer.get_iter_at_mark(self.search_mark)
            search_iter.forward_char()
        else:
            return False

        found, search_iter, _end, _ = self.search_context.forward(search_iter)

        if not found:
            self.search_mark = None
            return False
        self.source_view.scroll_to_iter(search_iter, 0, 1, 1, 1)
        self.text_buffer.place_cursor(search_iter)
        return True

    def do_previous_match(self, text):
        """Find previous search match."""
        if self.search_settings.get_search_text() != text:
            self.search_settings.set_search_text(text)
            self.search_mark = self.text_buffer.get_insert()
            search_iter = self.text_buffer.get_iter_at_mark(self.search_mark)
        elif self.search_mark:
            search_iter = self.text_buffer.get_iter_at_mark(self.search_mark)
        else:
            return False

        found, _start, search_iter, _ = self.search_context.backward(
            search_iter,
        )
        if not found:
            self.search_mark = None
            return False
        search_iter.backward_chars(len(text))
        self.source_view.scroll_to_iter(search_iter, 0, 1, 1, 1)
        self.text_buffer.place_cursor(search_iter)
        return True

    def stop_search(self):
        """Stop searching."""
        self.search_settings.set_search_text(None)
