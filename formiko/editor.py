"""Editor interface."""

from enum import Enum


class EditorType(Enum):
    """Editor type."""

    SOURCE = "source"
    VIM = "vim"
    PREVIEW = None
