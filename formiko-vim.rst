formiko-vim
===========

:manual_section: 1
:manual_group: General Commands Manual
:date: 18 Jan 2018
:subtitle: reStructuredText and MarkDown editor and live previewer
:author: Ondřej Tůma (mcbig@zeropage.cz)
:version: 1.3.0

SYNOPSIS
~~~~~~~~

formiko-vim [options] [FILE]

DESCRIPTION
~~~~~~~~~~~
Formiko is reStructuredText and MarkDown editor and live previewer. It is
written in Python with Gtk3 and Webkit2. It use Docutils and
recommonmark Common Mark parser.

This version use Vim as editor.

At this moment, **this works only on X11 graphics backend**, because GtkSockets
not work on Wayland yet.

OPTIONS
~~~~~~~

-h, --help          Show help options

:FILE:  Specifies the file to open when formiko starts. If this is not
        specified, formiko will load a blank file with an "Untitled Document"
        label with ReStructuredText format.

FILES
~~~~~

~/.config/formiko.ini
  Your personal configuration file. Formiko store your options automatically
  when you make change.

~/.cache/formiko/window.ini
  Your personal cache file. Formiko store there values about window size and
  paned panels.

~/.cache/formiko/WebKitCache
  This is your WebKit preview cache.

BUGS
~~~~
If you find a bug, please report it at the GitHub issues tracker. See
https://github.com/ondratu/formiko/issues.

SEE ALSO
~~~~~~~~
vim(1)
