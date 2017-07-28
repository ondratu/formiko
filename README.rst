Formiko
=======

:author: Ondřej Tůma <mcbig@zeropage.cz>

Formiko is reStructuredText and MarkDown editor and live previewer. It is
written in Python with Gtk3, GtkSourceView and Webkit2. Use Docutils and
recommonmark Common Mark parser.

Features:
---------
* GtkSourceView based editor with syntax highlighting
* possible use Vim editor
* vertical or horizontal window splitting
* preview mode
* periodic save file
* json and html preview

It support these parsers and writers:

* Docutils reStructuredText parser - http://docutils.sourceforge.net
* Common Mark parser - https://github.com/rtfd/recommonmark
* Docutils HTML4, S5/HTML slide show and PEP HTML writer - http://docutils.sourceforge.net
* Tiny HTML writer - https://github.com/ondratu/docutils-tinyhtmlwriter
* Yet another HTML writer - https://github.com/masayuko/docutils-htmlwriter
* HTML 5 writer - https://github.com/Kozea/docutils-html5-writer

Requirements:
-------------
* python 2.7 or 3
* GTK+3
* gobject-introspection
* PyGObject
* Webkit2 4.x
* GtkSourceView 3.x
* gir files for all Gtk libraries

recommended:
~~~~~~~~~~~~

* docutils - reStrucured support
* recommonmark - for Common Mark support (MarkDown)
* Pygments - syntax color in html output code blocks

optionally:
~~~~~~~~~~~
**Python**:

* docutils-tinyhtmlwriter
* docutils-htmlwriter
* docutils-html5-writer

**System**:

* vim-gtk or vim-gnome

Installation
------------

Debian
~~~~~~
Debian use sometimes versions in package names. Here are in Stretch version.
If you use different version, your gtksource or webkit2 could have another
version name.

.. code:: sh

    # python3.5, gtk3, librsvg etc are in dependencies
    apt install python3-pip python3-gi python3-docutils gir1.2-gtksource-3.0 \
                gir1.2-webkit2-4.0
    pip3 install formiko

    # optionaly
    apt install vim-gtk3
    pip3 install docutils-tinyhtmlwriter recommonmark docutils-html5-writer

NetBSD
~~~~~~
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
