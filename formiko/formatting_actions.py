"""Formatting action group for the SOURCE editor."""

from typing import ClassVar

from gi.repository import Gio, Gtk

from formiko.dialogs import InsertLinkDialog
from formiko.format_utils import (
    RST_HEADER_CHARS,
    build_known_formats,
    compute_link,
)
from formiko.widgets import IconButton

#: Parsers that support inline and block formatting.
FORMATTING_PARSERS = frozenset(("rst", "m2r", "html"))


class FormattingActionGroup(Gio.SimpleActionGroup):
    """Action group for inline and block text formatting.

    Instantiate once and insert into the window with::

        window.insert_action_group("fmt", group)

    Buttons in the UI use ``action_name="fmt.bold-text"`` etc.
    Call :meth:`set_parser` whenever the active parser changes so that
    actions are enabled only for supported formats.
    """

    # ------------------------------------------------------------------ inline
    _MARKUP_BOLD: ClassVar = {
        "rst": ("**", "**"),
        "m2r": ("**", "**"),
        "html": ("<b>", "</b>"),
    }
    _MARKUP_ITALIC: ClassVar = {
        "rst": ("*", "*"),
        "m2r": ("*", "*"),
        "html": ("<i>", "</i>"),
    }
    _MARKUP_STRIKETHROUGH: ClassVar = {
        "rst": (":del:`", "`"),
        "m2r": ("~~", "~~"),
        "html": ("<s>", "</s>"),
    }
    _MARKUP_CODE: ClassVar = {
        "rst": ("``", "``"),
        "m2r": ("`", "`"),
        "html": ("<code>", "</code>"),
    }

    # Per-parser list of all known *inline* markers (used for stripping).
    # Block-level markers are intentionally excluded.
    _KNOWN_FORMATS: ClassVar = build_known_formats(
        _MARKUP_BOLD, _MARKUP_ITALIC, _MARKUP_STRIKETHROUGH, _MARKUP_CODE,
    )

    # (action-name, icon, tooltip, markup-dict) for each inline button
    _INLINE_DEFS: ClassVar = (
        ("bold-text", "format-text-bold-symbolic", "Bold", _MARKUP_BOLD),
        (
            "italic-text",
            "format-text-italic-symbolic",
            "Italic",
            _MARKUP_ITALIC,
        ),
        (
            "strikethrough-text",
            "format-text-strikethrough-symbolic",
            "Strikethrough",
            _MARKUP_STRIKETHROUGH,
        ),
        (
            "code-text",
            "format-text-code-symbolic",
            "Inline Code",
            _MARKUP_CODE,
        ),
    )

    # ------------------------------------------------------------------ block
    # Block markup values may be a plain ``(before, after)`` tuple or a
    # callable ``(editor_pref) -> (before, after)`` for formats whose markers
    # depend on editor settings (e.g. RST indentation).
    _MARKUP_BLOCKQUOTE: ClassVar = {
        "rst": lambda pref: (
            " " * pref.tab_width if pref.spaces_instead_of_tabs else "\t",
            "",
        ),
        "m2r": ("> ", ""),
        "html": ("<blockquote>", "</blockquote>"),
    }

    # (action-name, icon, tooltip, markup-dict) for each block button
    _BLOCK_DEFS: ClassVar = (
        (
            "blockquote",
            "format-text-blockquote-symbolic",
            "Blockquote",
            _MARKUP_BLOCKQUOTE,
        ),
    )

    def __init__(self, editor, renderer, parser, preferences):
        """Create all formatting actions.

        :param editor: The :class:`~formiko.sourceview.SourceView` instance.
        :param renderer: The :class:`~formiko.renderer.Renderer` instance used
            to query the active parser via ``renderer.get_parser()``.
        :param parser: The initial parser name (used to set enabled state).
        :param preferences: The :class:`~formiko.user.UserPreferences` object;
            its ``.editor`` attribute is consulted for RST indent settings.
        """
        super().__init__()
        self._editor = editor
        self._renderer = renderer
        self._editor_pref = preferences.editor

        is_markup = parser in FORMATTING_PARSERS
        self._actions: dict[str, Gio.SimpleAction] = {}

        for name, _icon, _tooltip, markup_dict in self._INLINE_DEFS:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", self._make_inline_handler(markup_dict))
            action.set_enabled(is_markup)
            self.add_action(action)
            self._actions[name] = action

        for name, _icon, _tooltip, markup_dict in self._BLOCK_DEFS:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", self._make_block_handler(markup_dict))
            action.set_enabled(is_markup)
            self.add_action(action)
            self._actions[name] = action

        # Header actions: one per level (1-6) for reliable keyboard shortcuts
        for level in range(1, 7):
            action = Gio.SimpleAction.new(f"header-{level}", None)
            action.connect(
                "activate",
                lambda _a, _p, lvl=level: self._on_header_level(lvl),
            )
            action.set_enabled(is_markup)
            self.add_action(action)
            self._actions[f"header-{level}"] = action

        # Bullet-list action
        bullet_action = Gio.SimpleAction.new("bullet", None)
        bullet_action.connect("activate", self._on_bullet)
        bullet_action.set_enabled(is_markup)
        self.add_action(bullet_action)
        self._actions["bullet"] = bullet_action

        # Ordered (numbered) list action
        ordered_action = Gio.SimpleAction.new("ordered", None)
        ordered_action.connect("activate", self._on_ordered)
        ordered_action.set_enabled(is_markup)
        self.add_action(ordered_action)
        self._actions["ordered"] = ordered_action

        # Insert-link action
        link_action = Gio.SimpleAction.new("insert-link", None)
        link_action.connect("activate", self._on_insert_link)
        link_action.set_enabled(is_markup)
        self.add_action(link_action)
        self._actions["insert-link"] = link_action

    # ------------------------------------------------------------------
    # Public API

    def set_parser(self, parser: str) -> None:
        """Enable or disable all formatting actions for *parser*."""
        is_markup = parser in FORMATTING_PARSERS
        for action in self._actions.values():
            action.set_enabled(is_markup)

    @staticmethod
    def create_bar() -> Gtk.Box:
        """Return a :class:`Gtk.Box` containing the full formatting toolbar.

        Inline buttons and block buttons are placed in separate linked groups
        with a visual separator between them.  The caller inserts the returned
        box into the UI.

        This is a static method so that the bar can be built before the action
        group instance is registered — GTK resolves ``fmt.*`` actions lazily.
        """
        G = FormattingActionGroup  # noqa: N806

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        inline_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        inline_box.add_css_class("linked")
        for name, icon, tooltip, _ in G._INLINE_DEFS:  # noqa: SLF001
            inline_box.append(
                IconButton(
                    symbol=icon,
                    tooltip=tooltip,
                    action_name=f"fmt.{name}",
                    focus_on_click=False,
                ),
            )
        inline_box.append(
            IconButton(
                symbol="insert-link-symbolic",
                tooltip="Insert Link",
                action_name="fmt.insert-link",
                focus_on_click=False,
            ),
        )
        outer.append(inline_box)

        outer.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        block_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        block_box.add_css_class("linked")

        # Simple block buttons (blockquote, …)
        for name, icon, tooltip, _ in G._BLOCK_DEFS:  # noqa: SLF001
            block_box.append(
                IconButton(
                    symbol=icon,
                    tooltip=tooltip,
                    action_name=f"fmt.{name}",
                    focus_on_click=False,
                ),
            )

        # Header dropdown button
        header_menu = Gio.Menu()
        for level in range(1, 7):
            header_menu.append(f"Header {level}", f"fmt.header-{level}")

        header_btn = Gtk.MenuButton(
            icon_name="format-text-larger-symbolic",
            tooltip_text="Header level",
            menu_model=header_menu,
            focus_on_click=False,
        )
        block_box.append(header_btn)

        block_box.append(
            IconButton(
                symbol="view-list-bullet-symbolic",
                tooltip="Bullet list",
                action_name="fmt.bullet",
                focus_on_click=False,
            ),
        )

        block_box.append(
            IconButton(
                symbol="view-list-ordered-symbolic",
                tooltip="Ordered list",
                action_name="fmt.ordered",
                focus_on_click=False,
            ),
        )

        outer.append(block_box)

        return outer

    # ------------------------------------------------------------------
    # Private helpers

    def _make_inline_handler(self, markup_dict):
        """Return an activate callback for an inline format action."""
        def handler(_action, *_params):
            parser = self._renderer.get_parser()
            before, after = markup_dict[parser]
            known = self._KNOWN_FORMATS.get(parser, [])
            self._editor.toggle_format(before, after, known)
        return handler

    def _make_block_handler(self, markup_dict):
        """Return an activate callback for a block format action."""
        def handler(_action, *_params):
            parser = self._renderer.get_parser()
            fmt = markup_dict[parser]
            if callable(fmt):
                before, after = fmt(self._editor_pref)
            else:
                before, after = fmt
            if parser == "rst":
                # RST blockquote is indentation; strip bullet/ordered
                self._editor.toggle_line_format(
                    before, after,
                    all_block_variants=(("- ", ""),),
                    strip_ordered=True,
                )
            elif parser == "m2r":
                self._editor.toggle_line_format(
                    before, after,
                    all_block_variants=self._MD_BLOCK_VARIANTS,
                    strip_ordered=True,
                )
            else:  # html
                self._editor.toggle_line_format(
                    before, after,
                    all_block_variants=self._HTML_BLOCK_VARIANTS,
                    strip_ordered=True,
                )
        return handler

    @staticmethod
    def _header_markup(parser: str, level: int) -> "tuple[str, str]":
        """Return ``(before, after)`` for the given header *level*."""
        if parser == "m2r":
            return "#" * level + " ", ""
        # html
        return f"<h{level}>", f"</h{level}>"

    def _on_header_level(self, level: int) -> None:
        """Activate callback for the ``header-N`` actions."""
        parser = self._renderer.get_parser()

        if parser == "rst":
            self._editor.toggle_rst_header(RST_HEADER_CHARS[level - 1])
        else:
            before, after = self._header_markup(parser, level)
            all_variants = [
                self._header_markup(parser, lvl) for lvl in range(1, 7)
            ]
            if parser == "m2r":
                extra = (("> ", ""), ("- ", ""))
            else:  # html
                extra = (("<blockquote>", "</blockquote>"), ("<li>", "</li>"))
            self._editor.toggle_line_exclusive(
                before, after, all_variants,
                extra_strip_variants=extra,
                strip_ordered=True,
            )

    # Known block-level prefixes (used for cross-format stripping).
    # Ordered: strips these when toggling *on* (regex handles bullet→ordered).
    # Bullet/header/blockquote: strip each other via all_block_variants /
    # extra_strip_variants and strip_ordered=True.
    _MD_BLOCK_VARIANTS: ClassVar = (
        ("###### ", ""), ("##### ", ""), ("#### ", ""),
        ("### ", ""), ("## ", ""), ("# ", ""),
        ("> ", ""),
        ("- ", ""),
    )
    _HTML_BLOCK_VARIANTS: ClassVar = tuple(
        [(f"<h{n}>", f"</h{n}>") for n in range(1, 7)]
        + [("<blockquote>", "</blockquote>"), ("<li>", "</li>")],
    )

    def _on_bullet(self, _action, *_params) -> None:
        """Activate callback for the ``bullet`` action."""
        parser = self._renderer.get_parser()

        if parser == "rst":
            self._editor.toggle_bullet(
                "- ", "", (), needs_blank=True,
                strip_ordered=True,
            )
        elif parser == "m2r":
            self._editor.toggle_bullet(
                "- ", "", self._MD_BLOCK_VARIANTS, needs_blank=True,
                strip_ordered=True,
            )
        else:  # html
            self._editor.toggle_bullet(
                "<li>", "</li>", self._HTML_BLOCK_VARIANTS, needs_blank=False,
            )

    def _on_ordered(self, _action, *_params) -> None:
        """Activate callback for the ``ordered`` action."""
        parser = self._renderer.get_parser()

        if parser == "rst":
            self._editor.toggle_ordered(
                all_block_variants=(("- ", ""),),
                needs_blank=True,
                auto_number=True,
            )
        elif parser == "m2r":
            self._editor.toggle_ordered(
                all_block_variants=self._MD_BLOCK_VARIANTS,
                needs_blank=True,
            )
        else:  # html — numbered list items use the same <li> as bullet
            self._editor.toggle_bullet(
                "<li>", "</li>", self._HTML_BLOCK_VARIANTS, needs_blank=False,
            )

    def _on_insert_link(self, _action, *_params) -> None:
        """Activate callback for the ``insert-link`` action."""
        parser = self._renderer.get_parser()
        selected = self._editor.get_selected_text()
        # Capture offsets now — selection will be lost when dialog grabs focus
        start_off, end_off = self._editor.get_selection_offsets()

        def do_insert(text, url):
            link = compute_link(text, url, parser)
            self._editor.insert_link_text(link, start_off, end_off)

        root = self._editor.get_root()
        dlg = InsertLinkDialog(do_insert, selected, parser)
        dlg.present_and_focus(root)
