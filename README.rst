Formiko
=======

:author: Ondřej Tůma <mcbig@zeropage.cz>

Formiko is a reStructuredText and MarkDown editor and live previewer. It is
written in Python with Gtk4, GtkSourceView and WebKit. It uses Docutils and a
MarkDown-to-reStructuredText converter. If you want to **donate** to the
development, you can do so via the `paypal link <https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=4F4EJ3SV8JGYJ&item_name=Formiko+editor&currency_code=EUR&source=url>`_.

Features:
---------
* GtkSourceView based editor with syntax highlighting
* optional Vim editor support
* vertical or horizontal window splitting
* preview mode with auto scroll
* periodic save file
* json and html preview
* spell check
* linked file opening

It supports these parsers and writers:

* Docutils reStructuredText parser - https://www.docutils.org
* MarkDown to reStructuredText convertor (M2R2) -
  https://github.com/crossnox/m2r2
* Docutils HTML4, HTML5, S5/HTML slide show and PEP HTML writer -
  http://docutils.sourceforge.net
* Tiny HTML writer - https://github.com/ondratu/docutils-tinyhtmlwriter

Vim support
~~~~~~~~~~~
Formiko has Neovim editor support aka ``formiko-vim`` command. This runs `Neovim
<https://neovim.io/>`_ editor in Vte.Terminal.

Requirements:
-------------
* Python 3
* GTK 4
* gobject-introspection
* PyGObject
* WebKitGTK 6.x
* GtkSourceView 5.x
* libspelling 1.x
* gir files for all Gtk libraries
* vte - neovim support
* docutils - reStructuredText support
* jsonpath-ng - JSON Search path support

recommended:
~~~~~~~~~~~~
* m2r2 - converting MarkDown to reStructuredText
* Pygments - syntax color in html output code blocks
* docutils-tinyhtmlwriter - Tiny HTML Writer

**formiko-vim**:

* vte - Terminal emulator widget
* neovim - heavily refactored vim fork
* pynvim - Python3 library for scripting Neovim processes

development:
~~~~~~~~~~~~

* pygobject-stubs

Installation
------------

Flatpak
~~~~~~~
Formiko exists in the Flathub repository as cz.zeropage.Formiko. If you are new with
Flatpak, see `setup guide <https://flatpak.org/setup/>`_.

.. code:: sh

  # add Flathub repository as root
  flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

  # install Formiko as user
  flatpak install flathub cz.zeropage.Formiko

  # run Formiko
  flatpak run cz.zeropage.Formiko

Debian based
~~~~~~~~~~~~
Debian-based distributions sometimes use versions in package names. Here is an
example for the Debian Forky version. If you use a different version, your
gtksource or webkit2 may have a different version name.

.. code:: sh

    # python3, gtk4 etc are in dependencies
    apt install python3-pip python3-gi python3-docutils python3-jsonpath-ng \
                python3-pygments gir1.2-gtksource-5 gir1.2-webkit-6.0 \
                gir1.2-spelling-1 gir1.2-adw

    pip3 install formiko --break-system-packages

**Optionally**

    # languages
    apt install hunspell-en-us  # or other language you want

    # neovim
    apt install gir1.2-vte-3.91 neovim python3-pynvim

NetBSD
~~~~~~
**Broken at this moment - the WebKit with GTK4 and the libspelling packages are not available at this moment**

Installation process can be different for each BSD releases. It's about which
Python release is default. By this, you can change ``py313`` to your right
version.

NetBSD use pkgsrc, so some binaries are stored in ``/usr/pkg/bin`` directory.
Formiko call neovim directly. If you want to use neovim version with
pkgsrc, you must fix ``VIM_PATH`` variable in ``formiko/vim.py`` file.

.. code:: sh

    # python3.13 is in dependencies, as is gtk4
    pkgin install py313-pip py313-gobject3 py313-docutils gtksourceview5 \
                  libadwaita librsvg webkit-gtk
    pip3.6 install jsonpath-ng formiko

    # optionally
    pkgin install neovim pynvim
    pip3.6 install m2r2 docutils-tinyhtmlwriter

FreeBSD
~~~~~~~

Installation process can be different for each BSD releases. It's about which
Python release is default. By this, you can change ``py311`` to your right
version.

On FreeBSD you must install all these packages:

.. code:: sh

    pkg install py311-pygobject py311-docutils py311-pygments py311-pip \
        gtksourceview5 webkit2-gtk_60 libspelling py311-jsonpath-ng \
        libadwaita

    pip-3.11 install formiko



**Optionally**

.. code:: sh

    # MarkDown, and tiny writer support
    pip-3.11 install m2r2 docutils-tinyhtmlwriter

    # languages
    pkg install en-hunspell  # or other language you want

    # neovim
    pkg install vte3 neovim py311-pynvim py311-typing-extensions
