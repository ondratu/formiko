"""Custom docutils directives and RST parser classes for formiko."""

import fnmatch
import os
from typing import ClassVar

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.parsers.rst import Parser as RstParser
from docutils.parsers.rst import directives as rst_directives

from formiko.utils import Undefined

try:
    from docutils_tinyhtml import Writer as TinyWriter  # type: ignore[import]
except ImportError:

    class TinyWriter(Undefined):  # type: ignore[no-redef]
        """Not imported TinyWriter."""


try:
    from m2r2 import MdInclude  # type: ignore[import]
    from m2r2 import convert as m2r_convert

    class _M2RConfig:
        no_underscore_emphasis = False
        m2r_parse_relative_links = False
        m2r_anonymous_references = False
        m2r_disable_inline_math = False
        m2r_use_mermaid = False

    class _M2REnv:
        config = _M2RConfig()

    class StandaloneMdInclude(MdInclude):
        """MdInclude with standalone docutils support.

        (no Sphinx env required).
        """

        def run(self):
            """Call ``MdInclude.run`` with local env."""
            settings = self.state.document.settings
            if not hasattr(settings, "env"):
                settings.env = _M2REnv()
            return super().run()

    rst_directives.register_directive("mdinclude", StandaloneMdInclude)

    class Mark2Resturctured(RstParser):
        """Converting from MarkDown to reStructuredText before parse."""

        def parse(self, inputstring, document):
            """Create RST from MD first and call than parse."""
            return super().parse(m2r_convert(inputstring), document)

except ImportError:

    class Mark2Resturctured(Undefined):  # type: ignore[no-redef]
        """Not imported Mark2Resturctured."""


class HtmlPreview:
    """Dummy html preview class."""


class FileTreeDirective(Directive):
    """RST directive that renders a directory tree as a bullet list.

    Usage::

        .. file-tree:: path/to/dir
           :depth: 3
           :include: *.md
           :links:
    """

    required_arguments = 1
    optional_arguments = 0
    option_spec: ClassVar = {
        "depth": rst_directives.nonnegative_int,
        "include": rst_directives.unchanged,
        "exclude": rst_directives.unchanged,
        "links": rst_directives.flag,
    }

    def run(self):
        """Build and return bullet_list nodes for the directory tree."""
        source = self.state_machine.input_lines.source(
            self.lineno - self.state_machine.input_offset - 1,
        )
        source_dir = os.path.dirname(os.path.abspath(source))
        path = os.path.normpath(
            os.path.join(source_dir, self.arguments[0]),
        )

        if not os.path.isdir(path):
            return [
                self.state_machine.reporter.error(
                    f"file-tree: directory not found:"
                    f" {self.arguments[0]!r}",
                    line=self.lineno,
                ),
            ]

        depth = self.options.get("depth", 2)
        include_pattern = self.options.get("include", None)
        exclude_pattern = self.options.get("exclude", None)
        links = "links" in self.options
        tree = self._build_tree(
            path,
            include_pattern,
            exclude_pattern,
            depth,
            0,
            source_dir,
            links,
        )
        return [tree] if tree else []

    def _file_matches(self, name, include_pattern, exclude_pattern):
        """Return True if *name* passes the include/exclude filters."""
        if include_pattern and not fnmatch.fnmatch(name, include_pattern):
            return False
        return not (
            exclude_pattern and fnmatch.fnmatch(name, exclude_pattern)
        )

    def _has_visible_file(self, dirpath, include_pattern, exclude_pattern):
        """Return True if *dirpath* contains at least one file passing filters.

        Only scans the immediate children (used when at depth limit).
        """
        try:
            for entry in os.scandir(dirpath):
                if (
                    not entry.name.startswith(".")
                    and entry.is_file()
                    and self._file_matches(
                        entry.name, include_pattern, exclude_pattern,
                    )
                ):
                    return True
        except PermissionError:
            pass
        return False

    def _make_file_item(self, entry, source_dir, links):
        """Return a list_item node for a file entry."""
        item = nodes.list_item()
        para = nodes.paragraph()
        if links:
            rel_path = os.path.relpath(entry.path, source_dir)
            para += nodes.reference(refuri=rel_path, text=entry.name)
        else:
            para += nodes.Text(entry.name)
        item += para
        return item

    def _make_dir_item(
        self, entry, include_pattern, exclude_pattern,
        depth, current_depth, source_dir, links,
    ):
        """Return a list_item node for a directory entry, or None to skip."""
        at_depth_limit = current_depth + 1 >= depth
        if at_depth_limit:
            # Can't recurse further; when a filter is active, check whether
            # the dir has at least one matching immediate file.
            if (include_pattern or exclude_pattern) and not (
                self._has_visible_file(
                    entry.path, include_pattern, exclude_pattern,
                )
            ):
                return None
            subtree = None
        else:
            subtree = self._build_tree(
                entry.path, include_pattern, exclude_pattern,
                depth, current_depth + 1, source_dir, links,
            )
            if subtree is None:
                # no visible children after filtering
                return None

        item = nodes.list_item()
        item += nodes.paragraph(text=entry.name)
        if subtree is not None:
            item += subtree
        return item

    def _build_tree(
        self,
        dirpath,
        include_pattern,
        exclude_pattern,
        depth,
        current_depth,
        source_dir,
        links,
    ):
        """Recursively build a bullet_list node for *dirpath*.

        Returns ``None`` when the resulting list would be empty.
        """
        if current_depth >= depth:
            return None

        try:
            entries = sorted(
                os.scandir(dirpath),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            return None

        items = []
        for entry in entries:
            if entry.name.startswith("."):
                continue

            if entry.is_dir(follow_symlinks=False):
                item = self._make_dir_item(
                    entry, include_pattern, exclude_pattern,
                    depth, current_depth, source_dir, links,
                )
            elif self._file_matches(
                entry.name, include_pattern, exclude_pattern,
            ):
                item = self._make_file_item(entry, source_dir, links)
            else:
                item = None

            if item is not None:
                items.append(item)

        if not items:
            return None

        bullet_list = nodes.bullet_list()
        bullet_list.extend(items)
        return bullet_list


rst_directives.register_directive("file-tree", FileTreeDirective)
