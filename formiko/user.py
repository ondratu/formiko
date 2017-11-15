from gi.repository.GLib import get_user_config_dir, get_user_cache_dir
from gi.repository.Gtk import Orientation

try:
    from configparser import ConfigParser, NoSectionError, NoOptionError
except:
    from ConfigParser import ConfigParser, NoSectionError, NoOptionError

from os import makedirs
from os.path import exists
from traceback import print_exc


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
    text_wrapping = True


class UserPreferences(object):
    preview = Orientation.HORIZONTAL.numerator
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
        cp.smart_get(self, 'parser')
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
        cp.smart_get(self.editor, 'text_wrapping', smart_bool, 'editor')

    def save(self):
        cp = SmartParser()
        cp.add_section('main')
        cp.set('main', 'preview', str(int(self.preview)))
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
        cp.smart_set(self.editor, 'text_wrapping', 'editor')

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

    def save(self):
        cp = SmartParser()
        cp.add_section('main')
        cp.set('main', 'width', str(self.width))
        cp.set('main', 'height', str(self.height))
        cp.set('main', 'paned', str(self.paned))
        cp.set('main', 'is_maximized', str(self.is_maximized))

        directory = get_user_cache_dir()
        if not exists(directory):
            makedirs(directory)
        with open("%s/formiko/window.ini" % directory, 'w+') as fp:
            cp.write(fp)
