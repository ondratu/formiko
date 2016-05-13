
from gi import require_version
from gi.repository import Gdk

from sys import argv

from formiko.application import Application


def main():
    require_version('Gtk', '3.0')
    Gdk.threads_init()
    app = Application()
    return app.run(argv)

if __name__ == "__main__":
    exit(main())
