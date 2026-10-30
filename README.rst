Formiko
=======

:author: Ondřej Tůma <mcbig@zeropage.cz>
:contributors: `The Formiko Team <https://github.com/ondratu/formiko/blob/master/formiko/data/AUTHORS>`_

Formiko is a reStructuredText and MarkDown editor and live previewer. It is
written in Python with Gtk4, GtkSourceView and WebKit. It uses Docutils and a
MarkDown-to-reStructuredText converter. If you want to **donate** to the
development, you can do so via the `paypal link <https://www.paypal.com/ncp/payment/E7Z8JVT3ZCETJ>`__.

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
* `EditorConfig <https://editorconfig.org/>`__ support

It supports these parsers and writers:

* Docutils reStructuredText parser - https://www.docutils.org
* MarkDown to reStructuredText converter (M2R2) -
  https://github.com/crossnox/m2r2
* Docutils HTML4, HTML5, S5/HTML slide show and PEP HTML writer -
  http://docutils.sourceforge.net
* Tiny HTML writer - https://github.com/ondratu/docutils-tinyhtmlwriter

EditorConfig
~~~~~~~~~~~~
Formiko reads the ``.editorconfig`` files that apply to the opened file. The
settings are used for that document only and are never written to the user
preferences. They can be turned off with *Use .editorconfig* in the status bar
Editor menu.

* ``indent_style``, ``indent_size``, ``tab_width`` - indentation
* ``max_line_length`` - position of the right margin
* ``charset`` - encoding of the file (``latin1``, ``utf-8``, ``utf-8-bom``,
  ``utf-16be``, ``utf-16le``)
* ``end_of_line`` - line endings (``lf``, ``cr``, ``crlf``)
* ``trim_trailing_whitespace``, ``insert_final_newline`` - applied when the
  file is saved

Without ``charset`` and ``end_of_line`` a file keeps the encoding and line
endings it was opened with. Be careful with ``trim_trailing_whitespace`` in
MarkDown: two trailing spaces are a line break there, so use
``trim_trailing_whitespace = false`` in a ``[*.md]`` section.

Custom directives
~~~~~~~~~~~~~~~~~
Formiko registers additional directives that are available in both
reStructuredText and MarkDown (via M2R2) documents.

``.. file-tree:: <path>``
  Renders a directory tree rooted at *path* (relative to the source file)
  as a bullet list.

  Options:

  ``:depth: <n>``
    Maximum display depth. Default is ``2``.
  ``:include: <pattern>``
    Show only files matching the glob pattern (e.g. ``*.md``).
    Directories with no matching files are hidden automatically.
  ``:exclude: <pattern>``
    Hide files matching the glob pattern. Applied after ``:include:``.
  ``:links:``
    Turn file names into hyperlinks pointing to the files,
    with paths relative to the source document.

  Example::

    .. file-tree:: docs
       :depth: 3
       :include: *.rst
       :links:

``.. mdinclude:: <file>``
  Includes a Markdown file and converts it to reStructuredText inline.
  Requires `m2r2 <https://github.com/crossnox/m2r2>`_. The directive is
  intended for Markdown files, but works in RST documents as well.

  Options:

  ``:start-line: <n>``
    Start reading the file from line *n*.
  ``:end-line: <n>``
    Stop reading the file at line *n*.

  Example::

    .. mdinclude:: CONTRIBUTING.md
       :start-line: 3

Task lists
~~~~~~~~~~
A list item starting with a marker in square brackets is rendered with a plain
Unicode symbol instead, so it looks the same in every writer and needs no CSS.
It works in reStructuredText and MarkDown (via M2R2) documents, in bullet and
numbered lists. The set of markers follows Obsidian and its themes. Markers
are case sensitive, except ``[X]``, which is the same as ``[x]``. Each item
also gets a ``task-<name>`` class and its list gets the ``task-list`` class.

Example::

  * [x] done
  * [ ] to do
  * [?] question

.. list-table::
   :header-rows: 1
   :widths: 20 40 20

   * - Marker
     - Meaning
     - Symbol
   * - ``[ ]``
     - to do
     - ☐
   * - ``[x]`` ``[X]``
     - done
     - ☑
   * - ``[/]``
     - incomplete
     - ◐
   * - ``[-]``
     - canceled
     - ☒
   * - ``[>]``
     - forwarded
     - ➔
   * - ``[<]``
     - scheduling
     - ◷
   * - ``[?]``
     - question
     - ⁇
   * - ``[!]``
     - important
     - ‼
   * - ``[*]``
     - star
     - ★
   * - ``["]``
     - quote
     - ❝
   * - ``[l]``
     - location
     - ⌖
   * - ``[b]``
     - bookmark
     - ⚑
   * - ``[i]``
     - information
     - ⓘ
   * - ``[I]``
     - idea
     - ✦
   * - ``[$]`` ``[S]``
     - money
     - $
   * - ``[€]``
     - money
     - €
   * - ``[p]``
     - pros
     - ⊕
   * - ``[c]``
     - cons
     - ⊖
   * - ``[f]``
     - fire
     - ♨
   * - ``[k]``
     - key
     - ⚿
   * - ``[w]``
     - win
     - ✪
   * - ``[u]``
     - up
     - ▲
   * - ``[d]``
     - down
     - ▼

Vim support
~~~~~~~~~~~
Formiko has Neovim editor support aka ``formiko-vim`` command. This runs `Neovim
<https://neovim.io/>`_ editor in Vte.Terminal.

WakaTime support
~~~~~~~~~~~~~~~~
Formiko can report your writing activity to `WakaTime <https://wakatime.com>`_.
It is off by default; enable it in Preferences and paste in your WakaTime API
key to turn it on. Once enabled, Formiko sends heartbeats to wakatime.com
whenever you open, edit, save or read a document, so your time is tracked
per project on your WakaTime dashboard.

To get your API key, log in to wakatime.com and see
`Get your API key <https://wakatime.com/settings/api-key>`_.

In ``formiko-vim``, editing itself is tracked by neovim's own
`vim-wakatime <https://github.com/wakatime/vim-wakatime>`_ plugin, not by
Formiko's Preferences setting, and needs to be configured separately inside
your neovim config. Formiko's own WakaTime setting still covers the live
preview pane in that mode.

Requirements:
-------------
* Python 3.11+
* GTK 4
* gobject-introspection
* PyGObject
* WebKitGTK 6.x
* GtkSourceView 5.x
* gir files for all Gtk libraries
* docutils - reStructuredText support
* jsonpath-ng - JSON Search path support
* editorconfig - EditorConfig support (editorconfig-core-py)

recommended:
~~~~~~~~~~~~
* m2r2 - converting MarkDown to reStructuredText
* Pygments - syntax color in html output code blocks
* libspelling 1.x - spell checking
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

On Debian based distributions you must install all these packages:

.. code:: sh

    # python3, gtk4 etc are in dependencies
    apt install python3-pip python3-gi python3-docutils python3-jsonpath-ng \
                python3-editorconfig gir1.2-gtksource-5 gir1.2-webkit-6.0 \
                gir1.2-adw

    pip3 install formiko --break-system-packages

**Optionally**

.. code:: sh

    # syntax highlighting in code blocks
    apt install python3-pygments

    # spell checking
    apt install gir1.2-spelling-1

    # languages
    apt install hunspell-en-us  # or other language you want

    # MarkDown, and tiny writer support
    pip3 install m2r2 docutils-tinyhtmlwriter --break-system-packages

    # neovim
    apt install gir1.2-vte-3.91 neovim python3-pynvim

NetBSD
~~~~~~
Installation process can be different for each NetBSD releases. It's about which
Python release is default. By this, you can change ``py313`` to your right
version.

On NetBSD you must install all these packages:

.. code:: sh

    # python3.13 is in dependencies, as is gtk4
    pkgin install py313-pip py313-gobject3 py313-docutils gtksourceview5 \
                  libadwaita librsvg webkit-gtk60 adwaita-icon-theme

    pip3.13 install jsonpath-ng editorconfig formiko

**Optionally**

.. code:: sh

    # syntax highlighting in code blocks
    pkgin install py313-pygments

    # spell checking
    pkgin install libspelling

    # languages
    pkgin install en-hunspell  # or other language you want

    # MarkDown, and tiny writer support
    pip3.13 install m2r2 docutils-tinyhtmlwriter

.. note:: ``formiko-vim`` is not available on NetBSD, because ``vte`` with GTK4
          support is not available in pkgsrc, so neovim cannot be embedded.

FreeBSD
~~~~~~~

Installation process can be different for each BSD releases. It's about which
Python release is default. By this, you can change ``py311`` to your right
version.

On FreeBSD you must install all these packages:

.. code:: sh

    pkg install py312-pygobject py312-docutils py312-pygments py312-pip \
        gtksourceview5 webkit2-gtk_60 libspelling py312-jsonpath-ng \
        libadwaita

    pip-3.12 install formiko



**Optionally**

.. code:: sh

    # MarkDown, and tiny writer support
    pip-3.12 install m2r2 docutils-tinyhtmlwriter

    # languages
    pkg install en-hunspell  # or other language you want

    # neovim
    pkg install vte3 neovim py312-pynvim py312-typing-extensions
