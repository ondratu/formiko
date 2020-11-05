from gi import require_version

require_version('Gdk', '3.0')   # noqa
require_version('Gtk', '3.0')   # noqa

from gi.repository import Gdk

from sys import argv
from signal import signal, SIGINT

from formiko.application import Application


def handler_exit(*args):
    """
    Handler for exit.

    Args:
    """
    exit(1)


def main():
    """
    Main entry point.

    Args:
    """
    signal(SIGINT, handler_exit)
    app = Application()
    return app.run(argv)


def main_vim():
    """
    Run the application.

    Args:
    """
    signal(SIGINT, handler_exit)
    Gdk.threads_init()
    app = Application(application_id="cz.zeropage.Formiko.vim")
    return app.run(argv)


if __name__ == "__main__":
    exit(main())
