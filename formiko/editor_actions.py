from gi.repository.Gio import SimpleActionGroup, SimpleAction
from gi.repository.GLib import VariantType, Variant


class EditorActionGroup(SimpleActionGroup):
    def __init__(self, editor, renderer, preferences):
        super(EditorActionGroup, self).__init__()
        self.editor = editor
        self.renderer = renderer
        self.preferences = preferences
        self.editor_pref = preferences.editor

        self.create_stateful_action(
            "period-save-toggle", 'b', self.editor_pref.period_save,
            self.on_period_save)
        self.create_stateful_action(
            "use-spaces-toggle", 'b', self.editor_pref.spaces_instead_of_tabs,
            self.on_use_spaces)
        self.create_stateful_action(
            "tab-width", 'i', self.editor_pref.tab_width, self.on_tab_width)
        self.create_stateful_action(
            "auto-indent-toggle", 'b', self.editor_pref.auto_indent,
            self.on_auto_indent)
        self.create_stateful_action(
            "line-numbers-toggle", 'b', self.editor_pref.line_numbers,
            self.on_line_numbers)
        self.create_stateful_action(
            "right-margin-toggle", 'b', self.editor_pref.right_margin,
            self.on_right_margin)

    def create_stateful_action(self, name, _type, default_value, method):
        action = SimpleAction.new_stateful(
            name, VariantType.new(_type),
            Variant(_type, default_value))
        action.connect("change-state", method)
        self.add_action(action)

    def on_period_save(self, action, param):
        period_save = not self.editor_pref.period_save
        self.editor_pref.period_save = period_save
        self.editor.set_period_save(period_save)
        self.preferences.save()

    def on_use_spaces(self, action, param):
        use_spaces = not self.editor_pref.spaces_instead_of_tabs
        self.editor_pref.spaces_instead_of_tabs = use_spaces
        self.editor.set_spaces_instead_of_tabs(use_spaces)
        self.preferences.save()

    def on_tab_width(self, action, param):
        width = param.get_int32()
        self.editor_pref.tab_width = width
        self.editor.source_view.set_tab_width(width)
        self.renderer.set_tab_width(width)
        self.preferences.save()

    def on_auto_indent(self, action, param):
        auto_indent = not self.editor_pref.auto_indent
        self.editor_pref.auto_indent = auto_indent
        self.editor.source_view.set_auto_indent(auto_indent)
        self.preferences.save()

    def on_line_numbers(self, action, param):
        line_numbers = not self.editor_pref.line_numbers
        self.editor_pref.line_numbers = line_numbers
        self.editor.source_view.set_show_line_numbers(line_numbers)
        self.preferences.save()

    def on_right_margin(self, action, param):
        right_margin = not self.editor_pref.right_margin
        self.editor_pref.right_margin = right_margin
        self.editor.source_view.set_show_right_margin(right_margin)
        self.preferences.save()
