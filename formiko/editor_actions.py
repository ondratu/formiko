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

        self.create_stateful_action(
            "period-save-toggle",
            "b",
            self.editor_pref.period_save,
            self.on_period_save,
        )
        self.create_stateful_action(
            "check-spelling-toggle",
            "b",
            self.editor_pref.check_spelling,
            self.on_check_spelling,
        )

        action = SimpleAction.new("spell-lang", VariantType("s"))
        action.connect("activate", self.on_spell_lang)
        self.add_action(action)

        self.create_stateful_action(
            "use-spaces-toggle",
            "b",
            self.editor_pref.spaces_instead_of_tabs,
            self.on_use_spaces,
        )
        self.create_stateful_action(
            "tab-width",
            "i",
            self.editor_pref.tab_width,
            self.on_tab_width,
        )
        self.create_stateful_action(
            "auto-indent-toggle",
            "b",
            self.editor_pref.auto_indent,
            self.on_auto_indent,
        )
        self.create_stateful_action(
            "line-numbers-toggle",
            "b",
            self.editor_pref.line_numbers,
            self.on_line_numbers,
        )
        self.create_stateful_action(
            "right-margin-toggle",
            "b",
            self.editor_pref.right_margin,
            self.on_right_margin,
        )
        self.create_stateful_action(
            "right-margin-value",
            "d",
            self.editor_pref.right_margin_value,
            self.on_right_margin_value,
        )
        self.create_stateful_action(
            "current-line-toggle",
            "b",
            self.editor_pref.current_line,
            self.on_current_line,
        )
        self.create_stateful_action(
            "text-wrapping-toggle",
            "b",
            self.editor_pref.text_wrapping,
            self.on_text_wrapping,
        )
        self.create_stateful_action(
            "white-chars-toggle",
            "b",
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

    def on_period_save(self, action, param):
        """Save period save preferences."""
        period_save = not self.editor_pref.period_save
        self.editor_pref.period_save = period_save
        self.editor.set_period_save(period_save)
        self.preferences.save()

    def on_check_spelling(self, action, param):
        """Set spell check preferences."""
        check_spelling = not self.editor_pref.check_spelling
        self.editor_pref.check_spelling = check_spelling
        self.editor.set_check_spelling(
            check_spelling,
            self.editor_pref.spell_lang,
        )
        self.preferences.save()

    def on_spell_lang(self, action, param):
        """Save right spell lang preferences."""
        self.editor_pref.spell_lang = param.get_string()
        self.preferences.save()

    def on_use_spaces(self, action, param):
        """Save space vs tabs preferences."""
        use_spaces = not self.editor_pref.spaces_instead_of_tabs
        self.editor_pref.spaces_instead_of_tabs = use_spaces
        self.editor.set_spaces_instead_of_tabs(use_spaces)
        self.preferences.save()

    def on_tab_width(self, action, param):
        """Save tab width preferences."""
        width = param.get_int32()
        if width != self.editor_pref.tab_width:
            self.editor_pref.tab_width = width
            self.editor.source_view.set_tab_width(width)
            self.renderer.set_tab_width(width)
            self.preferences.save()

    def on_auto_indent(self, action, param):
        """Save auto indent preferences."""
        auto_indent = not self.editor_pref.auto_indent
        self.editor_pref.auto_indent = auto_indent
        self.editor.source_view.set_auto_indent(auto_indent)
        self.preferences.save()

    def on_line_numbers(self, action, param):
        """Save line number showing."""
        line_numbers = not self.editor_pref.line_numbers
        self.editor_pref.line_numbers = line_numbers
        self.editor.source_view.set_show_line_numbers(line_numbers)
        self.preferences.save()

    def on_right_margin(self, action, param):
        """Save right margin preferences."""
        right_margin = not self.editor_pref.right_margin
        self.editor_pref.right_margin = right_margin
        self.editor.source_view.set_show_right_margin(right_margin)
        self.preferences.save()

    def on_right_margin_value(self, action, param):
        """Save right margin value preferences."""
        margin_value = int(param.get_double())
        self.editor_pref.right_margin_value = margin_value
        self.editor.source_view.set_right_margin_position(margin_value)
        self.preferences.save()

    def on_current_line(self, action, param):
        """Save highlighting current file preferences."""
        current_line = not self.editor_pref.current_line
        self.editor_pref.current_line = current_line
        self.editor.source_view.set_highlight_current_line(current_line)
        self.preferences.save()

    def on_text_wrapping(self, action, param):
        """Save text wrapping mode preferences."""
        text_wrapping = not self.editor_pref.text_wrapping
        self.editor_pref.text_wrapping = text_wrapping
        self.editor.set_text_wrapping(text_wrapping)
        self.preferences.save()

    def on_white_chars(self, action, param):
        """Save showing white chars preferences."""
        white_chars = not self.editor_pref.white_chars
        self.editor_pref.white_chars = white_chars
        self.editor.set_white_chars(white_chars)
        self.preferences.save()
