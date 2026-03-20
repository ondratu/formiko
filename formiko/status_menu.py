"""Status bar menu widgets."""
from gi.repository import Gio, GLib, Gtk

from formiko.widgets import ActionableSpinButton


class StatusMenuButton(Gtk.MenuButton):
    """Status bar menu button."""

    css = Gtk.CssProvider()
    css.load_from_string("""
            * {
                border: 0;
                padding: 1px 8px 2px 4px;
                outline-width: 0;
            }
        """)

    def __init__(self, label, popover):
        super().__init__(popover=popover)
        ctx = self.get_style_context()
        ctx.add_provider(
            StatusMenuButton.css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        self.set_child(box)
        self.label = Gtk.Label(label=label)
        box.append(self.label)

        icon = Gio.ThemedIcon(name="pan-down-symbolic")
        img = Gtk.Image.new_from_gicon(icon)
        box.append(img)

    def set_label(self, label):
        """Set button label."""
        self.label.set_label(label)


class LineColPopover(Gtk.Popover):
    """Lines and columns settings popover."""

    def __init__(self, preferences):
        super().__init__()

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.box.set_margin_top(10)
        self.box.set_margin_bottom(10)
        self.box.set_margin_start(10)
        self.box.set_margin_end(10)
        self.set_child(self.box)

        self.box.append(
            self.check_button(
                "Display line numbers",
                "editor.line-numbers-toggle",
                preferences.line_numbers,
            ),
        )
        self.box.append(
            self.check_button(
                "Highlight current line",
                "editor.current-line-toggle",
                preferences.current_line,
            ),
        )
        self.box.append(self.margin(preferences))
        self.box.append(
            self.check_button(
                "Text wrapping",
                "editor.text-wrapping-toggle",
                preferences.text_wrapping,
            ),
        )
        self.box.append(
            self.check_button(
                "Draw white chars",
                "editor.white-chars-toggle",
                preferences.white_chars,
            ),
        )

    def check_button(self, label, action, value):
        """Create check button for specific settings."""
        del value  # GTK4 auto-syncs from action state
        return Gtk.CheckButton(label=label, action_name=action)

    def margin(self, preferences):
        """Create Box with right margin settings."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        toggle = self.check_button(
            "Display right margin",
            "editor.right-margin-toggle",
            preferences.right_margin,
        )
        vbox.append(toggle)

        spin = ActionableSpinButton(
            "editor.right-margin-value",
            sensitive=preferences.right_margin,
            value=preferences.right_margin_value,
        )
        spin.set_range(1.0, 256.0)
        spin.set_increments(1.0, 8.0)
        vbox.append(spin)
        toggle.connect("toggled", self.on_margin_toggle, spin)

        return vbox

    def on_margin_toggle(self, widget, spin):
        """Change sensitve when margin toggle was changed."""
        spin.set_sensitive(widget.get_active())


class Statusbar(Gtk.Box):
    """Status bar widget."""

    css = Gtk.CssProvider()
    css.load_from_string(
        "* {border-top: 1px solid alpha(currentColor, 0.15); padding: 1px;}",
    )

    def __init__(self, preferences):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        ctx = self.get_style_context()
        ctx.add_provider(
            Statusbar.css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.message_label = Gtk.Label()
        self.message_label.set_hexpand(True)
        self.message_label.set_margin_start(10)
        self.message_label.set_margin_end(10)
        self.append(self.message_label)

        self._words_count = 0
        self._chars_count = 0
        self.info_bar = self.create_info_bar()
        self._update_stat_label()
        self.info_bar.set_margin_start(10)
        self.info_bar.set_margin_end(10)
        self.append(self.info_bar)

        self.editor_popover = self.create_editor_popover(preferences)
        self.editor_btn = StatusMenuButton("Editor", self.editor_popover)
        self.append(self.editor_btn)

        self.tab_popover = self.create_tab_popover(preferences)
        self.width_btn = StatusMenuButton(
            f"Tabulator width {preferences.tab_width}",
            self.tab_popover,
        )
        self.append(self.width_btn)

        btn = StatusMenuButton("Line 1, Col 1", LineColPopover(preferences))
        self.append(btn)

    def create_tab_popover(self, preferences):
        """Create popover for tab settings."""
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        pop.set_child(box)

        auto_indent = Gtk.CheckButton(
            label="Auto indent",
            action_name="editor.auto-indent-toggle",
        )
        box.append(auto_indent)

        box.append(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
        )

        tab_group = None
        for i in (2, 4, 8):
            tab_btn = Gtk.CheckButton(
                label=str(i),
                group=tab_group,
                action_target=GLib.Variant("i", i),
            )
            if preferences.tab_width == i:
                tab_btn.set_active(True)
            tab_btn.connect("toggled", self.on_tab_spaces)
            tab_btn.set_action_name("editor.tab-width")
            box.append(tab_btn)
            if tab_group is None:
                tab_group = tab_btn

        box.append(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
        )

        self.tab_use_space = Gtk.CheckButton(
            label="Use spaces",
            action_name="editor.use-spaces-toggle",
        )
        box.append(self.tab_use_space)

        return pop

    def on_tab_spaces(self, widget):
        """Set label when radio buttons was toggled."""
        if widget.get_active():
            self.width_btn.set_label(
                f"Tabulator width {widget.get_action_target_value()}",
            )

    def create_editor_popover(self, preferences):
        """Create Editor preferences popover."""
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        pop.set_child(box)

        period_btn = Gtk.CheckButton(
            label="Save file each 5 min",
            action_name="editor.period-save-toggle",
        )
        box.append(period_btn)

        spell_btn = Gtk.CheckButton(
            label="Check Spelling",
            action_name="editor.check-spelling-toggle",
        )
        box.append(spell_btn)

        auto_bullet_btn = Gtk.CheckButton(
            label="Auto bullet completion",
            action_name="editor.auto-bullet-toggle",
        )
        box.append(auto_bullet_btn)

        tab_indent_btn = Gtk.CheckButton(
            label="Tab key indents bullets",
            action_name="editor.tab-indent-bullet-toggle",
        )
        box.append(tab_indent_btn)

        return pop

    def create_info_bar(self):
        """Create info bar part."""
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bar.stat_label = Gtk.Label()
        bar.append(bar.stat_label)
        return bar

    def _update_stat_label(self):
        """Reformat the combined word/character count label."""
        self.info_bar.stat_label.set_label(
            f"{self._words_count}\N{NO-BREAK SPACE}words,"
            f" {self._chars_count}\N{NO-BREAK SPACE}characters",
        )

    def set_words_count(self, count):
        """Set words count label."""
        self._words_count = count
        self._update_stat_label()

    def set_chars_count(self, count):
        """Set chars count label."""
        self._chars_count = count
        self._update_stat_label()

    def push(self, context_id, text):
        """Set message to status bar."""
        self.message_label.set_text(text)
