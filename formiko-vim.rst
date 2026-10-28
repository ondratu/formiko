formiko-vim
===========

:manual_section: 1
:manual_group: General Commands Manual
:date: 18 Jan 2018
:subtitle: reStructuredText and MarkDown editor and live previewer
:author: Ondřej Tůma (mcbig@zeropage.cz)
:version: {version}

SYNOPSIS
~~~~~~~~

formiko-vim [options] [FILE]

DESCRIPTION
~~~~~~~~~~~
Formiko is reStructuredText and MarkDown editor and live previewer. It is
written in Python with GTK 4, libadwaita and WebKit 6.0. It use Docutils
for reStructuredText and optionally m2r2 or mistune for MarkDown.

This version use Neovim embedded in a terminal widget as editor.

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
