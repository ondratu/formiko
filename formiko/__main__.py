"""Formiko module / main support."""

import faulthandler
import os
import sys
from contextlib import suppress
from signal import SIGINT, signal

# A crash inside a native dependency (GTK, litehtml, cairo, ...) would
# otherwise just vanish - there's no console attached to a --windowed
# frozen build. This dumps the Python-level stack of whichever call was
# in progress to stderr, which at least identifies it even though the
# fault itself is outside Python's own control.
faulthandler.enable()

if sys.platform == "win32" and getattr(sys, "frozen", False):
    # MSYS2's GTK4/Pango stack uses the fontconfig/FreeType backend rather
    # than native DirectWrite, libadwaita/GTK look up the
    # org.gnome.desktop.interface GSettings schema internally even on
    # Windows (an unknown schema is a fatal GLib error, not a warning),
    # and GtkSourceView looks up the RelaxNG schemas it validates its
    # language files against as real files under share/gtksourceview-5/.
    # None of these has a "look next to the exe" fallback on Windows, so
    # point them at the copies bundled alongside the frozen app (see
    # build-windows-installer.yml's "Stage runtime files" step) before
    # anything - including gi's own typelib loading - can touch them.
    _bundle_dir = sys._MEIPASS  # noqa: SLF001
    os.environ.setdefault(
        "FONTCONFIG_PATH", os.path.join(_bundle_dir, "fontconfig"),
    )
    os.environ.setdefault(
        "GSETTINGS_SCHEMA_DIR", os.path.join(_bundle_dir, "glib-schemas"),
    )
    os.environ.setdefault(
        "XDG_DATA_DIRS", os.path.join(_bundle_dir, "share"),
    )

from gi import require_version  # noqa: E402

require_version("Gtk", "4.0")
require_version("Gdk", "4.0")
require_version("Adw", "1")
require_version("GtkSource", "5")
require_version("Pango", "1.0")
# WebKit's version is required by formiko.webkit_browser, the concrete
# BrowserView backend, so a future non-WebKit backend doesn't force it.

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
