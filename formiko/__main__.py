"""Formiko module / main support."""
import sys
from signal import SIGINT, signal

from gi import require_version

require_version("Gdk", "3.0")
require_version("Gtk", "3.0")
require_version("GtkSource", "3.0")
require_version("Pango", "1.0")
require_version("GtkSpell", "3.0")

try:
    require_version("WebKit2", "4.1")
except ValueError:
    require_version("WebKit2", "4.0")

# pylint: disable = wrong-import-position
from gi.repository import Gdk  # noqa: E402

from formiko.application import Application  # noqa: E402


def handler_exit(*_):
    """Signal handler."""
    sys.exit(1)


def main():
    """Snadard main function."""
    signal(SIGINT, handler_exit)
    app = Application()
    return app.run(sys.argv)


def main_vim():
    """Extra main for vim version."""
    signal(SIGINT, handler_exit)
    Gdk.threads_init()
    app = Application(application_id="cz.zeropage.Formiko.vim")
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
