Formiko
=======

:author: Ondřej Tůma <mcbig@zeropage.cz>

Formiko is reStructuredText and MarkDown editor and live previewer. It is
written in Python with Gtk3, GtkSourceView and Webkit2. Use Docutils and
recommonmark Common Mark parser. If you want to **donate** development, you
can do by `paypal link <https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=4F4EJ3SV8JGYJ&item_name=Formiko+editor&currency_code=EUR&source=url>`_.

Features:
---------
* GtkSourceView based editor with syntax highlighting
* possible use Vim editor
* vertical or horizontal window splitting
* preview mode with auto scroll
* periodic save file
* json and html preview
* spell check
* linked file opening

It support these parsers and writers:

* Docutils reStructuredText parser - http://docutils.sourceforge.net
* MarkDown to reStructuredText convertor (M2R) -
  https://github.com/miyakogi/m2r
* Common Mark parser - https://github.com/rtfd/recommonmark
* Docutils HTML4, S5/HTML slide show and PEP HTML writer -
  http://docutils.sourceforge.net
* Tiny HTML writer - https://github.com/ondratu/docutils-tinyhtmlwriter
* Yet another HTML writer - https://github.com/masayuko/docutils-htmlwriter
* HTML 5 writer - https://github.com/Kozea/docutils-html5-writer

Vim support
~~~~~~~~~~~
Formiko have Vim editor support aka ``formiko-vim`` command. This run `Vim
<https://vim.sourceforge.io/>`_ editor in GtkSocket. At this moment, this
socket work only on X11 backend, so this is not work on Wayland yet.

There is bug for GTK+:
  Bug `721224 <https://bugzilla.gnome.org/show_bug.cgi?id=721224>`_ - please
  add support for GtkSocket/GtkPlug in Wayland backend

Requirements:
-------------
* python 2.7 or 3
* GTK+3
* gobject-introspection
* PyGObject
* Webkit2 4.x
* GtkSourceView 3.x
* gir files for all Gtk libraries
* GtkSpell3
* docutils - reStrucured support

recommended:
~~~~~~~~~~~~
* m2r - converting MarkDown to reStructuredText
* recommonmark - for Common Mark support (MarkDown)
* Pygments - syntax color in html output code blocks

optionally:
~~~~~~~~~~~
**Python**:

* docutils-tinyhtmlwriter
* docutils-html5-writer

**System**:

* vim-gtk or vim-gnome for ``formiko-vim``

Installation
------------

Flatpak
~~~~~~~
Formiko exist in Flathub repository as cz.zeropage.Formiko. If you are new with
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
Debian based distributions use sometimes versions in package names. Here are
example for Debian Stretch version. If you use different version, your
gtksource or webkit2 could have another version name.

.. code:: sh

    # python3.5, gtk3, librsvg etc are in dependencies
    apt install python3-pip python3-gi python3-docutils gir1.2-gtksource-3.0 \
                gir1.2-webkit2-4.0 gir1.2-gtkspell3-3.0
    pip3 install formiko

    # optionaly
    apt install vim-gtk3
    pip3 install docutils-tinyhtmlwriter recommonmark docutils-html5-writer

**Formiko is in Debian and Ubuntu repository**. So you can install it standard
way.

NetBSD
~~~~~~
There is not GtkSpell3 on NetBSD, which is need for next 1.3.x version. So you
must use 1.2.x bug fix release.

Installation process can be different for each BSD releases. It's about which
Python release is default. By this, you can change ``pyXX`` to your right
version.

NetBSD use pkgsrc, so some binaries are stored in ``/usr/pkg/bin`` directory.
Formiko call vim and gvim directly. If you want to use vim version with
pkgsrc, you must fix ``VIM_PATH`` variable in ``formiko/vim.py`` file.

.. code:: sh

    # python3.6 is in dependecies as like gtk3
    pkgin install py36-pip py36-gobject3 py36-docutils gtksourceview3 \
                  librsvg webkit-gtk py36-pygments
    pip3.6 install formiko

    # optionaly
    pkgin install vim-gtk3
    pip3.6 install docutils-tinyhtmlwriter recommonmark docutils-html5-writer

FreeBSD
~~~~~~~
Installation process can be different for each BSD releases. It's about which
Python release is default. By this, you can change ``pyXX`` to your right
version.

On FreeBSD you must install all these packages:

.. code:: sh

    pkg install py37-gobject3 py37-docutils py37-pygments py37-pip \
        gtksourceview3 webkit2-gtk3 gtkspell3 gobject-introspection \
        librsvg2 adwaita-icon-theme

**Optionaly**

.. code:: sh

    pkg install en-hunspell  # or other language you want
    pip-3.7 install docutils-tinyhtmlwriter docutils-html5-writer m2r
