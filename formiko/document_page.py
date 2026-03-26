"""Per-tab document widget bundling editor, renderer and associated state."""

import os
import re
import threading
from os import stat
from os.path import basename, dirname, splitext
from traceback import print_exc

from gi import get_required_version
from gi.repository import Gdk, GLib, GObject, Gtk

from formiko.editor import EditorType
from formiko.editor_actions import EditorActionGroup
from formiko.formatting_actions import FormattingActionGroup
from formiko.renderer import EXTS, Renderer
from formiko.sourceview import SourceView
from formiko.user import UserPreferences, View
from formiko.widgets import ImutableDict

# Debug stubs: set env vars before launching to replace heavy widgets.
#   FORMIKO_STUB_EDITOR=1   → plain GtkTextView instead of GtkSource.View
#   FORMIKO_STUB_RENDERER=1 → Gtk.DrawingArea instead of WebKitWebView
_STUB_EDITOR = bool(os.environ.get("FORMIKO_STUB_EDITOR"))
_STUB_RENDERER = bool(os.environ.get("FORMIKO_STUB_RENDERER"))

if get_required_version("Vte"):
    from formiko.vim import VimEditor

RE_WORD = re.compile(r"([\w]+)", re.U)
RE_CHAR = re.compile(r'[\w \t\.,\?\(\)"\']', re.U)


class DocumentPage(Gtk.Box):
    """Per-tab widget: editor + renderer + per-file state."""

    __gsignals__ = ImutableDict({
        # Emitted when file name/path or modified state changes.
        "doc-state-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # Emitted after each render cycle with updated word/char counts.
        "words-count-changed": (
            GObject.SignalFlags.RUN_FIRST, None, (int, int),
        ),
    })

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

    def _create_renderer(self):
        win_prefs = self._window.preferences
        if _STUB_RENDERER:
            from formiko.debug_stubs import StubRenderer  # noqa: PLC0415
            self.renderer = StubRenderer(self._window)
        else:
            self.renderer = Renderer(
                self._window,
                parser=self.preferences.parser,
                writer=win_prefs.writer,
            )
        self.renderer.set_vexpand(True)
        self.renderer.set_hexpand(True)
        if not _STUB_RENDERER and win_prefs.custom_style and win_prefs.style:
            self.renderer.set_style(win_prefs.style)
        self.renderer.set_tab_width(self.preferences.editor.tab_width)

    def _create_editor_layout(self, file_name):
        ext = splitext(file_name)[1] if file_name else ""
        initial_parser = EXTS.get(ext, self.preferences.parser)
        self.preferences.parser = initial_parser
        self.renderer.set_parser(initial_parser)

        if self.editor_type == EditorType.VIM:
            self.editor = VimEditor(self._window, file_name)
        elif _STUB_EDITOR:
            from formiko.debug_stubs import (  # noqa: PLC0415
                StubEditor,
                StubEditorGSV,
                StubEditorGSVFull,
                StubEditorGSVGutter,
                StubEditorGSVLang,
                StubEditorGSVLangAI,
                StubEditorGSVLangHCL,
                StubEditorGSVLangNoHL,
                StubEditorGSVLangTW,
                StubEditorGSVLangAIAfter,
                StubEditorGSVLangCSS,
                StubEditorGSVRealOrder,
                StubEditorGSVRealOrderColor,
            )
            _stub_map = {
                "1": StubEditor, "tv": StubEditor,
                "gsv": StubEditorGSV,
                "gsv_lang": StubEditorGSVLang,
                "gsv_gutter": StubEditorGSVGutter,
                "gsv_full": StubEditorGSVFull,
                # granular: which gsv_full setting prevents typing-freeze?
                "gsv_lang_hcl":  StubEditorGSVLangHCL,   # + highlight_current_line
                "gsv_lang_ai":   StubEditorGSVLangAI,    # + auto_indent (BEFORE set_child)
                "gsv_lang_tw":   StubEditorGSVLangTW,    # + tab_width=4 (BEFORE set_child)
                "gsv_lang_nohl": StubEditorGSVLangNoHL,  # lang set, syntax OFF
                # order-of-operations tests
                "gsv_lang_ai_after": StubEditorGSVLangAIAfter,  # auto_indent AFTER set_child
                "gsv_lang_css":      StubEditorGSVLangCSS,      # CSS font before set_child
                "gsv_real_order":    StubEditorGSVRealOrder,    # CSS before + props after (like real)
                "gsv_real_color":    StubEditorGSVRealOrderColor,  # + color scheme after set_child
            }
            cls = _stub_map.get(_STUB_EDITOR, StubEditor)
            self.editor = cls(self._window, self.preferences)
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

        if self.editor_type == EditorType.SOURCE and not _STUB_EDITOR:
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
        if self.editor_type == EditorType.SOURCE:
            self.editor.text_buffer.connect(
                "modified-changed", self._on_modified_changed,
            )

        if file_name:
            self.editor.read_from_file(file_name)

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

        view = self._window.cache.view
        if view == View.EDITOR:
            self.renderer.set_visible(False)
        elif view == View.PREVIEW:
            self.editor.set_visible(False)

        self.append(self.paned)
        self.connect("realize", self._on_realize)

    def _on_realize(self, _widget):
        """Workaround for a GTK4 allocation bug causing the editor to freeze.

        When GtkTextView is nested inside AdwTabView's AdwBin, lazy text
        validation (flush_first_validate) triggers queue_resize() during
        a LAYOUT phase.  On an even-numbered LAYOUT iteration,
        gtk_widget_ensure_allocate_on_children() leaves AdwBin.alloc_needed
        =TRUE without scheduling a new LAYOUT phase.  Subsequent PAINT
        frames then skip AdwBin — keystrokes are written to the buffer but
        not rendered until the mouse crosses into the WebKit preview panel.

        Two-part fix:
        1. buffer "changed" → request_phase(LAYOUT): ensures the frame
           clock runs a LAYOUT phase after each keystroke so the allocation
           path is re-entered.
        2. frame-clock "layout" → allocate(AdwBin) on 4th iteration only:
           the 4th iteration is always the freeze-causing even iteration where
           alloc_needed=TRUE and resize_queued=TRUE.  A direct allocate() call
           here uses the size_allocate ELSE branch; the gated resize_queued
           prevents re-triggering; line 4356 clears alloc_needed=FALSE so the
           following PAINT is not blocked.
        """
        if not hasattr(self, "editor"):
            return
        if not hasattr(self.editor, "text_buffer"):
            return
        self.editor.text_buffer.connect(
            "changed", self._on_buf_changed_request_layout,
        )
        clock = self.get_frame_clock()
        if clock is not None:
            self._fix_layout_frame = -1
            self._fix_layout_iter = 0
            clock.connect("layout", self._on_frame_layout_alloc_fix)

    def _on_buf_changed_request_layout(self, _buf):
        """Schedule LAYOUT so the layout handler can clear alloc_needed."""
        clock = self.get_frame_clock()
        if clock is not None:
            clock.request_phase(Gdk.FrameClockPhase.LAYOUT)

    def _on_frame_layout_alloc_fix(self, clock):
        """Clear AdwBin.alloc_needed left by ensure_allocate_on_children.

        Root cause: GTK's LAYOUT while-loop runs up to 4 iterations. On even
        iterations, gtk_widget_ensure_allocate_on_children() is called on AdwBin
        (alloc_needed=FALSE but alloc_needed_on_child=TRUE). Inside, the child
        allocation triggers flush_first_validate() → queue_resize(AdwBin).
        Because ensure_allocate() already cleared resize_queued=FALSE (line
        11013 of gtkwidget.c), the gate at queue_resize() fails, so
        alloc_needed=TRUE is set without being cleared by the ELSE branch's
        line 4356.  After 4 iterations the while-loop exits with
        alloc_needed=TRUE on AdwBin → PAINT is skipped → visual freeze.

        Fix: apply allocate() ONLY on the 4th "layout" signal emission of each
        frame (the freeze-causing even iteration).  At that point the freeze
        state guarantees alloc_needed=TRUE and resize_queued=TRUE on AdwBin.
        With alloc_needed=TRUE the full size_allocate ELSE branch runs; with
        resize_queued=TRUE the inner queue_resize(AdwBin) is gated → line 4356
        sets alloc_needed=FALSE → PAINT succeeds.
        Skipping iterations 1-3 avoids calling allocate() when alloc_needed is
        already FALSE (which would enter ensure_allocate_on_children and re-
        trigger the bug) and prevents spurious "layout continuously requested"
        warnings.
        """
        frame = clock.get_frame_counter()
        if frame != self._fix_layout_frame:
            self._fix_layout_frame = frame
            self._fix_layout_iter = 0
        self._fix_layout_iter += 1
        if self._fix_layout_iter < 4:
            return
        parent = self.get_parent()  # AdwBin
        if parent is None:
            return
        alloc = parent.get_allocation()
        if alloc.width > 0 and alloc.height > 0:
            parent.allocate(alloc.width, alloc.height, -1, None)

    def load_file(self, file_name):
        """Load *file_name* into this empty, unmodified tab."""
        self.editor.read_from_file(file_name)
        self._last_changes = self.editor.changes
        # read_from_file emits 'file-type' synchronously (before set_text),
        # which triggers set_parser → idle_add(do_render) with the new parser.
        # That pending idle is the one render we want.  Set renderer.src
        # directly here so the idle finds the correct content when it runs,
        # without queuing a second do_render via renderer.render().
        text = self.editor.text
        self.renderer.src = text
        self.renderer.file_name = self.editor.file_path
        self.renderer.pos = self.editor.position
        self._words_count = sum(1 for _ in RE_WORD.finditer(text))
        self._chars_count = sum(1 for _ in RE_CHAR.finditer(text))

    def refresh(self):
        """Force an immediate re-render."""
        self._check_in_thread(True)

    def _on_file_type(self, _widget, ext):
        parser = EXTS.get(ext, self.preferences.parser)
        self.preferences.parser = parser
        self.renderer.set_parser(parser)
        if self.editor_type == EditorType.SOURCE and hasattr(self, "fmt_actions"):
            self.fmt_actions.set_parser(parser)
            self.editor.change_mime_type(parser)
            self.editor.set_list_features_enabled(
                parser in ("rst", "md", "m2r"),
            )
        if hasattr(self._window, "file_browser") and self.file_path:
            directory = dirname(self.file_path)
            if directory:
                self._window.file_browser.set_directory(directory)
        self._window.on_active_tab_parser_changed(self, parser)
        self.emit("doc-state-changed")

    def _on_modified_changed(self, _buf):
        self.emit("doc-state-changed")

    def _on_scroll_changed(self, _widget, position):
        if self._window.preferences.auto_scroll:
            self.renderer.scroll_to_position(position)

    @property
    def words_count(self):
        """Word count, updated each render cycle."""
        return self._words_count

    @property
    def chars_count(self):
        """Character count, updated each render cycle."""
        return self._chars_count

    @property
    def file_path(self):
        """Opened file path, or the preview file path."""
        if self.editor_type != EditorType.PREVIEW:
            return self.editor.file_path
        return self._preview_file

    @property
    def file_name(self):
        """Basename of the opened file."""
        if self.editor_type != EditorType.PREVIEW:
            return self.editor.file_name
        return basename(self._preview_file) if self._preview_file else ""

    @property
    def is_modified(self):
        """True when the document has unsaved changes."""
        if self.editor_type != EditorType.PREVIEW:
            return self.editor.is_modified
        return False

    @property
    def parser(self):
        """Current parser name."""
        return self.preferences.parser

    def _check_in_thread(self, force=False):
        """Periodic refresh dispatcher."""
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
                self.emit(
                    "words-count-changed",
                    self._words_count,
                    self._chars_count,
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
                GLib.idle_add(self.emit, "doc-state-changed")
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
        """Stop the refresh loop."""
        self.running = False
