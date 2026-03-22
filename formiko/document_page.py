"""Per-tab document widget bundling editor, renderer and associated state."""

import re
import threading
from os import stat
from os.path import basename, dirname, splitext
from traceback import print_exc

from gi import get_required_version
from gi.repository import GLib, Gtk

from formiko.editor import EditorType
from formiko.editor_actions import EditorActionGroup
from formiko.formatting_actions import FormattingActionGroup
from formiko.renderer import EXTS, Renderer
from formiko.sourceview import SourceView
from formiko.user import UserPreferences, View

if get_required_version("Vte"):
    from formiko.vim import VimEditor

RE_WORD = re.compile(r"([\w]+)", re.U)
RE_CHAR = re.compile(r'[\w \t\.,\?\(\)"\']', re.U)


class DocumentPage(Gtk.Box):
    """Per-tab widget containing editor, renderer and per-file state.

    One instance is created for each open tab.  Global (per-window) settings
    such as writer, style and view mode are read from *window.preferences* at
    creation time; only *parser* is stored per-tab.
    """

    def __init__(self, window, editor_type: EditorType, file_name=""):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            vexpand=True,
            hexpand=True,
        )
        self._window = window
        self.editor_type = editor_type
        # Per-tab preferences - we only track parser here; the rest is global.
        self.preferences = UserPreferences()
        self._last_changes = 0
        self._vim_title = ""
        self.running = True
        self._words_count = 0
        self._chars_count = 0

        self._create_renderer()

        if editor_type != EditorType.PREVIEW:
            self._create_editor_layout(file_name)
        else:
            self.paned = None
            self._preview_file = file_name
            ext = splitext(file_name)[1] if file_name else ""
            parser = EXTS.get(ext, self.preferences.parser)
            self.preferences.parser = parser
            self.renderer.set_parser(parser)
            self.append(self.renderer)

        GLib.timeout_add(200, self._check_in_thread)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _create_renderer(self):
        """Create a Renderer instance using global window writer/style."""
        win_prefs = self._window.preferences
        self.renderer = Renderer(
            self._window,
            parser=self.preferences.parser,
            writer=win_prefs.writer,
        )
        self.renderer.set_vexpand(True)
        self.renderer.set_hexpand(True)
        if win_prefs.custom_style and win_prefs.style:
            self.renderer.set_style(win_prefs.style)
        self.renderer.set_tab_width(self.preferences.editor.tab_width)

    def _create_editor_layout(self, file_name):
        """Create editor, action groups and paned layout."""
        ext = splitext(file_name)[1] if file_name else ""
        initial_parser = EXTS.get(ext, self.preferences.parser)
        self.preferences.parser = initial_parser
        self.renderer.set_parser(initial_parser)

        # Editor widget
        if self.editor_type == EditorType.VIM:
            self.editor = VimEditor(self._window, file_name)
        else:
            self.editor = SourceView(
                self._window,
                self.preferences,
                "editor.spell-lang",
            )
            self.editor_actions = EditorActionGroup(
                self.editor,
                self.renderer,
                self.preferences,
            )

        if self.editor_type == EditorType.SOURCE:
            self.fmt_actions = FormattingActionGroup(
                self.editor,
                self.renderer,
                initial_parser,
                self.preferences,
            )
            self.editor.set_list_features_enabled(
                initial_parser in ("rst", "md", "m2r"),
            )

        self.editor.connect("file-type", self._on_file_type)
        self.editor.connect("scroll-changed", self._on_scroll_changed)

        if file_name:
            self.editor.read_from_file(file_name)

        # Paned layout
        win_cache = self._window.cache
        self.paned = Gtk.Paned(
            orientation=self._window.preferences.preview,
            position=win_cache.paned,
            vexpand=True,
            hexpand=True,
        )
        self.paned.set_start_child(self.editor)
        self.paned.set_resize_start_child(True)
        self.paned.set_shrink_start_child(False)
        self.paned.set_end_child(self.renderer)
        self.paned.set_resize_end_child(True)
        self.paned.set_shrink_end_child(False)

        # Apply current global view mode
        view = self._window.cache.view
        if view == View.EDITOR:
            self.renderer.set_visible(False)
        elif view == View.PREVIEW:
            self.editor.set_visible(False)

        self.append(self.paned)

    def load_file(self, file_name):
        """Load *file_name* into this (empty, unmodified) document tab.

        Reads the file into the editor; parser and UI are updated via the
        'file-type' signal that :meth:`editor.read_from_file` emits.
        After loading, the renderer is refreshed directly — no need to wait
        for the periodic refresh loop.
        Only valid for non-PREVIEW tabs.
        """
        self.editor.read_from_file(file_name)
        # Render immediately with the loaded content instead of waiting for
        # the periodic check_in_thread loop (avoids multi-level idle chaining).
        self._last_changes = self.editor.changes
        self.renderer.render(
            self.editor.text,
            self.editor.file_path,
            self.editor.position,
        )

    def refresh(self):
        """Force an immediate re-render of this tab's content."""
        self._check_in_thread(True)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_file_type(self, _widget, ext):
        """Handle 'file-type' signal from the editor."""
        parser = EXTS.get(ext, self.preferences.parser)
        self.preferences.parser = parser
        self.renderer.set_parser(parser)
        if self.editor_type == EditorType.SOURCE:
            self.fmt_actions.set_parser(parser)
            self.editor.change_mime_type(parser)
            self.editor.set_list_features_enabled(
                parser in ("rst", "md", "m2r"),
            )
        # Update file browser in the parent window
        if hasattr(self._window, "file_browser") and self.file_path:
            directory = dirname(self.file_path)
            if directory:
                self._window.file_browser.set_directory(directory)
        # Update window-level UI if we are the active tab
        self._window.on_active_tab_parser_changed(self, parser)

    def _on_scroll_changed(self, _widget, position):
        """Handle 'scroll-changed' signal for auto-scroll sync."""
        if self._window.preferences.auto_scroll:
            self.renderer.scroll_to_position(position)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def words_count(self):
        """Return current word count (updated by refresh loop)."""
        return self._words_count

    @property
    def chars_count(self):
        """Return current character count (updated by refresh loop)."""
        return self._chars_count

    @property
    def file_path(self):
        """Return the opened file path."""
        if self.editor_type != EditorType.PREVIEW:
            return self.editor.file_path
        return self._preview_file

    @property
    def file_name(self):
        """Return the opened file name (basename)."""
        if self.editor_type != EditorType.PREVIEW:
            return self.editor.file_name
        return basename(self._preview_file) if self._preview_file else ""

    @property
    def is_modified(self):
        """Return True when the document has unsaved changes."""
        if self.editor_type != EditorType.PREVIEW:
            return self.editor.is_modified
        return False

    @property
    def parser(self):
        """Return the current parser name."""
        return self.preferences.parser

    # ------------------------------------------------------------------
    # Refresh loop
    # ------------------------------------------------------------------

    def _check_in_thread(self, force=False):
        """Periodic refresh dispatcher for this tab."""
        if not self.running:
            return False
        if self.editor_type == EditorType.VIM:
            threading.Thread(
                target=self._refresh_from_vim,
                args=(force,),
                daemon=True,
            ).start()
        elif self.editor_type == EditorType.SOURCE:
            GLib.idle_add(self._refresh_from_source, force)
        else:
            GLib.idle_add(self._refresh_from_file, force)
        return False

    def _refresh_from_source(self, force=False):
        """Refresh the renderer from the SourceView buffer."""
        try:
            last_changes = self.editor.changes
            if force or last_changes > self._last_changes:
                self._last_changes = last_changes
                text = self.editor.text
                self._words_count = sum(1 for _ in RE_WORD.finditer(text))
                self._chars_count = sum(1 for _ in RE_CHAR.finditer(text))
                self.renderer.render(
                    text,
                    self.editor.file_path,
                    self.editor.position,
                )
            GLib.timeout_add(100, self._check_in_thread)
        except BaseException:  # pylint: disable=broad-exception-caught
            print_exc()

    def _refresh_from_vim(self, force=False):
        """Refresh the renderer from the Vim buffer (background thread)."""
        another_file = False
        try:
            file_name = self.editor.file_name
            file_path = self.editor.file_path
            if not self.running:
                return
            if file_name != self._vim_title:
                self._vim_title = file_name
                another_file = True
            if not self.running:
                return
            last_changes = self.editor.get_vim_changes()
            if force or last_changes > self._last_changes or another_file:
                self._last_changes = last_changes
                if not self.running:
                    return
                lines = self.editor.get_vim_lines()
                if not self.running:
                    return
                buff = self.editor.get_vim_get_buffer(lines)
                if not self.running:
                    return
                pos = self.editor.get_vim_scroll_pos(lines)
                self.renderer.render(buff, file_path, pos)
            GLib.timeout_add(100, self._check_in_thread)
        except BaseException:  # pylint: disable=broad-exception-caught
            print_exc()

    def _refresh_from_file(self, force=False):
        """Refresh the renderer from disk (PREVIEW mode)."""
        try:
            last_changes = stat(self._preview_file).st_ctime
            if force or last_changes > self._last_changes:
                self._last_changes = last_changes
                with open(self._preview_file, encoding="utf-8") as src:
                    buff = src.read()
                    self.renderer.render(
                        buff,
                        self._preview_file,
                        self.renderer.position,
                    )
        except BaseException:  # pylint: disable=broad-exception-caught
            print_exc()
        GLib.timeout_add(500, self._check_in_thread)

    def stop(self):
        """Stop the refresh loop for this tab."""
        self.running = False
