"""Actions for sourceview editor."""

from gi.repository.Gio import SimpleAction, SimpleActionGroup
from gi.repository.GLib import Variant, VariantType


class EditorActionGroup(SimpleActionGroup):
    """Edtior Action group."""

    def __init__(self, editor, renderer, preferences):
        super().__init__()
        self.editor = editor
        self.renderer = renderer
        self.preferences = preferences
        self.editor_pref = preferences.editor

        self.create_toggle_action(
            "period-save-toggle",
            self.editor_pref.period_save,
            self.on_period_save,
        )
        self.create_toggle_action(
            "check-spelling-toggle",
            self.editor_pref.check_spelling,
            self.on_check_spelling,
        )
        self.create_toggle_action(
            "auto-bullet-toggle",
            self.editor_pref.auto_bullet,
            self.on_auto_bullet,
        )
        self.create_toggle_action(
            "tab-indent-bullet-toggle",
            self.editor_pref.tab_indent_bullet,
            self.on_tab_indent_bullet,
        )

        action = SimpleAction.new("spell-lang", VariantType("s"))
        action.connect("activate", self.on_spell_lang)
        self.add_action(action)

        self.create_toggle_action(
            "use-spaces-toggle",
            self.editor_pref.spaces_instead_of_tabs,
            self.on_use_spaces,
        )
        self.create_stateful_action(
            "tab-width",
            "i",
            self.editor_pref.tab_width,
            self.on_tab_width,
        )
        self.create_toggle_action(
            "auto-indent-toggle",
            self.editor_pref.auto_indent,
            self.on_auto_indent,
        )
        self.create_toggle_action(
            "line-numbers-toggle",
            self.editor_pref.line_numbers,
            self.on_line_numbers,
        )
        self.create_toggle_action(
            "right-margin-toggle",
            self.editor_pref.right_margin,
            self.on_right_margin,
        )
        self.create_stateful_action(
            "right-margin-value",
            "d",
            self.editor_pref.right_margin_value,
            self.on_right_margin_value,
        )
        self.create_toggle_action(
            "current-line-toggle",
            self.editor_pref.current_line,
            self.on_current_line,
        )
        self.create_toggle_action(
            "text-wrapping-toggle",
            self.editor_pref.text_wrapping,
            self.on_text_wrapping,
        )
        self.create_toggle_action(
            "white-chars-toggle",
            self.editor_pref.white_chars,
            self.on_white_chars,
        )

    def create_stateful_action(self, name, _type, default_value, method):
        """Create stateful action helper."""
        action = SimpleAction.new_stateful(
            name,
            VariantType.new(_type),
            Variant(_type, default_value),
        )
        action.connect("change-state", method)
        self.add_action(action)

    def create_toggle_action(self, name, default_value, method):
        """Create boolean toggle action (no parameter type, activate-based)."""
        action = SimpleAction.new_stateful(
            name,
            None,
            Variant("b", default_value),
        )
        action.connect("activate", method)
        self.add_action(action)

    def on_period_save(self, action, _):
        """Save period save preferences."""
        period_save = not action.get_state().get_boolean()
        action.set_state(Variant("b", period_save))
        self.editor_pref.period_save = period_save
        self.editor.set_period_save(period_save)
        self.preferences.save()

    def on_check_spelling(self, action, _):
        """Set spell check preferences."""
        check_spelling = not action.get_state().get_boolean()
        action.set_state(Variant("b", check_spelling))
        self.editor_pref.check_spelling = check_spelling
        self.editor.set_check_spelling(
            check_spelling,
            self.editor_pref.spell_lang,
        )
        self.preferences.save()

    def on_auto_bullet(self, action, _):
        """Save auto bullet completion preferences."""
        auto_bullet = not action.get_state().get_boolean()
        action.set_state(Variant("b", auto_bullet))
        self.editor_pref.auto_bullet = auto_bullet
        self.editor.set_auto_bullet(auto_bullet)
        self.preferences.save()

    def on_tab_indent_bullet(self, action, _):
        """Save Tab key indentation for bullets preferences."""
        tab_indent_bullet = not action.get_state().get_boolean()
        action.set_state(Variant("b", tab_indent_bullet))
        self.editor_pref.tab_indent_bullet = tab_indent_bullet
        self.editor.set_tab_indent_bullet(tab_indent_bullet)
        self.preferences.save()

    def on_spell_lang(self, _, param):
        """Save right spell lang preferences."""
        self.editor_pref.spell_lang = param.get_string()
        self.preferences.save()

    def on_use_spaces(self, action, _):
        """Save space vs tabs preferences."""
        use_spaces = not action.get_state().get_boolean()
        action.set_state(Variant("b", use_spaces))
        self.editor_pref.spaces_instead_of_tabs = use_spaces
        self.editor.set_spaces_instead_of_tabs(use_spaces)
        self.preferences.save()

    def on_tab_width(self, action, param):
        """Save tab width preferences."""
        width = param.get_int32()
        if width != self.editor_pref.tab_width:
            action.set_state(Variant("i", width))
            self.editor_pref.tab_width = width
            self.editor.source_view.set_tab_width(width)
            self.renderer.set_tab_width(width)
            self.preferences.save()

    def on_auto_indent(self, action, _):
        """Save auto indent preferences."""
        auto_indent = not action.get_state().get_boolean()
        action.set_state(Variant("b", auto_indent))
        self.editor_pref.auto_indent = auto_indent
        self.editor.source_view.set_auto_indent(auto_indent)
        self.preferences.save()

    def on_line_numbers(self, action, _):
        """Save line number showing."""
        line_numbers = not action.get_state().get_boolean()
        action.set_state(Variant("b", line_numbers))
        self.editor_pref.line_numbers = line_numbers
        self.editor.source_view.set_show_line_numbers(line_numbers)
        self.preferences.save()

    def on_right_margin(self, action, _):
        """Save right margin preferences."""
        right_margin = not action.get_state().get_boolean()
        action.set_state(Variant("b", right_margin))
        self.editor_pref.right_margin = right_margin
        self.editor.source_view.set_show_right_margin(right_margin)
        self.preferences.save()

    def on_right_margin_value(self, _, param):
        """Save right margin value preferences."""
        margin_value = int(param.get_double())
        self.editor_pref.right_margin_value = margin_value
        self.editor.source_view.set_right_margin_position(margin_value)
        self.preferences.save()

    def on_current_line(self, action, _):
        """Save highlighting current file preferences."""
        current_line = not action.get_state().get_boolean()
        action.set_state(Variant("b", current_line))
        self.editor_pref.current_line = current_line
        self.editor.source_view.set_highlight_current_line(current_line)
        self.preferences.save()

    def on_text_wrapping(self, action, _):
        """Save text wrapping mode preferences."""
        text_wrapping = not action.get_state().get_boolean()
        action.set_state(Variant("b", text_wrapping))
        self.editor_pref.text_wrapping = text_wrapping
        self.editor.set_text_wrapping(text_wrapping)
        self.preferences.save()

    def on_white_chars(self, action, _):
        """Save showing white chars preferences."""
        white_chars = not action.get_state().get_boolean()
        action.set_state(Variant("b", white_chars))
        self.editor_pref.white_chars = white_chars
        self.editor.set_white_chars(white_chars)
        self.preferences.save()
