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


class UserPreferences(object):
    preview = Orientation.HORIZONTAL.numerator
    parser = 'rst'
    writer = 'html4'
    style = ''
    custom_style = False
    period_save = True
    spaces_instead_of_tabs = False
    tab_width = 8

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

        cp.smart_get(self, 'period_save', smart_bool, 'editor')
        cp.smart_get(self, 'spaces_instead_of_tabs', smart_bool, 'editor')
        cp.smart_get(self, 'tab_width', int, 'editor')

    def save(self):
        cp = SmartParser()
        cp.add_section('main')
        cp.set('main', 'preview', str(int(self.preview)))
        cp.set('main', 'parser', self.parser)
        cp.set('main', 'writer', self.writer)
        cp.set('main', 'style', self.style)
        cp.set('main', 'custom_style', str(self.custom_style))
        cp.add_section('editor')
        cp.set('editor', 'period_save', str(self.period_save))
        cp.set('editor', 'spaces_instead_of_tabs',
               str(self.spaces_instead_of_tabs))
        cp.set('editor', 'tab_width', str(self.tab_width))

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
        cp.read("%s/formiko.ini" % directory)
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
        with open("%s/formiko.ini" % directory, 'w+') as fp:
            cp.write(fp)
