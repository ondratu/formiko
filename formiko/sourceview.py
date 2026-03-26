"""SourceView based editor widget.."""

import re
from os import fstat, rename, stat
from os.path import basename, dirname, exists, isfile, splitext
from sys import stderr
from traceback import format_exc

from gi.repository import Adw, Gdk, Gio, GObject, Gtk, GtkSource, Pango
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
    LANG_BY_EXT,
    FileChangedDialog,
    TraceBackDialog,
    build_save_filters,
    run_alert_dialog,
    save_file_dialog,
)
from formiko.format_utils import (
    compute_toggle_bullet,
    compute_toggle_format,
    compute_toggle_line_exclusive,
    compute_toggle_line_format,
    compute_toggle_ordered,
    compute_toggle_rst_header,
)
from formiko.widgets import ActionHelper, ImutableDict

try:
    from gi.repository import Spelling

    _SPELLING_AVAILABLE = True
except ImportError:
    _SPELLING_AVAILABLE = False

PERIOD_SAVE_TIME = 300  # 5min

# Matches ordered-list prefix with at least one content char: "  2. x"
_RE_ORDERED_CONT = re.compile(r"^(\s*)(\d+)\. \S")
# Matches bullet-list prefix with at least one content char: "  - x"
_RE_BULLET_CONT = re.compile(r"^(\s*)([-*] )\S")


def _is_list_line(line_text: str) -> bool:
    """Return True if the line begins with a list marker (after any indent)."""
    return bool(re.match(r"^\s*([-*] |\d+\. )", line_text))


def _list_continuation_marker(line_text: str) -> "str | None":
    """Return the list marker to insert on the next line, or ``None``."""
    m = _RE_ORDERED_CONT.match(line_text)
    if m:
        return f"{m.group(1)}{int(m.group(2)) + 1}. "
    m = _RE_BULLET_CONT.match(line_text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return None


class SourceView(Gtk.ScrolledWindow, ActionHelper):
    """Widget containted SourceView."""

    __file_name = ""
    __last_changes = 0
    __last_ctime = 0
    __pause_period = False

    __gsignals__ = ImutableDict(
        {
            "file-type": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
            "scroll-changed": (GObject.SignalFlags.RUN_LAST, None, (float,)),
        },
    )

    action_name = GObject.Property(type=str)
    action_target = GObject.Property(type=GObject.TYPE_VARIANT)

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
            LANG_BY_EXT["." + preferences.parser],
        )
        self.text_buffer.connect("changed", self.inc_changes)
        self.source_view = View.new_with_buffer(self.text_buffer)
        self.setup_list_features()

        adj = self.get_vadjustment()
        adj.connect("value-changed", self.on_scroll_changed)

        # Set monospace font from system settings (GNOME monospace-font-name)
        self._font_css = Gtk.CssProvider()
        self.source_view.get_style_context().add_provider(
            self._font_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._apply_system_font()
        try:
            self._desktop_settings = Gio.Settings(
                schema_id="org.gnome.desktop.interface",
            )
            self._desktop_settings.connect(
                "changed::monospace-font-name",
                self._on_system_font_changed,
            )
        except Exception:  # noqa: S110
            pass  # schema not available (non-GNOME desktop)

        # Apply source_view properties BEFORE set_child() to avoid triggering
        # an extra GTK4 LAYOUT cycle after the widget is inserted into the tree.
        # Setting these after set_child() causes the GTK4 alloc_needed deadlock
        # when GtkSource's syntax engine calls queue_resize during LAYOUT.
        editor_pref = preferences.editor
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
        self._auto_bullet_pref = editor_pref.auto_bullet
        self._tab_indent_pref = editor_pref.tab_indent_bullet

        # Apply color scheme to the buffer before inserting into the widget tree.
        # text_buffer.set_style_scheme() does not need a realized widget, and
        # applying it after set_child() can trigger queue_resize on the view.
        self._apply_color_scheme(self._is_dark())

        # Initialize spell checker before set_child() — TextBufferAdapter, action
        # groups, and extra menus all operate on the buffer or view object itself
        # (no widget tree needed), so initialising them here avoids triggering
        # an extra LAYOUT cycle after the view enters the tree.
        self.spell_adapter = None
        self.checker = None
        if _SPELLING_AVAILABLE:
            self.checker = Spelling.Checker.get_default()
            self.spell_adapter = Spelling.TextBufferAdapter.new(
                self.text_buffer,
                self.checker,
            )
            self.spell_adapter.set_enabled(False)  # off until user enables
            self.source_view.insert_action_group(
                "spelling",
                self.spell_adapter,
            )
            self.source_view.set_extra_menu(
                self.spell_adapter.get_menu_model(),
            )
            self.checker.connect(
                "notify::language",
                self.on_language_changed,
            )

        self.set_check_spelling(
            editor_pref.check_spelling,
            editor_pref.spell_lang,
        )

        # SearchContext operates on the buffer, not the widget tree.
        self.search_settings = SearchSettings(wrap_around=True)
        self.search_context = SearchContext.new(
            self.text_buffer,
            self.search_settings,
        )
        self.search_mark = None

        self.set_child(self.source_view)

        # Follow Adwaita dark/light mode for syntax highlighting scheme
        Adw.StyleManager.get_default().connect(
            "notify::dark",
            self.on_style_scheme_changed,
        )
        Gtk.Settings.get_default().connect(
            "notify::gtk-theme-name",
            self.on_style_scheme_changed,
        )

        self.__win = win
        self.set_period_save(editor_pref.period_save)
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

    def _apply_system_font(self):
        """Apply the system monospace font (GNOME gsettings) to the editor."""
        font_name = "Monospace 11"
        try:
            settings = Gio.Settings(schema_id="org.gnome.desktop.interface")
            font_name = settings.get_string("monospace-font-name") or font_name
        except Exception:  # noqa: S110
            pass
        desc = Pango.FontDescription.from_string(font_name)
        family = desc.get_family() or "Monospace"
        size_pts = desc.get_size() / Pango.SCALE if desc.get_size() else 11
        css = (
            f'textview {{ font-family: "{family}"; font-size: {size_pts}pt; }}'
        )
        self._font_css.load_from_string(css)

    def _on_system_font_changed(self, _settings, _key):
        """React to system monospace font change."""
        self._apply_system_font()

    def change_mime_type(self, parser):
        """Change internal mime type for right syntax highlighting."""
        language = LANG_BY_EXT.get("." + parser, LANG_BY_EXT[".rst"])
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

    def setup_list_features(self):
        """Set up list auto-continuation and Tab-indent (initially disabled).

        Call :meth:`set_list_features_enabled` to activate/deactivate.
        Both features share :func:`_is_list_line` for bullet detection.
        """
        self._list_handler_id = None
        self._tab_key_ctrl_active = False
        self._parser_supports_lists = False
        self._auto_bullet_pref = True
        self._tab_indent_pref = True
        self._tab_key_ctrl = Gtk.EventControllerKey.new()
        self._tab_key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self._tab_key_ctrl.connect("key-pressed", self._on_tab_key_pressed)

    def set_list_features_enabled(self, enabled):
        """Enable or disable list features based on parser support."""
        self._parser_supports_lists = enabled
        self._apply_auto_bullet()
        self._apply_tab_indent_bullet()

    def _apply_auto_bullet(self):
        """Apply auto-bullet state based on parser support and user pref."""
        should = self._parser_supports_lists and self._auto_bullet_pref
        active = self._list_handler_id is not None
        if should == active:
            return
        if should:
            self._list_handler_id = self.text_buffer.connect(
                "insert-text",
                self._on_list_insert_text,
            )
        else:
            self.text_buffer.disconnect(self._list_handler_id)
            self._list_handler_id = None

    def _apply_tab_indent_bullet(self):
        """Apply Tab-indent state based on parser support and user pref."""
        should = self._parser_supports_lists and self._tab_indent_pref
        if should == self._tab_key_ctrl_active:
            return
        if should:
            self.source_view.add_controller(self._tab_key_ctrl)
        else:
            self.source_view.remove_controller(self._tab_key_ctrl)
        self._tab_key_ctrl_active = should
        self.source_view.set_indent_on_tab(should)

    def set_auto_bullet(self, enabled):
        """Set auto bullet continuation user preference."""
        self._auto_bullet_pref = enabled
        self._apply_auto_bullet()

    def set_tab_indent_bullet(self, enabled):
        """Set Tab key indentation for bullets user preference."""
        self._tab_indent_pref = enabled
        self._apply_tab_indent_bullet()

    def _on_list_insert_text(self, buf, location, text, _length):
        """Auto-continue list item marker after pressing Enter."""
        if "\n" not in text:
            return
        line_start = location.copy()
        line_start.set_line_offset(0)
        line_text = buf.get_text(line_start, location, False)
        marker = _list_continuation_marker(line_text)
        if not marker:
            return

        def _insert():
            cur = buf.get_iter_at_mark(buf.get_insert())
            new_line_start = cur.copy()
            new_line_start.set_line_offset(0)
            already = buf.get_text(new_line_start, cur, False)
            if marker.startswith(already):
                rest = marker[len(already):]
                if rest:
                    buf.insert_at_cursor(rest)
            return False

        idle_add(_insert)

    def _on_tab_key_pressed(self, _ctrl, keyval, _keycode, state):
        """Indent the current list-item line on Tab (no selection)."""
        if keyval != Gdk.KEY_Tab:
            return False
        if state & (
            Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.SHIFT_MASK
            | Gdk.ModifierType.ALT_MASK
        ):
            return False
        buf = self.text_buffer
        if buf.get_has_selection():
            return False
        ins = buf.get_iter_at_mark(buf.get_insert())
        line_start = ins.copy()
        line_start.set_line_offset(0)
        line_end = line_start.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()
        line_text = buf.get_text(line_start, line_end, False)
        if not _is_list_line(line_text):
            return False
        self.source_view.indent_lines(line_start, line_end)
        return True

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
            timeout_add(200, self.check_in_thread)
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
                dialog.connect(
                    "response",
                    self._on_file_changed_response,
                    last_ctime,
                )
                dialog.present(self.__win)
                return  # loop restarted in _on_file_changed_response
        except OSError:
            pass  # file switching when modify by another software
        timeout_add(200, self.check_in_thread)

    def _on_file_changed_response(self, _dialog, response, last_ctime):
        """Handle response from the file-changed dialog."""
        if response == "yes":
            cursor = self.text_buffer.get_insert()
            offset = self.text_buffer.get_iter_at_mark(cursor).get_offset()
            self.read_from_file(self.__file_name, offset)
        else:
            self.__last_ctime = last_ctime
        self.__pause_period = False
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
                rename(self.__file_name, self.__file_name + "~")
            with open(self.__file_name, "w", encoding="utf-8") as src:
                src.write(self.text)
                src.flush()
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
            self._open_save_dialog(self._after_save_dialog)
        else:
            self.save_to_file()

    def save_as(self):
        """Save the file as another."""
        self._open_save_dialog(self._after_save_dialog)

    def _after_save_dialog(self, file_name):
        """Apply new file name and save."""
        if file_name:
            self.__file_name = file_name
            self.emit("file_type", self.file_ext)
            self.save_to_file()

    def _open_save_dialog(self, callback):
        """Open Gtk.FileDialog for saving and call *callback(file_name)*."""
        lang = self.text_buffer.get_language()
        filters, default_filter, suffix, filter_suffixes = build_save_filters(
            lang.get_id(),
        )
        if self.__file_name:
            folder = dirname(self.file_path)
            name, _ = splitext(self.file_name)
        else:
            folder = get_user_special_dir(UserDirectory.DIRECTORY_DOCUMENTS)
            name = "Untitled document"
        save_file_dialog(
            self.__win,
            "Save Document",
            filters,
            default_filter,
            default_suffix=suffix,
            filter_suffixes=filter_suffixes,
            initial_folder=folder,
            initial_name=name,
            callback=callback,
        )

    def do_file_type(self, ext):
        """Set file type for right syntax highlighting."""
        if ext:
            language = LANG_BY_EXT.get(ext, LANG_BY_EXT[".rst"])
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

    def get_selected_text(self) -> str:
        """Return the currently selected text, or an empty string."""
        bounds = self.text_buffer.get_selection_bounds()
        if not bounds:
            return ""
        return self.text_buffer.get_text(bounds[0], bounds[1], False)

    def get_selection_offsets(self) -> "tuple[int, int]":
        """Return ``(start, end)`` character offsets of the current selection.

        When nothing is selected both values equal the cursor offset.
        """
        bounds = self.text_buffer.get_selection_bounds()
        if bounds:
            return bounds[0].get_offset(), bounds[1].get_offset()
        cursor = self.text_buffer.get_iter_at_mark(
            self.text_buffer.get_insert(),
        )
        off = cursor.get_offset()
        return off, off

    def _replace_range(
        self,
        start_off: int,
        end_off: int,
        new_text: str,
    ) -> None:
        """Replace buffer content between offsets and select *new_text*.

        This is the single low-level primitive used by all formatting
        methods that modify a character range.  The replacement text is
        selected so the user can see what changed.

        Must be called inside ``begin_user_action / end_user_action``
        or wraps its own pair when called standalone.
        """
        buf = self.text_buffer
        start = buf.get_iter_at_offset(start_off)
        end = buf.get_iter_at_offset(end_off)
        buf.delete(start, end)
        ins = buf.get_iter_at_offset(start_off)
        buf.insert(ins, new_text)
        sel_s = buf.get_iter_at_offset(start_off)
        sel_e = buf.get_iter_at_offset(start_off + len(new_text))
        buf.select_range(sel_s, sel_e)

    def toggle_format(self, before, after, known_formats):
        """Toggle formatting markers around selected text.

        Expands the selection to cover any adjacent known formatting markers,
        strips the detected format, then applies the requested format — or
        removes it when the selection is already wrapped with it.  The
        original (inner) text remains selected after the operation.

        ``known_formats`` is a list of (before, after) tuples for the current
        file type.  Longer markers are tested first so that ``**`` is never
        mis-detected as a pair of ``*`` markers.
        """
        bounds = self.text_buffer.get_selection_bounds()
        if not bounds:
            return
        buf_text = self.text_buffer.props.text
        sel_start = bounds[0].get_offset()
        sel_end = bounds[1].get_offset()

        eff_start, eff_end, result, inner_start, inner_end = (
            compute_toggle_format(
                buf_text,
                sel_start,
                sel_end,
                before,
                after,
                known_formats,
            )
        )

        self.text_buffer.begin_user_action()
        self._replace_range(eff_start, eff_end, result)
        # Restore selection over the inner (content) text only
        sel_iter = self.text_buffer.get_iter_at_offset(
            eff_start + inner_start,
        )
        sel_end_iter = self.text_buffer.get_iter_at_offset(
            eff_start + inner_end,
        )
        self.text_buffer.select_range(sel_iter, sel_end_iter)
        self.text_buffer.end_user_action()

    def insert_link_text(
        self,
        link_text: str,
        start_off: int,
        end_off: int,
    ) -> None:
        """Insert *link_text* at the given buffer offsets and select it.

        When *start_off == end_off* (no prior selection), the text is
        inserted at that position with padding spaces added as needed.
        Otherwise the range ``[start_off, end_off)`` is replaced.

        The inserted link text is selected after the operation so the
        user can see what was inserted.
        """
        buf = self.text_buffer
        buf.begin_user_action()
        if start_off != end_off:
            self._replace_range(start_off, end_off, link_text)
        else:
            full = buf.props.text
            off = start_off
            prefix = "" if off == 0 or full[off - 1] in (" ", "\n") else " "
            suffix = (
                "" if off >= len(full) or full[off] in (" ", "\n") else " "
            )
            padded = prefix + link_text + suffix
            self._replace_range(off, off, padded)
            # Re-select only the link text (not padding)
            ins_start = off + len(prefix)
            sel_s = buf.get_iter_at_offset(ins_start)
            sel_e = buf.get_iter_at_offset(ins_start + len(link_text))
            buf.select_range(sel_s, sel_e)
        buf.end_user_action()

    # ------------------------------------------------------------------
    # Line-level formatting helpers
    # ------------------------------------------------------------------

    def _get_current_line(self):
        """Return ``(line_num, start_iter, end_iter, text)`` for cursor."""
        buf = self.text_buffer
        cursor = buf.get_iter_at_mark(buf.get_insert())
        line_num = cursor.get_line()
        start = cursor.copy()
        start.set_line_offset(0)
        end = cursor.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        return line_num, start, end, buf.get_text(start, end, True)

    def _get_line_text(self, line_num):
        """Return the text of *line_num*, or ``None`` if invalid."""
        if line_num < 0:
            return None
        buf = self.text_buffer
        _, start = buf.get_iter_at_line(line_num)
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        return buf.get_text(start, end, True)

    def _replace_line(self, line_start, line_end, old_text, new_text):
        """Replace *old_text* with *new_text* between the two iters."""
        if new_text != old_text:
            buf = self.text_buffer
            buf.begin_user_action()
            buf.delete(line_start, line_end)
            buf.insert(line_start, new_text)
            buf.end_user_action()

    # ------------------------------------------------------------------
    # Public line-level formatting methods
    # ------------------------------------------------------------------

    def toggle_line_format(
        self,
        before,
        after="",
        all_block_variants=(),
        strip_ordered=False,
    ):
        """Toggle block formatting for the line at the cursor."""
        _, start, end, text = self._get_current_line()
        new = compute_toggle_line_format(
            text,
            before,
            after,
            all_block_variants=all_block_variants,
            strip_ordered=strip_ordered,
        )
        self._replace_line(start, end, text, new)

    def toggle_line_exclusive(
        self,
        before,
        after,
        all_variants,
        extra_strip_variants=(),
        strip_ordered=False,
    ):
        """Toggle an exclusive block format on the current line."""
        _, start, end, text = self._get_current_line()
        new = compute_toggle_line_exclusive(
            text,
            before,
            after,
            all_variants,
            extra_strip_variants=extra_strip_variants,
            strip_ordered=strip_ordered,
        )
        self._replace_line(start, end, text, new)

    def toggle_rst_header(self, underline_char):
        """Toggle an RST heading underline on the current line."""
        buf = self.text_buffer
        line_num, _, line_end, line_text = self._get_current_line()

        # Next line (if any)
        next_start = line_end.copy()
        next_start.forward_char()
        next_line_text = None
        next_line_end = None
        if next_start.get_line() > line_num:
            next_line_end = next_start.copy()
            if not next_line_end.ends_line():
                next_line_end.forward_to_line_end()
            next_line_text = buf.get_text(
                next_start,
                next_line_end,
                True,
            )

        new_underline, had_underline = compute_toggle_rst_header(
            line_text,
            next_line_text,
            underline_char,
        )

        if new_underline is None and not had_underline:
            return

        buf.begin_user_action()

        if had_underline and next_line_end is not None:
            buf.delete(line_end, next_line_end)

        if new_underline is not None:
            _, cur_end = buf.get_iter_at_line(line_num)
            if not cur_end.ends_line():
                cur_end.forward_to_line_end()
            buf.insert(cur_end, "\n" + new_underline)

        buf.end_user_action()

    def _toggle_list_item(self, compute_fn, needs_blank, **kwargs):
        """Shared implementation for bullet and ordered list toggle.

        Calls *compute_fn* with the current and (optionally) previous
        line texts plus any extra *kwargs*.  Handles blank-line
        insertion and line replacement.
        """
        buf = self.text_buffer
        line_num, line_start, line_end, line_text = self._get_current_line()

        prev = self._get_line_text(line_num - 1) if needs_blank else None

        new_text, insert_blank = compute_fn(
            line_text,
            prev,
            **kwargs,
        )

        if new_text == line_text and not insert_blank:
            return

        buf.begin_user_action()

        if insert_blank:
            buf.insert(line_start, "\n")
            _, line_start = buf.get_iter_at_line(line_num + 1)
            line_end = line_start.copy()
            if not line_end.ends_line():
                line_end.forward_to_line_end()

        if new_text != line_text:
            buf.delete(line_start, line_end)
            buf.insert(line_start, new_text)

        buf.end_user_action()

    def toggle_bullet(
        self,
        before,
        after,
        all_block_variants,
        needs_blank,
        strip_ordered=False,
    ):
        """Toggle bullet-list formatting on the current line."""
        self._toggle_list_item(
            compute_toggle_bullet,
            needs_blank,
            before=before,
            after=after,
            all_block_variants=all_block_variants,
            strip_ordered=strip_ordered,
        )

    def toggle_ordered(
        self,
        all_block_variants,
        needs_blank,
        auto_number=False,
    ):
        """Toggle ordered (numbered) list on the current line."""
        self._toggle_list_item(
            compute_toggle_ordered,
            needs_blank,
            all_block_variants=all_block_variants,
            auto_number=auto_number,
        )

    def stop_search(self):
        """Stop searching."""
        self.search_settings.set_search_text(None)
