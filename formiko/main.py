from gi import require_version

require_version('Gdk', '3.0')   # noqa
require_version('Gtk', '3.0')   # noqa

from gi.repository import Gdk

from sys import argv
from signal import signal, SIGINT

from formiko.application import Application


def handler_exit(*args):
    exit(1)


def main():
    signal(SIGINT, handler_exit)
    Gdk.threads_init()
    app = Application()
    return app.run(argv)


def main_vim():
    signal(SIGINT, handler_exit)
    Gdk.threads_init()
    app = Application(application_id="cz.zeropage.formiko.vim")
    return app.run(argv)


if __name__ == "__main__":
    exit(main())
