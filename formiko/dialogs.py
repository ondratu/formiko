# -*- coding: utf-8 -*-
from gi.repository import Gtk

from formiko import __version__, __author__, __copyright__


class AboutDialog(Gtk.AboutDialog):
    def __init__(self, transient_for):
        super(AboutDialog, self).__init__(transient_for=transient_for,
                                          modal=True)
        self.set_program_name("Formiko")
        self.set_version(__version__)
        self.set_copyright(__copyright__ + ' ' + __author__)
        self.set_website("https://github.com/ondratu/formiko")
        # self.set_website("https://formiko.zeropage.cz")
        # self.set_logo("formiko.svg")


class QuitDialogWithoutSave(Gtk.MessageDialog):
    def __init__(self, parent, file_name):
        super(QuitDialogWithoutSave, self).__init__(
            parent,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK_CANCEL,
            "File %s not saved.\n"
            "Are you sure to quite without save ?" % file_name)
