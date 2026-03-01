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

from formiko.dialogs import TraceBackDialog
from formiko.widgets import ImutableDict

VIM_PATH = "/usr/bin"


class VimEditor(Vte.Terminal):
    """NeoVim widget based on VTE."""

    __gsignals__ = ImutableDict(
        {
            "file-type": (SIGNAL_RUN_FIRST, None, (str,)),
            "scroll-changed": (
                SIGNAL_RUN_LAST,
                None,
                (float,),
            ),  # not implemented
        },
    )

    nvim: pynvim.Nvim
    _nvim_alive: bool = False

    def __init__(self, app_window, file_name=""):
        super().__init__()
        self.__win = app_window
        self.__file_name = file_name
        self._uuid = "/tmp/.formiko." + str(uuid4())  # noqa: S108
        self.connect("child-exited", self._on_nvim_exited)
        self.connect("child-exited", app_window.destroy_from_vim)
        self.connect("realize", self.start_server)

    def _on_nvim_exited(self, *_):
        """Mark the Neovim connection as dead when the process exits."""
        self._nvim_alive = False

    def start_server(self, *_):
        """Start neovim server and put it into terminal."""
        file_type = ""
        if self.__file_name:
            _, ext = splitext(self.__file_name)
            self.emit("file-type", ext)
        else:
            file_type = "rst"

        args = [VIM_PATH + "/nvim", "--listen", self._uuid]
        if self.__file_name:
            args.append(self.__file_name)

        try:
            _, _pid = self.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                None,
                args,
                None,
                GLib.SpawnFlags.DEFAULT,
            )
        except GLib.Error as error:
            dialog = TraceBackDialog(self.__win, str(error))
            dialog.present()
            return

        while not exists(self._uuid):
            sleep(0.1)
        self.nvim = pynvim.attach("socket", path=self._uuid)
        self._nvim_alive = True
        if file_type:
            self.vim_remote_send(":set filetype=" + file_type)

    def _nvim_call(self, fn, default=None):
        """Call a pynvim callable; return *default* if Neovim has exited."""
        if not self._nvim_alive:
            return default
        try:
            return fn()
        except EOFError:
            self._nvim_alive = False
            return default

    def vim_remote_expr(self, command):
        """Do expresion on vim server and return value."""
        return self._nvim_call(lambda: self.nvim.eval(command))

    def vim_remote_send(self, command):
        """Call command on vim server."""
        self._nvim_call(lambda: self.nvim.command(command))

    def get_vim_changes(self):
        """Retun number of changes in vim."""
        return self.vim_remote_expr("b:changedtick") or 0

    def get_vim_lines(self):
        """Return number of lines in vim."""
        return self.vim_remote_expr("line('$')") or 0

    def get_vim_get_buffer(self, count):
        """Retun text from vim."""
        buff = self.vim_remote_expr(f"getline(0, {count})")
        return "\n".join(buff)

    def get_vim_pos(self):
        """Return cursor position in vim."""
        pos = self.vim_remote_expr("getpos('.')") or [0, 0, 0, 0]
        _buff, row, col, _off = pos
        return row, col

    def get_vim_scroll_pos(self, total_lines):
        """Return scroll position based on cursor row as a fraction (0.0-1.0).

        Uses the cursor row so the preview tracks vertical position in the
        document without flickering on each keystroke within a line.
        """
        row, _ = self.get_vim_pos()
        return (row - 1) / max(total_lines - 1, 1)

    def get_vim_file_path(self):
        """Return file path from vim."""
        return self.vim_remote_expr("expand('%:p')") or self.__file_name

    def get_vim_encoding(self):
        """Return vim encoding."""
        return self.vim_remote_expr("&l:encoding")

    def get_vim_filetype(self):
        """Return file type of file from vim."""
        return self.vim_remote_expr("&l:filetype")

    def vim_quit(self):
        """Quit the vim."""
        self._nvim_call(lambda: self.nvim.quit())

    @property
    def is_modified(self):
        """Return true if file in vim is modified."""
        return bool(self.vim_remote_expr("&l:modified") or 0)

    @property
    def file_name(self):
        """Return file openned in vim."""
        __file_name = self.vim_remote_expr("@%")
        if __file_name != self.__file_name:
            _, ext = splitext(__file_name)
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
        """Open a file in Neovim."""
        self.__file_name = file_name
        _, ext = splitext(file_name)
        self.emit("file-type", ext)
        self._nvim_call(lambda: self.nvim.command("e " + file_name))

    def save(self, _):
        """Log error, save is not supported."""
        error("Not supported call save in VimEditor")

    def save_as(self, *_):
        """Log error, save as is not supported."""
        error("Not supported call save_as in VimEditor")
