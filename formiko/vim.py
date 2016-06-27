# -*- coding: utf-8 -*-
from gi.repository.Gtk import Socket
from gi.repository.GObject import SIGNAL_RUN_FIRST

from subprocess import Popen, PIPE, check_output
from logging import error
from os.path import splitext


class VimEditor(Socket):
    __gsignals__ = {
        'file_type': (SIGNAL_RUN_FIRST, None, (str,))
    }

    def __init__(self, app_window, server_name, file_name=''):
        super(VimEditor, self).__init__()
        self.server_name = server_name
        self.__file_name = file_name
        self.connect("plug-removed", app_window.destroy_from_vim)
        self.connect("hierarchy-changed", self.hierarchy_changed)

    def hierarchy_changed(self, widget, previous_toplevel, *args):
        if previous_toplevel is None:
            self.vim_start_server()

    def vim_start_server(self):
        if self.__file_name:
            name, ext = splitext(self.__file_name)
            self.emit("file_type", ext)
        args = [
            "/usr/bin/gvim",
            "--socketid", str(self.get_id()),
            "--servername", self.server_name,
            "--echo-wid",
            # no menu (m) a no toolbar (T)
            "-c", "set go-=m go-=T filetype=rst"]
        if self.__file_name:
            args.append(self.__file_name)
        server = Popen(args, stdout=PIPE)
        server.stdout.readline()    # read wid, so server was started
        self.show()

    def vim_remote_expr(self, command):
        out = check_output([
            "/usr/bin/vim",
            "--servername", self.server_name,
            "--remote-expr", command
            ])
        return out.decode('utf-8').strip()

    def vim_remote_send(self, command):
        check_output([
            "/usr/bin/vim",
            "--servername", self.server_name,
            "--remote-send", command
            ])

    def get_vim_changes(self):
        try:
            return int(self.vim_remote_expr("b:changedtick"))
        except:
            return 0

    def get_vim_lines(self):
        return int(self.vim_remote_expr("line('$')"))

    def get_vim_get_buffer(self, count):
        return self.vim_remote_expr("getline(0, %d)" % count)

    def get_vim_pos(self):
        buff, row, col, off = self.vim_remote_expr("getpos('.')").split('\n')
        return int(row), int(col)

    def get_vim_file_path(self):
        return self.vim_remote_expr("expand('%:p')")

    def get_vim_encoding(self):
        return self.vim_remote_expr("&l:encoding")

    def get_vim_filetype(self):
        return self.vim_remote_expr("&l:filetype")

    def vim_quit(self):
        self.vim_remote_send("<ESC>:q! <CR>")

    def vim_open_file(self, file_name):
        self.vim_remote_send("<ESC>:e %s<CR>" % file_name)

    @property
    def is_modified(self):
        return bool(int(self.vim_remote_expr("&l:modified")))

    @property
    def file_name(self):
        __file_name = self.vim_remote_expr("@%")
        if __file_name != self.__file_name:
            name, ext = splitext(__file_name)
            self.emit("file_type", ext)
        self.__file_name = __file_name
        return self.__file_name

    def do_file_type(self, ext):
        pass

    def read_from_file(self, file_name):
        error('Not supported call read_from_file in VimEditor')

    def save(self, *args):
        error('Not supported call save in VimEditor')

    def save_as(self, *args):
        error('Not supported call save_as in VimEditor')
