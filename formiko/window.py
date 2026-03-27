"""Gtk.ApplicationWindow implementation."""

from enum import Enum
from os.path import basename, dirname, expanduser, splitext

from gi.repository import Adw, Gio, GLib, Gtk, Pango

from formiko.dialogs import (
    UnsavedChangesDialog,
    build_export_filters,
    build_open_filters,
    open_file_dialog,
    run_alert_dialog,
    save_file_dialog,
)
from formiko.document_page import DocumentPage
from formiko.editor import EditorType
from formiko.filebrowser import FileBrowser
from formiko.formatting_actions import FormattingActionGroup
from formiko.menu import AppMenu
from formiko.preferences import Preferences
from formiko.renderer import WebView as GtkWebView
from formiko.sourceview import View as GtkSourceView
from formiko.status_menu import Statusbar
from formiko.user import UserCache, UserPreferences, View
from formiko.widgets import IconButton, connect_accel_tooltip

NOT_SAVED_NAME = "Untitled Document"


class SearchWay(Enum):
    """Direction for search navigation."""

    NEXT = 0
    PREVIOUS = 1


class TabLabel(Gtk.Box):
    """Tab label widget with title and close button for Gtk.Notebook."""

    def __init__(self, title, on_close):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._label = Gtk.Label(label=title)
        self._label.set_hexpand(True)
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._label.set_width_chars(8)
        self._label.set_max_width_chars(30)
        close_btn = Gtk.Button()
        close_btn.set_icon_name("window-close-symbolic")
        close_btn.add_css_class("flat")
        close_btn.add_css_class("circular")
        close_btn.set_focus_on_click(False)
        close_btn.connect("clicked", on_close)
        self.append(self._label)
        self.append(close_btn)

    def set_title(self, title):
        """Update the displayed tab title."""
        self._label.set_label(title)

    def set_needs_attention(self, needs):
        """Highlight label when the document has unsaved changes."""
        if needs:
            self._label.add_css_class("accent")
        else:
            self._label.remove_css_class("accent")


class AppWindow(Adw.ApplicationWindow):
    """Main application window with tabbed editor interface."""

    # pylint: disable = too-many-public-methods
    # pylint: disable = too-many-instance-attributes
    # pylint: disable = unused-argument

    def __init__(
        self,
        editor_type: EditorType,
        file_name="",
        no_initial_tab=False,
    ):
        """:param EditorType editor_type: SOURCE, VIM or PREVIEW.

        :param str file_name: Path to open on startup.
        :param bool no_initial_tab: Skip initial tab (drag-receive windows).
        """
        self.runing = True
        self.editor_type = editor_type
        self.focused = None
        self.search_way = SearchWay.NEXT
        self.cache = UserCache()
        self.preferences = UserPreferences()
        self._action_groups = {}
        self._tabs_needing_paned_reset: set = set()
        self._last_active_doc = None
        self._tab_labels: dict = {}
        super().__init__()
        self._setup_actions()
        self.set_default_icon_name("formiko")
        self._setup_layout(file_name, no_initial_tab)
        self.connect("close-request", self._on_close_request)

    def insert_action_group(self, prefix, group):
        """Override to track inserted action groups for get_action_group()."""
        self._action_groups[prefix] = group
        super().insert_action_group(prefix, group)

    def get_action_group(self, prefix):
        """Return action group by prefix (GTK4 replacement for removed API)."""
        if prefix == "win":
            return self
        if prefix == "app":
            return self.get_application()
        return self._action_groups.get(prefix)

    def _setup_actions(self):
        self._register_document_actions()
        self._register_search_actions()
        self._register_view_actions()
        self._register_renderer_actions()
        self._register_json_actions()

    def _register_document_actions(self):
        action = Gio.SimpleAction.new("new-tab", None)
        action.connect("activate", self._on_new_tab)
        self.add_action(action)

        action = Gio.SimpleAction.new("open-document", None)
        action.connect("activate", self.on_open_document)
        self.add_action(action)

        action = Gio.SimpleAction.new("save-document", None)
        action.connect("activate", self._on_save_document)
        action.set_enabled(False)
        self.add_action(action)

        action = Gio.SimpleAction.new("save-document-as", None)
        action.connect("activate", self._on_save_document_as)
        action.set_enabled(self.editor_type == EditorType.SOURCE)
        self.add_action(action)

        action = Gio.SimpleAction.new("export-document-as", None)
        action.connect("activate", self._on_export_document_as)
        action.set_enabled(self.editor_type != EditorType.PREVIEW)
        self.add_action(action)

        action = Gio.SimpleAction.new("print-document", None)
        action.connect("activate", self._on_print_document)
        self.add_action(action)

        action = Gio.SimpleAction.new("close-window", None)
        action.connect("activate", self._on_close_window)
        self.add_action(action)

        action = Gio.SimpleAction.new("next-tab", None)
        action.connect("activate", self._on_next_tab)
        self.add_action(action)

        action = Gio.SimpleAction.new("prev-tab", None)
        action.connect("activate", self._on_prev_tab)
        self.add_action(action)

    def _register_search_actions(self):
        action = Gio.SimpleAction.new("find-in-document", None)
        action.connect("activate", self._on_find_in_document)
        self.add_action(action)

        action = Gio.SimpleAction.new("find-next-match", None)
        action.connect("activate", self._on_find_next_match)
        self.add_action(action)

        action = Gio.SimpleAction.new("find-previous-match", None)
        action.connect("activate", self._on_find_previous_match)
        self.add_action(action)

    def _register_view_actions(self):
        self.refresh_preview_action = Gio.SimpleAction.new(
            "refresh-preview",
            None,
        )
        self.refresh_preview_action.connect(
            "activate",
            self._on_refresh_preview,
        )
        self.add_action(self.refresh_preview_action)

        self._create_stateful_action(
            "switch-view-toggle",
            "q",
            self.cache.view,
            self._on_switch_view_toggle,
        )
        for name, view in (
            ("show-editor", View.EDITOR),
            ("show-preview", View.PREVIEW),
            ("show-both", View.BOTH),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect(
                "activate",
                lambda _a, _p, v=view: self.change_action_state(
                    "switch-view-toggle",
                    GLib.Variant("q", v),
                ),
            )
            self.add_action(action)

        self._create_stateful_action(
            "change-preview",
            "q",
            self.preferences.preview,
            self._on_change_preview,
        )
        self._create_toggle_action(
            "auto-scroll-toggle",
            self.preferences.auto_scroll,
            self._on_auto_scroll_toggle,
        )
        if self.editor_type != EditorType.PREVIEW:
            self._create_toggle_action(
                "toggle-sidebar",
                False,
                self._on_toggle_sidebar,
            )

    def _register_renderer_actions(self):
        pref = self.preferences
        self._create_stateful_action(
            "change-writer",
            "s",
            pref.writer,
            self._on_change_writer,
        )
        self._create_stateful_action(
            "change-parser",
            "s",
            pref.parser,
            self._on_change_parser,
        )
        self._create_toggle_action(
            "custom-style-toggle",
            pref.custom_style,
            self._on_custom_style_toggle,
        )
        self._create_stateful_action(
            "change-style",
            "s",
            pref.style,
            self._on_change_style,
        )

    def _register_json_actions(self):
        action = Gio.SimpleAction.new("json-expand-all", None)
        action.connect(
            "activate",
            lambda *_: self.active_page
            and self.active_page.renderer.json_expand_all(),
        )
        self.add_action(action)

        action = Gio.SimpleAction.new("json-collapse-all", None)
        action.connect(
            "activate",
            lambda *_: self.active_page
            and self.active_page.renderer.json_collapse_all(),
        )
        self.add_action(action)

    def _create_stateful_action(self, name, _type, default_value, method):
        """Create a stateful GSimpleAction with the given variant type."""
        action = Gio.SimpleAction.new_stateful(
            name,
            GLib.VariantType.new(_type),
            GLib.Variant(_type, default_value),
        )
        action.connect("activate", method)
        self.add_action(action)

    def _create_toggle_action(self, name, default_value, method):
        action = Gio.SimpleAction.new_stateful(
            name,
            None,
            GLib.Variant("b", default_value),
        )
        action.connect("activate", method)
        self.add_action(action)

    def _on_close_window(self, action, *params):
        """'close-window' action handler: close active tab or whole window."""
        if self.notebook.get_n_pages() > 1:
            n = self.notebook.get_current_page()
            if n >= 0:
                doc = self.notebook.get_nth_page(n)
                self._request_close_doc(doc)
        elif self.ask_if_modified():
            self.save_win_state()
            self.destroy()

    def open_document(self, file_path):
        """Open *file_path* in an existing tab or create a new one."""
        for window in self.get_application().get_windows():
            if not isinstance(window, AppWindow):
                continue
            if not window.notebook:
                continue
            for doc in window.iter_doc_pages():
                if file_path == doc.file_path:
                    window.present()
                    window.notebook.set_current_page(
                        window.notebook.page_num(doc),
                    )
                    return

        self.new_tab(file_path)

    def on_open_document(self, actions, *params):
        """Open the file-chooser dialog."""
        filters, default_filter = build_open_filters()
        open_file_dialog(
            self,
            "Open Document",
            filters,
            default_filter,
            callback=self.open_document,
        )

    def _on_save_document(self, action, *params):
        page = self.active_page
        if page and page.editor_type == EditorType.SOURCE:
            page.editor.save()

    def _on_save_document_as(self, action, *params):
        page = self.active_page
        if page and page.editor_type == EditorType.SOURCE:
            page.editor.save_as()

    def _on_export_document_as(self, action, *params):
        """'export-document-as' action handler."""
        page = self.active_page
        if not page:
            return
        file_name = (
            page.editor.file_name
            if page.editor_type != EditorType.PREVIEW
            else None
        )
        renderer = page.renderer
        filters, default_filter, suffix, filter_suffixes = (
            build_export_filters(renderer.get_parser())
        )
        name, _ = splitext(file_name) if file_name else (None, None)
        save_file_dialog(
            self,
            "Export Document As",
            filters,
            default_filter,
            default_suffix=suffix,
            filter_suffixes=filter_suffixes,
            initial_folder=dirname(name) or GLib.get_home_dir()
            if name
            else GLib.get_home_dir(),
            initial_name=basename(name) if name else None,
            callback=lambda fn: self._write_export(renderer, fn),
        )

    def _write_export(self, renderer, file_name):
        """Write rendered output to *file_name*."""
        with open(file_name, "w+", encoding="utf-8") as output:
            output.write(renderer.render_output()[1].strip())

    def _on_print_document(self, action, *params):
        page = self.active_page
        if page:
            page.renderer.print_page()

    def _on_close_request(self, *args):
        """'close-request' handler (GTK4 replacement for delete-event)."""
        rv = self.ask_if_modified()
        if rv:
            self.save_win_state()
        return not rv  # True = prevent close

    def _on_switch_view_toggle(self, action, param):
        """'switch-view-toggle' action handler."""
        if action.get_state() != param:
            action.set_state(param)

        state = param.get_uint16()
        self.cache.view = state
        for doc in self._iter_doc_pages():
            if doc.editor_type == EditorType.PREVIEW:
                continue
            if state == View.BOTH:
                doc.editor.set_visible(True)
                doc.renderer.set_visible(True)
            elif state == View.EDITOR:
                doc.editor.set_visible(True)
                doc.renderer.set_visible(False)
            else:
                doc.editor.set_visible(False)
                doc.renderer.set_visible(True)

        refresh_enabled = state != View.EDITOR
        self.refresh_preview_action.set_enabled(refresh_enabled)
        if state == View.BOTH:
            self.both_toggle_btn.set_active(True)
        elif state == View.EDITOR:
            self.editor_toggle_btn.set_active(True)
        else:
            self.preview_toggle_btn.set_active(True)

    def _on_change_preview(self, action, param):
        """'change-preview' action handler."""
        if action.get_state() != param:
            action.set_state(param)

        orientation = param.get_uint16()
        if self.preferences.preview == orientation:
            return
        self.preferences.preview = orientation
        self.preferences.save()
        for doc in self._iter_doc_pages():
            if doc.paned:
                doc.paned.set_orientation(orientation)
                self._tabs_needing_paned_reset.add(doc)
        # Workaround for https://gitlab.gnome.org/GNOME/gtk/issues/1959 -
        # set_orientation() calls queue_resize(), which schedules a layout
        # pass via the GDK frame clock (next vsync, ~16 ms at 60 Hz).
        # idle_add fires before that frame clock tick, so get_width() would
        # still return the old size; the 20 ms timeout waits past one frame.
        GLib.idle_add(
            lambda: GLib.timeout_add(
                20, self._reset_active_paned,
            ) and False,
        )

    def _paned_half(self, paned):
        """Return the position for a 50/50 split of *paned*."""
        if paned.get_orientation() == Gtk.Orientation.VERTICAL:
            return paned.get_height() // 2
        return paned.get_width() // 2

    def _reset_active_paned(self):
        """Set the active tab's paned to 50/50 after orientation change."""
        doc = self.active_page
        if doc and doc.paned:
            paned = doc.paned
            half = self._paned_half(paned)
            if half > 0:
                paned.set_position(half)
                self._tabs_needing_paned_reset.discard(doc)
        return False

    def _on_auto_scroll_toggle(self, action, param):
        """'auto-schroll-toggle' action handler."""
        auto_scroll = not action.get_state().get_boolean()
        action.set_state(GLib.Variant("b", auto_scroll))
        self.preferences.auto_scroll = auto_scroll
        self.preferences.save()

    def _on_change_parser(self, action, param):
        """'change-parser' action handler (applies to active tab)."""
        parser = param.get_string()

        if action.get_state() != param:
            action.set_state(param)

        page = self.active_page
        if not page:
            return

        page.preferences.parser = parser
        page.renderer.set_parser(parser)
        if page.editor_type == EditorType.SOURCE:
            page.fmt_actions.set_parser(parser)
            page.editor.change_mime_type(parser)
            page.editor.set_list_features_enabled(
                parser in ("rst", "md", "m2r"),
            )

        # Save as global default for new tabs
        self.preferences.parser = parser
        self.preferences.save()

        self._apply_parser_ui(parser)

    def on_active_tab_parser_changed(self, doc, parser):
        """Update window UI when the active tab's parser changes."""
        if self.active_page is not doc:
            return
        action = self.lookup_action("change-parser")
        if action:
            action.set_state(GLib.Variant("s", parser))
        self._apply_parser_ui(parser)

    def _apply_parser_ui(self, parser):
        """Update header-bar visibility for JSON vs markup parsers."""
        self.json_box.set_visible(parser == "json")
        self.json_fold_box.set_visible(parser == "json")
        if self.editor_type == EditorType.SOURCE:
            self.fmt_bar.set_visible(parser != "json")

    def _on_browser_file_activated(self, _browser, file_path):
        """Open a file selected in the file browser."""
        self.open_document(file_path)
        action = self.lookup_action("toggle-sidebar")
        if action and action.get_state().get_boolean():
            action.activate(None)

    def _on_toggle_sidebar(self, action, *_):
        """'toggle-sidebar' action handler."""
        new_state = not action.get_state().get_boolean()
        action.set_state(GLib.Variant("b", new_state))
        self.overlay_split.set_show_sidebar(new_state)

    def _on_scroll_changed(self, widget, position):
        """'scroll-changed' event handler."""
        if self.preferences.auto_scroll:
            self.renderer.scroll_to_position(position)

    def _on_filter_activate(self, _):
        """Handle activation of the JSONPath filter."""
        page = self.active_page
        if not page:
            return
        expr = self.path_entry.get_text()
        if page.renderer.get_parser() == "json":
            json_preview = page.renderer.parser_instance
            if json_preview:
                json_preview.filter_callback = self._on_filter_applied
                json_preview.apply_path_filter(expr)

    def _on_filter_applied(self, expr, count):
        """Update statusbar after a filter is applied."""
        if hasattr(self, "status_bar"):
            if expr:
                msg = f'Filter: "{expr}" → {count} match(es)'
            else:
                msg = "Filter cleared."
            self.status_bar.push(0, msg)

    def _on_change_writer(self, action, param):
        """'change-writer' action handler (applies to all tabs)."""
        if action.get_state() != param:
            action.set_state(param)
            writer = param.get_string()
            self.preferences.writer = writer
            self.preferences.save()
            for doc in self._iter_doc_pages():
                doc.renderer.set_writer(writer)

    def _on_custom_style_toggle(self, action, param):
        """'custom-style-toggle' action handler (applies to all tabs)."""
        custom_style = not action.get_state().get_boolean()
        action.set_state(GLib.Variant("b", custom_style))
        self.preferences.custom_style = custom_style
        style = self.preferences.style if custom_style else ""
        for doc in self._iter_doc_pages():
            doc.renderer.set_style(style)
        self.preferences.save()

    def _on_change_style(self, action, param):
        """'change-style' action handler (applies to all tabs)."""
        if action.get_state() != param:
            action.set_state(param)
            style = param.get_string()
            self.preferences.style = style
            effective = style if self.preferences.custom_style else ""
            for doc in self._iter_doc_pages():
                doc.renderer.set_style(effective)
            self.preferences.save()

    def _on_find_in_document(self, action, *param):
        """'find-in-document' action handler."""
        page = self.active_page
        if not page:
            return
        if (
            page.editor_type != EditorType.SOURCE
            and not page.renderer.props.visible
        ):
            return  # works only with source view or renderer

        if self.search.get_search_mode():
            if self.search_way == SearchWay.NEXT:
                self._on_find_next_match(action, *param)
            else:
                self._on_find_previous_match(action, *param)
        else:
            editor = getattr(page, "editor", None)
            if editor:
                editor.stop_search()
            page.renderer.stop_search()

            self.search_way = SearchWay.NEXT
            self.focused = self.get_focus()
            self.search.set_search_mode(True)
            self.search_entry.grab_focus()
            if self.search_text:
                self.search_entry.set_text(self.search_text)
                self.search_entry.select_region(0, -1)

    def _on_search_focus_out(self, *args):
        """'focus-leave' event handler (replaces focus-out-event)."""
        self.search_text = self.search_entry.get_text()
        if self.search.get_search_mode():
            self.search.set_search_mode(False)

    def _on_search_mode_changed(self, search_bar, param):
        """'search-mode-enabled' notify event handler."""
        if not self.search.get_search_mode():
            page = self.active_page
            editor = getattr(page, "editor", None) if page else None
            renderer = page.renderer if page else None
            if not self.search_text:
                if isinstance(self.focused, GtkSourceView):
                    if editor:
                        editor.stop_search()
                elif isinstance(self.focused, GtkWebView):
                    if renderer:
                        renderer.stop_search()
                elif (
                    page
                    and page.editor_type == EditorType.SOURCE
                    and editor
                    and editor.props.visible
                ):
                    editor.stop_search()
                elif renderer and renderer.props.visible:
                    renderer.stop_search()

            if self.focused:
                self.focused.grab_focus()
            self.focused = None

    def _on_search_changed(self, search_entry):
        """'search-changed' event handler."""
        if self.search_way == SearchWay.NEXT:
            res = self._on_find_next_match(None, None)
        else:
            res = self._on_find_previous_match(None, None)

        ctx = self.search_entry.get_style_context()
        if not res and self.search_entry.get_text():
            Gtk.StyleContext.add_class(ctx, "error")
        else:
            Gtk.StyleContext.remove_class(ctx, "error")

    def _on_find_next_match(self, action, *params):
        """'find-next-match' action handler."""
        res = False
        if self.search.get_search_mode():
            text = self.search_entry.get_text()
            page = self.active_page
            if not page:
                return res
            editor = getattr(page, "editor", None)
            renderer = page.renderer

            if isinstance(self.focused, GtkSourceView):
                res = editor.do_next_match(text) if editor else False
            elif isinstance(self.focused, GtkWebView):
                res = renderer.do_next_match(text)
            elif (
                page.editor_type == EditorType.SOURCE
                and editor
                and editor.props.visible
            ):
                res = editor.do_next_match(text)
            elif renderer.props.visible:
                res = renderer.do_next_match(text)
        return res

    def _on_find_previous_match(self, action, *params):
        """'find-previous-match' action handler."""
        res = False
        if self.search.get_search_mode():
            text = self.search_entry.get_text()
            page = self.active_page
            if not page:
                return res
            editor = getattr(page, "editor", None)
            renderer = page.renderer

            if isinstance(self.focused, GtkSourceView):
                res = editor.do_previous_match(text) if editor else False
            elif isinstance(self.focused, GtkWebView):
                res = renderer.do_previous_match(text)
            elif (
                page.editor_type == EditorType.SOURCE
                and editor
                and editor.props.visible
            ):
                res = editor.do_previous_match(text)
            elif renderer.props.visible:
                res = renderer.do_previous_match(text)
        return res

    def _on_refresh_preview(self, action, *params):
        """'refresh-preview' action handler."""
        page = self.active_page
        if page:
            page.refresh()

    def ask_if_modified(self):
        """Ask user for each unsaved tab. Returns True if OK to proceed."""
        for doc in self._iter_doc_pages():
            if doc.editor_type == EditorType.PREVIEW:
                continue
            if doc.is_modified:
                n = self.notebook.page_num(doc)
                if n >= 0:
                    self.notebook.set_current_page(n)
                dialog = UnsavedChangesDialog(doc.file_name)
                response = run_alert_dialog(dialog, self)
                if response == "cancel":
                    return False
                if (
                    response == "save"
                    and doc.editor_type == EditorType.SOURCE
                ):
                    doc.editor.save()
        self.runing = False
        for doc in self._iter_doc_pages():
            doc.stop()
            if doc.editor_type == EditorType.VIM:
                doc.editor.vim_quit()
        return True

    def destroy_from_vim(self, vim_widget=None, *args):
        """Close the tab whose VimEditor exited."""
        self.runing = False
        for doc in list(self.iter_doc_pages()):
            if doc.editor_type == EditorType.VIM and (
                vim_widget is None or doc.editor is vim_widget
            ):
                doc.stop()
                if self.notebook.get_n_pages() <= 1:
                    self.save_win_state()
                    self.destroy()
                else:
                    n = self.notebook.page_num(doc)
                    if n >= 0:
                        self._tab_labels.pop(doc, None)
                        self.notebook.remove_page(n)
                        self._update_tab_bar_visibility()
                return
        self.save_win_state()
        self.destroy()

    def save_win_state(self):
        """Persist window geometry and paned position to cache."""
        self.cache.width = self.get_width()
        self.cache.height = self.get_height()
        page = self.active_page
        if page and page.paned:
            self.cache.paned = page.paned.get_position()
        self.cache.is_maximized = self.is_maximized()
        self.cache.save()

    def _update_title(self, file_name, file_path, modified=False):
        """Update window title and headerbar title/subtitle."""
        star = "*" if modified else ""
        name = file_name or NOT_SAVED_NAME
        if file_path:
            raw_dir = dirname(file_path)
            home = expanduser("~")
            subtitle = (
                "~" + raw_dir[len(home):]
                if raw_dir.startswith(home)
                else raw_dir
            )
            wm_title = f"{star}{name} ({subtitle})"
        else:
            subtitle = "Draft"
            wm_title = f"{star}{name}"
        self._window_title.set_title(f"{star}{name}")
        self._window_title.set_subtitle(subtitle)
        self.set_title(wm_title)

    @staticmethod
    def doc_starred_name(doc):
        """Return tab display name for *doc*, prefixed with '*' if modified."""
        star = "*" if doc.is_modified else ""
        return f"{star}{doc.file_name or NOT_SAVED_NAME}"

    def _sync_tab_page_ui(self, doc):
        """Sync the tab label title and attention highlight for *doc*."""
        tab_label = self._tab_labels.get(doc)
        if not tab_label:
            return
        name = self.doc_starred_name(doc)
        tab_label.set_title(name)
        tab_label.set_needs_attention(doc.is_modified)
        fallback = f"{doc.file_name or NOT_SAVED_NAME} (Draft)"
        tab_label.set_tooltip_text(doc.file_path or fallback)

    def _sync_active_window_ui(self, doc):
        """Sync window title, save action and status bar for the active tab."""
        self._update_title(doc.file_name, doc.file_path, doc.is_modified)
        action = self.lookup_action("save-document")
        if action:
            action.set_enabled(
                doc.editor_type == EditorType.SOURCE and doc.is_modified,
            )
        if (
            hasattr(self, "status_bar")
            and doc.editor_type == EditorType.SOURCE
        ):
            self.status_bar.set_words_count(doc.words_count)
            self.status_bar.set_chars_count(doc.chars_count)

    def _on_doc_state_changed(self, doc):
        """Update tab UI and window title on name/modified state change."""
        self._sync_tab_page_ui(doc)
        if doc is self.active_page:
            self._sync_active_window_ui(doc)

    def _on_doc_words_changed(self, doc, words, chars):
        if doc is self.active_page and hasattr(self, "status_bar"):
            self.status_bar.set_words_count(words)
            self.status_bar.set_chars_count(chars)

    def _create_headerbar(self):
        headerbar = Adw.HeaderBar()
        self._window_title = Adw.WindowTitle()
        headerbar.set_title_widget(self._window_title)
        self._headerbar_pack_start(headerbar)
        self._headerbar_pack_end(headerbar)
        return headerbar

    def _headerbar_pack_start(self, headerbar):
        if self.editor_type != EditorType.PREVIEW:
            sidebar_btn = Gtk.ToggleButton(
                icon_name="sidebar-show-symbolic",
                action_name="win.toggle-sidebar",
            )
            connect_accel_tooltip(sidebar_btn, "Show File Browser")
            headerbar.pack_start(sidebar_btn)

        headerbar.pack_start(
            IconButton(
                symbol="tab-new-symbolic",
                tooltip="New Tab",
                action_name="win.new-tab",
            ),
        )
        headerbar.pack_start(
            IconButton(
                symbol="document-open-symbolic",
                tooltip="Open Document",
                action_name="win.open-document",
            ),
        )

        if self.editor_type == EditorType.SOURCE:
            headerbar.pack_start(
                IconButton(
                    symbol="document-save-symbolic",
                    tooltip="Save Document",
                    action_name="win.save-document",
                ),
            )
            self.fmt_bar = FormattingActionGroup.create_bar()
            self.fmt_bar.set_visible(self.preferences.parser != "json")
            headerbar.pack_start(self.fmt_bar)

        headerbar.pack_start(self._create_json_filter_box())

    def _headerbar_pack_end(self, headerbar):
        """Pack right-side buttons into the header bar."""
        headerbar.pack_end(
            Gtk.MenuButton(
                icon_name="open-menu-symbolic",
                tooltip_text="Main Menu",
                menu_model=AppMenu(self.editor_type),
                primary=True,
            ),
        )

        self.pref_menu = Preferences(self.preferences)
        headerbar.pack_end(
            Gtk.MenuButton(
                icon_name="emblem-system-symbolic",
                tooltip_text="Preferences",
                popover=self.pref_menu,
            ),
        )

        headerbar.pack_end(
            IconButton(
                symbol="view-refresh-symbolic",
                tooltip="Refresh preview",
                action_name="win.refresh-preview",
            ),
        )

        headerbar.pack_end(self._create_json_fold_box())

        if self.editor_type != EditorType.PREVIEW:
            headerbar.pack_end(self._create_view_toggle_box())

    def _create_json_filter_box(self):
        """Create the JSONPath filter entry and button box."""
        self.path_entry = Gtk.SearchEntry(placeholder_text="JSONPath filter…")
        self.path_entry.set_width_chars(50)
        self.path_entry.set_hexpand(True)
        self.path_entry.connect("activate", self._on_filter_activate)

        filter_btn = Gtk.Button.new_from_icon_name("system-search-symbolic")
        filter_btn.set_tooltip_text("Apply Filter")
        filter_btn.connect("clicked", self._on_filter_activate)

        self.json_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.json_box.add_css_class("linked")
        self.json_box.append(self.path_entry)
        self.json_box.append(filter_btn)
        self.json_box.set_visible(self.preferences.parser == "json")
        return self.json_box

    def _create_json_fold_box(self):
        """Create the JSON expand/collapse buttons box."""
        self.json_fold_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.json_fold_box.add_css_class("linked")
        self.json_fold_box.append(
            IconButton(
                symbol="format-indent-more-symbolic",
                tooltip="Expand All",
                action_name="win.json-expand-all",
            ),
        )
        self.json_fold_box.append(
            IconButton(
                symbol="format-indent-less-symbolic",
                tooltip="Collapse All",
                action_name="win.json-collapse-all",
            ),
        )
        self.json_fold_box.set_visible(self.preferences.parser == "json")
        return self.json_fold_box

    def _create_view_toggle_box(self):
        """Create the editor/preview/both toggle button group."""
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.add_css_class("linked")

        self.editor_toggle_btn = Gtk.ToggleButton(
            icon_name="text-editor-symbolic",
            action_name="win.switch-view-toggle",
            action_target=GLib.Variant("q", View.EDITOR),
        )
        connect_accel_tooltip(
            self.editor_toggle_btn, "Show Editor", "win.show-editor",
        )
        btn_box.append(self.editor_toggle_btn)

        self.preview_toggle_btn = Gtk.ToggleButton(
            icon_name="view-reveal-symbolic",
            action_name="win.switch-view-toggle",
            action_target=GLib.Variant("q", View.PREVIEW),
        )
        connect_accel_tooltip(
            self.preview_toggle_btn, "Show Web Preview", "win.show-preview",
        )
        btn_box.append(self.preview_toggle_btn)

        self.both_toggle_btn = Gtk.ToggleButton(
            icon_name="view-dual-symbolic",
            action_name="win.switch-view-toggle",
            action_target=GLib.Variant("q", View.BOTH),
        )
        connect_accel_tooltip(
            self.both_toggle_btn,
            "Show Editor and Web Preview",
            "win.show-both",
        )
        btn_box.append(self.both_toggle_btn)

        return btn_box

    def _setup_layout(self, file_name, no_initial_tab=False):
        """Create and wire up the window layout."""
        self.set_default_size(self.cache.width, self.cache.height)

        self.notebook = Gtk.Notebook()
        self.notebook.set_scrollable(True)
        self.notebook.set_show_border(False)
        self.notebook.set_show_tabs(False)
        self.notebook.connect("switch-page", self._on_tab_switched)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(self._create_headerbar())

        if self.editor_type == EditorType.SOURCE:
            self.status_bar = Statusbar(self.preferences.editor)
            toolbar_view.add_bottom_bar(self.status_bar)

        overlay = Gtk.Overlay()
        overlay.set_vexpand(True)
        self._create_search_bar(overlay)

        if self.editor_type != EditorType.PREVIEW:
            self.file_browser = FileBrowser()
            self.file_browser.connect(
                "file-activated",
                self._on_browser_file_activated,
            )
            self.overlay_split = Adw.OverlaySplitView(
                collapsed=True,
                show_sidebar=False,
                sidebar=self.file_browser,
                content=self.notebook,
                sidebar_width_unit=Adw.LengthUnit.SP,
                min_sidebar_width=220,
                max_sidebar_width=220,
            )
            overlay.set_child(self.overlay_split)
        else:
            overlay.set_child(self.notebook)

        toolbar_view.set_content(overlay)
        self.set_content(toolbar_view)

        if self.cache.is_maximized:
            self.maximize()

        if not no_initial_tab:
            self.new_tab(file_name)

    def _create_search_bar(self, overlay):
        """Create the floating search bar and add it to *overlay*."""
        self.search_text = ""
        self.search = Gtk.SearchBar()
        self.search.set_show_close_button(False)
        self.search.set_halign(Gtk.Align.CENTER)
        self.search.set_valign(Gtk.Align.START)
        self.search.connect(
            "notify::search-mode-enabled",
            self._on_search_mode_changed,
        )
        overlay.add_overlay(self.search)

        sbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        sbox.add_css_class("linked")
        self.search.set_child(sbox)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_width_chars(30)
        self.search_entry.set_hexpand(True)
        sbox.append(self.search_entry)
        self.search.connect_entry(self.search_entry)
        self.search_entry.connect("search-changed", self._on_search_changed)

        focus_ctrl = Gtk.EventControllerFocus.new()
        focus_ctrl.connect("leave", self._on_search_focus_out)
        self.search_entry.add_controller(focus_ctrl)

        sbox.append(
            IconButton(
                symbol="go-previous-symbolic",
                tooltip="Previous search",
                action_name="win.find-previous-match",
                focus_on_click=False,
            ),
        )
        sbox.append(
            IconButton(
                symbol="go-next-symbolic",
                tooltip="Next search",
                action_name="win.find-next-match",
                focus_on_click=False,
            ),
        )

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def _update_tab_bar_visibility(self):
        """Auto-hide the tab bar when only one tab is open."""
        self.notebook.set_show_tabs(self.notebook.get_n_pages() > 1)

    def new_tab(self, file_name=""):
        """Open *file_name* (or an empty document) in a new tab.

        If the active tab is an empty, unmodified document, the file is loaded
        into it instead of opening a new tab.
        """
        if file_name:
            active = self.active_page
            if (
                active is not None
                and active.editor_type != EditorType.PREVIEW
                and not active.file_path
                and not active.is_modified
            ):
                active.load_file(file_name)
                return active

        # Sync cache.paned from active tab so new tab inherits current split
        active = self.active_page
        if active and active.paned:
            self.cache.paned = active.paned.get_position()
        doc = DocumentPage(self, self.editor_type, file_name)
        title = basename(file_name) if file_name else NOT_SAVED_NAME
        tab_label = TabLabel(
            title, lambda _btn, d=doc: self._request_close_doc(d),
        )
        self._tab_labels[doc] = tab_label
        doc.connect("doc-state-changed", self._on_doc_state_changed)
        doc.connect("words-count-changed", self._on_doc_words_changed)
        scroll_ctrl = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL,
        )
        scroll_ctrl.connect("scroll", self._on_tab_label_scroll)
        tab_label.add_controller(scroll_ctrl)
        idx = self.notebook.append_page(doc, tab_label)
        self.notebook.set_tab_reorderable(doc, True)
        doc.show()
        self.notebook.set_current_page(idx)
        self._update_tab_bar_visibility()
        return doc

    def _on_new_tab(self, action, *params):
        self.new_tab()

    def _on_next_tab(self, action, *params):
        """Switch to the next tab, wrapping around at the end."""
        n = self.notebook.get_n_pages()
        if n > 1:
            current = self.notebook.get_current_page()
            self.notebook.set_current_page((current + 1) % n)

    def _on_prev_tab(self, action, *params):
        """Switch to the previous tab, wrapping around at the start."""
        n = self.notebook.get_n_pages()
        if n > 1:
            current = self.notebook.get_current_page()
            self.notebook.set_current_page((current - 1) % n)

    def _on_tab_label_scroll(self, _ctrl, _dx, dy):
        """Switch tab on mouse-wheel scroll over a tab label."""
        n = self.notebook.get_n_pages()
        if n <= 1:
            return False
        current = self.notebook.get_current_page()
        if dy > 0:
            self.notebook.set_current_page(min(current + 1, n - 1))
        elif dy < 0:
            self.notebook.set_current_page(max(current - 1, 0))
        return True

    @property
    def active_page(self):
        """Active :class:`DocumentPage`, or ``None``."""
        n = self.notebook.get_current_page()
        return self.notebook.get_nth_page(n) if n >= 0 else None

    def iter_doc_pages(self):
        """Yield all :class:`DocumentPage` instances in this window."""
        for i in range(self.notebook.get_n_pages()):
            yield self.notebook.get_nth_page(i)

    def _iter_doc_pages(self):
        """Alias for backwards compat; prefer iter_doc_pages()."""
        yield from self.iter_doc_pages()

    def get_page_for_doc(self, doc):
        """Return *doc* if it is an open tab in this window, else ``None``."""
        return doc if self.notebook.page_num(doc) >= 0 else None

    def _on_tab_switched(self, notebook, doc, page_num):
        """Handle tab switch: update action groups, title, parser UI."""
        # Copy paned position from the previously active tab
        prev = self._last_active_doc
        if (
            prev is not None
            and prev is not doc
            and prev.paned
            and doc.paned
            and doc not in self._tabs_needing_paned_reset
        ):
            doc.paned.set_position(prev.paned.get_position())
        self._last_active_doc = doc

        if hasattr(doc, "fmt_actions"):
            self.insert_action_group("fmt", doc.fmt_actions)
        if hasattr(doc, "editor_actions"):
            self.insert_action_group("editor", doc.editor_actions)

        self._sync_active_window_ui(doc)

        parser = doc.parser
        action = self.lookup_action("change-parser")
        if action:
            action.set_state(GLib.Variant("s", parser))
        self._apply_parser_ui(parser)

        if doc in self._tabs_needing_paned_reset:
            # Same GTK#1959 workaround: defer set_position until after layout.
            GLib.timeout_add(20, self._reset_active_paned)

        if hasattr(self, "file_browser") and doc.file_path:
            directory = dirname(doc.file_path)
            if directory:
                self.file_browser.set_directory(directory)

        if hasattr(self, "search") and self.search.get_search_mode():
            self.search.set_search_mode(False)

    def _request_close_doc(self, doc):
        """Close tab for *doc*, prompting to save if unsaved changes exist."""
        if doc.editor_type != EditorType.PREVIEW and doc.is_modified:
            n = self.notebook.page_num(doc)
            if n >= 0:
                self.notebook.set_current_page(n)
            dialog = UnsavedChangesDialog(doc.file_name)
            response = run_alert_dialog(dialog, self)
            if response == "cancel":
                return
            if response == "save" and doc.editor_type == EditorType.SOURCE:
                doc.editor.save()
        self._finalize_close_doc(doc)

    def _finalize_close_doc(self, doc):
        """Stop the doc's refresh loop and remove its tab."""
        doc.stop()
        if doc.editor_type == EditorType.VIM and hasattr(doc, "editor"):
            doc.editor.vim_quit()
        n = self.notebook.page_num(doc)
        if n >= 0:
            self._tab_labels.pop(doc, None)
            self.notebook.remove_page(n)
            self._update_tab_bar_visibility()
        if self.notebook.get_n_pages() == 0:
            self.save_win_state()
            self.destroy()

    # ------------------------------------------------------------------
    # Old refresh methods removed; refresh and title updates are now
    # driven by DocumentPage signals (doc-state-changed, words-count-changed).
    # ------------------------------------------------------------------

    @property
    def file_path(self):
        """Return the active tab's file path."""
        page = self.active_page
        return page.file_path if page else None
