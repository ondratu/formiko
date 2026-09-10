"""State and file discovery for the file browser."""

import contextlib
from os import listdir
from os.path import basename
from typing import Callable


class FileBrowserModel:
    """Store the file browser state without depending on GTK."""

    def __init__(
        self,
        default_directory="",
        file_filter: Callable[[str], bool] | None = None,
    ):
        self._directory = ""
        self._default_directory = default_directory
        self._files = []
        self._file_filter = file_filter or (lambda _name: True)

    @property
    def directory(self):
        """Return the directory currently selected for browsing."""
        return self._directory

    @property
    def files(self):
        """Return the files found during the last refresh."""
        return tuple(self._files)

    @property
    def directory_name(self):
        """Return the display name of the current directory."""
        return basename(self._directory) or self._directory

    def set_directory(self, directory):
        """Record which directory to browse, without loading it."""
        self._directory = directory or self._default_directory

    def refresh(self):
        """Reload and return known files from the current directory."""
        self._files = []
        if not self._directory:
            return self.files

        with contextlib.suppress(OSError):
            self._files = sorted(
                name for name in listdir(self._directory)
                if self._file_filter(name)
            )
        return self.files

    def clear(self):
        """Remove the files from the current view."""
        self._files = []
