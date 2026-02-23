"""Formiko module / main support."""

import sys
from contextlib import suppress
from signal import SIGINT, signal

from gi import require_version

require_version("Gtk", "4.0")
require_version("Gdk", "4.0")
require_version("Adw", "1")
require_version("GtkSource", "5")
require_version("Pango", "1.0")
require_version("WebKit", "6.0")

with suppress(ValueError):
    require_version("Spelling", "1")

with suppress(ValueError):
    require_version("Vte", "3.91")

# pylint: disable = wrong-import-position
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
    app = Application(application_id="cz.zeropage.Formiko.vim")
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
