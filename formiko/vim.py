"""GTK widget based on gvim.

This widget is deprecated, and it not work well on new platform. Modern
solution have to be based on nvim and it's protocol.
"""
from logging import error
from os.path import exists, splitext
from time import sleep
from uuid import uuid4

import pynvim
from gi.repository import GLib, Vte
from gi.repository.GObject import SIGNAL_RUN_FIRST, SIGNAL_RUN_LAST

from formiko.widgets import ImutableDict

VIM_PATH = "/usr/bin"


class VimEditor(Vte.Terminal):
    """NeoVim widget based on VTE."""

    __gsignals__ = ImutableDict({
        "file-type": (SIGNAL_RUN_FIRST, None, (str,)),
        "scroll-changed": (SIGNAL_RUN_LAST, None, (float,)),  # not implemented
        })

    nvim: pynvim.Nvim

    def __init__(self, app_window, file_name=""):
        super().__init__()
        self.__file_name = file_name
        self._uuid = "/tmp/.formiko."+str(uuid4())  # noqa: S108
        self.connect("child-exited", app_window.destroy_from_vim)
        self.connect("realize", self.start_server)

    def start_server(self, *_):
        """Start neovim server and put it into terminal."""
        file_type = ""
        if self.__file_name:
            name, ext = splitext(self.__file_name)
            self.emit("file-type", ext)
        else:
            file_type = "rst"

        args = [VIM_PATH+"/nvim", "--listen", self._uuid]
        if self.__file_name:
            args.append(self.__file_name)

        success, pid = self.spawn_sync(
            Vte.PtyFlags.DEFAULT,
            None,
            args,
            None,
            GLib.SpawnFlags.DEFAULT,
        )
        while not exists(self._uuid):
            sleep(0.1)
        self.nvim = pynvim.attach("socket", path=self._uuid)
        if file_type:
            self.vim_remote_send(":set filetype="+file_type)

    def vim_remote_expr(self, command):
        """Do expresion on vim server and return value."""
        return self.nvim.eval(command)

    def vim_remote_send(self, command):
        """Call command on vim server."""
        self.nvim.command(command)

    def get_vim_changes(self):
        """Retun number of changes in vim."""
        return self.vim_remote_expr("b:changedtick") or 0

    def get_vim_lines(self):
        """Return number of lines in vim."""
        return self.vim_remote_expr("line('$')") or 0

    def get_vim_get_buffer(self, count):
        """Retun text from vim."""
        buff = self.vim_remote_expr("getline(0, %d)" % count)
        return "\n".join(buff)

    def get_vim_pos(self):
        """Return cursor position in vim."""
        pos = self.vim_remote_expr("getpos('.')") or [0, 0, 0, 0]
        buff, row, col, off = pos
        return row, col

    def get_vim_file_path(self):
        """Return file path from vim."""
        return self.vim_remote_expr("expand('%:p')")

    def get_vim_encoding(self):
        """Return vim encoding."""
        return self.vim_remote_expr("&l:encoding")

    def get_vim_filetype(self):
        """Return file type of file from vim."""
        return self.vim_remote_expr("&l:filetype")

    def vim_quit(self):
        """Quit the vim."""
        self.nvim.quit()

    @property
    def is_modified(self):
        """Return true if file in vim is modified."""
        return bool(self.vim_remote_expr("&l:modified") or 0)

    @property
    def file_name(self):
        """Return file openned in vim."""
        __file_name = self.vim_remote_expr("@%")
        if __file_name != self.__file_name:
            name, ext = splitext(__file_name)
            self.emit("file-type", ext)
        self.__file_name = __file_name
        return self.__file_name

    @property
    def file_path(self):
        """Return file path in vim."""
        return self.get_vim_file_path()

    def do_file_type(self, ext):
        """Do nothing - just compatible interface."""

    def read_from_file(self, file_name):
        """Log error, read_from_file is not supported."""
        error("Not supported call read_from_file in VimEditor")

    def save(self, *args):
        """Log error, save is not supported."""
        error("Not supported call save in VimEditor")

    def save_as(self, *args):
        """Log error, save as is not supported."""
        error("Not supported call save_as in VimEditor")
