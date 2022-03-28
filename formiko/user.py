from os import makedirs
from os.path import exists
from traceback import print_exc

from gi.repository.GLib import get_user_config_dir, get_user_cache_dir, \
        log_default_handler, LogLevelFlags
from gi.repository.Gtk import Orientation

try:
    from configparser import ConfigParser, NoSectionError, NoOptionError
except ImportError:
    from ConfigParser import ConfigParser, NoSectionError, NoOptionError


from formiko.renderer import PARSERS


class View():
    EDITOR = 1
    PREVIEW = 2
    BOTH = 3

    def __new__(cls, value):
        value = int(value)
        assert 0 < value < 4
        return value


def smart_bool(value):
    if value.lower() in ("1", "true", "yes", "on", "enable"):
        return True
    elif value.lower() in ("0", "false", "no", "off", "disable"):
        return False
    raise ValueError("%s is not boolean value" % value)


class SmartParser(ConfigParser):
    def smart_get(self, obj, key, conv=str, sec='main'):
        try:
            val = self.get(sec, key)
            setattr(obj, key, conv(val))
        except NoSectionError:
            pass
        except NoOptionError:
            pass
        except Exception:
            print_exc()

    def smart_set(self, obj, key, sec='main'):
        self.set(sec, key, str(getattr(obj, key)))


class EditorPreferences(object):
    period_save = True
    check_spelling = True
    spell_lang = ""
    spaces_instead_of_tabs = False
    tab_width = 8
    auto_indent = True
    line_numbers = True
    right_margin = True
    right_margin_value = 80
    current_line = False
    text_wrapping = True
    white_chars = False


class UserPreferences(object):
    preview = Orientation.HORIZONTAL.numerator
    auto_scroll = True
    parser = 'rst'
    writer = 'html4'
    style = ''
    custom_style = False
    editor = EditorPreferences()

    def __init__(self):
        self.load()

    def load(self):
        directory = get_user_config_dir()
        cp = SmartParser()
        cp.read("%s/formiko.ini" % directory)
        cp.smart_get(self, 'preview', int)
        cp.smart_get(self, 'auto_scroll', smart_bool)

        cp.smart_get(self, 'parser')
        if self.parser not in PARSERS:
            log_default_handler("Application", LogLevelFlags.LEVEL_WARNING,
                                "Unknow parser `%s' in config, set default."
                                % self.parser)
            self.parser = 'rst'
        cp.smart_get(self, 'writer')
        cp.smart_get(self, 'style')
        cp.smart_get(self, 'custom_style', smart_bool)

        cp.smart_get(self.editor, 'period_save', smart_bool, 'editor')
        cp.smart_get(self.editor, 'check_spelling', smart_bool, 'editor')
        cp.smart_get(self.editor, 'spell_lang', str, 'editor')
        cp.smart_get(self.editor, 'spaces_instead_of_tabs', smart_bool,
                     'editor')
        cp.smart_get(self.editor, 'tab_width', int, 'editor')
        cp.smart_get(self.editor, 'auto_indent', smart_bool, 'editor')
        cp.smart_get(self.editor, 'line_numbers', smart_bool, 'editor')
        cp.smart_get(self.editor, 'right_margin', smart_bool, 'editor')
        cp.smart_get(self.editor, 'right_margin_value', int, 'editor')
        cp.smart_get(self.editor, 'current_line', smart_bool, 'editor')
        cp.smart_get(self.editor, 'text_wrapping', smart_bool, 'editor')
        cp.smart_get(self.editor, 'white_chars', smart_bool, 'editor')

    def save(self):
        cp = SmartParser()
        cp.add_section('main')
        cp.set('main', 'preview', str(int(self.preview)))
        cp.smart_set(self, 'auto_scroll')

        cp.smart_set(self, 'parser')
        cp.smart_set(self, 'writer')
        cp.smart_set(self, 'style')
        cp.smart_set(self, 'custom_style')

        cp.add_section('editor')
        cp.smart_set(self.editor, 'period_save', 'editor')
        cp.smart_set(self.editor, 'check_spelling', 'editor')
        cp.smart_set(self.editor, 'spell_lang', 'editor')
        cp.smart_set(self.editor, 'spaces_instead_of_tabs', 'editor')
        cp.smart_set(self.editor, 'tab_width', 'editor')
        cp.smart_set(self.editor, 'auto_indent', 'editor')
        cp.smart_set(self.editor, 'line_numbers', 'editor')
        cp.smart_set(self.editor, 'right_margin', 'editor')
        cp.smart_set(self.editor, 'right_margin_value', 'editor')
        cp.smart_set(self.editor, 'current_line', 'editor')
        cp.smart_set(self.editor, 'text_wrapping', 'editor')
        cp.smart_set(self.editor, 'white_chars', 'editor')

        directory = get_user_config_dir()
        if not exists(directory):
            makedirs(directory)
        with open("%s/formiko.ini" % directory, 'w+') as fp:
            cp.write(fp)


class UserCache(object):
    width = 800
    height = 600
    paned = 400
    is_maximized = False
    view = View.BOTH

    def __init__(self):
        self.load()

    def load(self):
        directory = get_user_cache_dir()
        cp = SmartParser()
        cp.read("%s/formiko/window.ini" % directory)
        cp.smart_get(self, 'width', int)
        cp.smart_get(self, 'height', int)
        cp.smart_get(self, 'paned', int)
        cp.smart_get(self, 'is_maximized', smart_bool)
        cp.smart_get(self, 'view', View)

    def save(self):
        cp = SmartParser()
        cp.add_section('main')
        cp.set('main', 'width', str(self.width))
        cp.set('main', 'height', str(self.height))
        cp.set('main', 'paned', str(self.paned))
        cp.set('main', 'is_maximized', str(self.is_maximized))
        cp.set('main', 'view', str(self.view))

        directory = get_user_cache_dir()+"/formiko"
        if not exists(directory):
            makedirs(directory)
        with open("%s/window.ini" % directory, 'w+') as fp:
            cp.write(fp)
