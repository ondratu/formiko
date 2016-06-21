
from gi import require_version
from gi.repository import Gdk

from sys import argv
from signal import signal, SIGINT

from formiko.application import Application


def handler_exit(*args):
    exit(1)


def main():
    signal(SIGINT, handler_exit)
    require_version('Gtk', '3.0')
    Gdk.threads_init()
    app = Application()
    return app.run(argv)


if __name__ == "__main__":
    exit(main())
