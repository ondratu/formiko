# -*- coding: utf-8 -*-
from gi.repository.GdkPixbuf import Pixbuf

from os.path import exists, split, join
from sys import argv


def get_path():
    """Try to get path to formiko.svg"""
    bin_path = split(argv[0])[0]
    icons_path = "icons/formiko.svg"
    share_path = join("share/formiko", icons_path)
    while (bin_path != '/'):
        # this work to /opt /usr /usr/local prefixes
        if exists(join(bin_path, share_path)):
            return join(bin_path, share_path)
        if exists(join(bin_path, icons_path)):
            return join(bin_path, icons_path)
        bin_path = split(bin_path)[0]


ICON_PATH = get_path()

if ICON_PATH:
    icon_16 = Pixbuf.new_from_file_at_scale(ICON_PATH, 16, 16, True)
    icon_32 = Pixbuf.new_from_file_at_scale(ICON_PATH, 32, 32, True)
    icon_48 = Pixbuf.new_from_file_at_scale(ICON_PATH, 48, 48, True)
    icon_64 = Pixbuf.new_from_file_at_scale(ICON_PATH, 64, 64, True)
    icon_128 = Pixbuf.new_from_file_at_scale(ICON_PATH, 128, 128, True)
else:
    from gi.repository.Gtk import IconTheme
    from gi.repository.GLib import log_default_handler, LogLevelFlags

    log_default_handler("Application", LogLevelFlags.LEVEL_ERROR,
                        "Formiko icon not found", 0)
    icon_theme = IconTheme.get_default()
    icon_16 = icon_theme.load_icon("text-editor-symbolic", 16, 0)
    icon_32 = icon_theme.load_icon("text-editor-symbolic", 32, 0)
    icon_48 = icon_theme.load_icon("text-editor-symbolic", 48, 0)
    icon_64 = icon_theme.load_icon("text-editor-symbolic", 64, 0)
    icon_128 = icon_theme.load_icon("text-editor-symbolic", 128, 0)

icon_list = [icon_16, icon_32, icon_48, icon_64, icon_128]
