Formiko
=======

:author: Ondřej Tůma <mcbig@zeropage.cz>

Formiko is reStructuredText and MarkDown editor and live previewer. It is written in Python with Gtk3, GtkSourceView and Webkit. Use Docutils and recommonmark Common Mark parser.

Features:
---------
* GtkSourceView based editor with syntax highlighting
* possible use Vim editor
* vertical or horizontal window splitting
* preview mode

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
* Webkit
* GtkSourceView

recommended:
~~~~~~~~~~~~

* docutils - reStrucured support
* recommonmark - for Common Mark support

optionally:
~~~~~~~~~~~

* docutils-tinyhtmlwriter
* docutils-htmlwriter
* docutils-html5-writer
* vim-gtk or vim-gnome
