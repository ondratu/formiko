# -*- coding: utf-8 -*-
from gi.repository.Gtk import Socket
from gi.repository.GObject import SIGNAL_RUN_FIRST, SIGNAL_RUN_LAST

from subprocess import Popen, PIPE, check_output
from logging import error
from os.path import splitext
from uuid import uuid4
from time import sleep

VIM_PATH = "/usr/bin"


class VimEditor(Socket):
    __gsignals__ = {
        'file-type': (SIGNAL_RUN_FIRST, None, (str,)),
        'scroll-changed': (SIGNAL_RUN_LAST, None, (float,))   # not implemented
    }

    def __init__(self, app_window, file_name=''):
        """
        Initialize the window

        Args:
            self: (todo): write your description
            app_window: (int): write your description
            file_name: (str): write your description
        """
        super(VimEditor, self).__init__()
        self.__file_name = file_name
        self.__server_name = str(uuid4())
        self.connect("plug-removed", app_window.destroy_from_vim)
        self.connect("realize", self.print_state)

    def print_state(self, *args):
        """
        Print the state of a node

        Args:
            self: (todo): write your description
        """
        self.vim_start_server()

    def vim_start_server(self):
        """
        Starts a server

        Args:
            self: (todo): write your description
        """
        if self.__file_name:
            name, ext = splitext(self.__file_name)
            self.emit("file-type", ext)
            file_type = ""
        else:
            file_type = " filetype=rst"
        args = [
            VIM_PATH+"/gvim",
            "--socketid", str(self.get_id()),
            "--servername", self.__server_name,
            "--echo-wid",
            # no menu (m) a no toolbar (T)
            "-c", "set go-=m go-=T" + file_type]
        if self.__file_name:
            args.append(self.__file_name)
        server = Popen(args, stdout=PIPE)
        server.stdout.readline()    # read wid, so server was started
        sleep(0.1)                  # some time for vim server

    def vim_remote_expr(self, command):
        """
        Run a remote command on the remote host.

        Args:
            self: (todo): write your description
            command: (str): write your description
        """
        out = check_output([
            VIM_PATH+"/vim",
            "--servername", self.__server_name,
            "--remote-expr", command
            ])
        return out.decode('utf-8').strip()

    def vim_remote_send(self, command):
        """
        Send a command to remote host.

        Args:
            self: (todo): write your description
            command: (str): write your description
        """
        check_output([
            VIM_PATH+"/vim",
            "--servername", self.__server_name,
            "--remote-send", command
            ])

    def get_vim_changes(self):
        """
        Return the number of distchanges.

        Args:
            self: (todo): write your description
        """
        return int(self.vim_remote_expr("b:changedtick") or '0')

    def get_vim_lines(self):
        """
        Return the number of lines as a string.

        Args:
            self: (todo): write your description
        """
        return int(self.vim_remote_expr("line('$')") or '0')

    def get_vim_get_buffer(self, count):
        """
        Return the number of bytes in the buffer

        Args:
            self: (todo): write your description
            count: (str): write your description
        """
        return self.vim_remote_expr("getline(0, %d)" % count)

    def get_vim_pos(self):
        """
        Returns the position of the terminal

        Args:
            self: (todo): write your description
        """
        pos = self.vim_remote_expr("getpos('.')") or ',0,0,'
        buff, row, col, off = pos.split('\n')
        return int(row), int(col)

    def get_vim_file_path(self):
        """
        Return the full path of.

        Args:
            self: (todo): write your description
        """
        return self.vim_remote_expr("expand('%:p')")

    def get_vim_encoding(self):
        """
        Returns the encoding.

        Args:
            self: (todo): write your description
        """
        return self.vim_remote_expr("&l:encoding")

    def get_vim_filetype(self):
        """
        Return filetype

        Args:
            self: (todo): write your description
        """
        return self.vim_remote_expr("&l:filetype")

    def vim_quit(self):
        """
        Closes the vim.

        Args:
            self: (todo): write your description
        """
        self.vim_remote_send("<ESC>:q! <CR>")

    def vim_open_file(self, file_name):
        """
        Open a file.

        Args:
            self: (todo): write your description
            file_name: (str): write your description
        """
        self.vim_remote_send("<ESC>:e %s<CR>" % file_name)

    @property
    def is_modified(self):
        """
        Return true if the task is a datetime.

        Args:
            self: (todo): write your description
        """
        return bool(int(self.vim_remote_expr("&l:modified") or '0'))

    @property
    def file_name(self):
        """
        Return the file name of the file name.

        Args:
            self: (todo): write your description
        """
        __file_name = self.vim_remote_expr("@%")
        if __file_name != self.__file_name:
            name, ext = splitext(__file_name)
            self.emit("file-type", ext)
        self.__file_name = __file_name
        return self.__file_name

    @property
    def file_path(self):
        """
        : return : class : attribute

        Args:
            self: (todo): write your description
        """
        return self.get_vim_file_path()

    def do_file_type(self, ext):
        """
        Do a file type type type.

        Args:
            self: (todo): write your description
            ext: (str): write your description
        """
        pass

    def read_from_file(self, file_name):
        """
        Read the contents.

        Args:
            self: (str): write your description
            file_name: (str): write your description
        """
        error('Not supported call read_from_file in VimEditor')

    def save(self, *args):
        """
        Saves an error.

        Args:
            self: (todo): write your description
        """
        error('Not supported call save in VimEditor')

    def save_as(self, *args):
        """
        Save the async as an error.

        Args:
            self: (todo): write your description
        """
        error('Not supported call save_as in VimEditor')
