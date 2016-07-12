# -*- coding: utf-8 -*-
from gi.repository.GdkPixbuf import Pixbuf

from os import makedirs


def main():
    for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        icon = Pixbuf.new_from_file_at_scale("formiko.svg", size, size, True)
        makedirs("%dx%d" % (size, size))
        icon.savev("%dx%d/formiko.png" % (size, size), "png", [], [])


if __name__ == "__main__":
    main()
