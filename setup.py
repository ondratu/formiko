"""Project setup.py - custom build commands and data_files."""

import logging
import re
from gzip import open as zopen
from os import listdir, makedirs, path
from shutil import rmtree
from typing import ClassVar

from docutils.core import publish_string
from docutils.writers.manpage import Writer
from setuptools import Command, setup
from setuptools.command.build import build
from setuptools.command.install import install


def _read_version():
    """Read project version from formiko/__init__.py without importing it."""
    init = path.join(
        path.dirname(path.abspath(__file__)),
        "formiko",
        "__init__.py",
    )
    with open(init, encoding="utf-8") as f:
        match = re.search(
            r'^__version__\s*=\s*["\']([^"\']+)["\']',
            f.read(),
            re.M,
        )
        if match:
            return match.group(1)
    error = "Cannot find __version__ in formiko/__init__.py"
    raise RuntimeError(error)


__version__ = _read_version()


def icons_data():
    """Return list of icons for setup.py."""
    _path = "share/icons/hicolor"
    icons = [(f"{_path}/scalable/apps", ["icons/formiko.svg"])]
    for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        icons.append(
            (
                f"{_path}/{size}x{size}/apps",
                [f"icons/{size}x{size}/formiko.png"],
            ),
        )
    return icons


def man_page(writer, src, dst):
    """Generate man page from rst source."""
    with open(src, encoding="utf-8") as source:
        rst = source.read().format(version=__version__)
    with zopen(dst, "wb") as destination:
        destination.write(publish_string(source=rst, writer=writer))


class Build(build):
    """Build command class for generating man pages."""

    man_base: str | None

    def initialize_options(self):
        """Initialize default option values."""
        super().initialize_options()
        self.man_base = None

    def finalize_options(self):
        """Finalize and validate option values."""
        super().finalize_options()
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")

    def run(self):
        """Build man pages in addition to standard build."""
        super().run()
        logging.info("building man pages")
        if self.dry_run:
            return

        writer = Writer()
        if not path.exists(self.man_base):
            makedirs(self.man_base)
        for page in ("formiko", "formiko-vim"):
            dst = f"{self.man_base}/{page}.1.gz"
            logging.info("manpage %s.rst -> %s", page, dst)
            man_page(writer, page + ".rst", dst)


class CleanMan(Command):
    """Clean build man files."""

    description = "clean up man files from 'build' command"
    user_options: ClassVar[list[tuple]] = [
        (
            "build-base=",
            "b",
            "base build directory (default: 'build.build-base')",
        ),
    ]

    man_base: str | None
    build_base: str | None

    def initialize_options(self):
        """Initialize default option values."""
        self.man_base = None
        self.build_base = None

    def finalize_options(self):
        """Finalize and validate option values."""
        self.set_undefined_options("build", ("build_base", "build_base"))
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")

    def run(self):
        """Remove generated man page files."""
        logging.info("clean man pages")
        if self.dry_run:
            return

        if path.exists(self.man_base):
            rmtree(self.man_base)


# ruff: noqa: ARG005
install.sub_commands.append(("install_man", lambda self: True))


class InstallMan(Command):
    """Install man files from build command."""

    description = "install data files"

    user_options: ClassVar[list[tuple]] = [
        (
            "man-dir=",
            "m",
            "destination directory for installing man files"
            "(default: installation base dir/man)",
        ),
    ]

    boolean_options: ClassVar[list[str]] = ["force"]
    man_base: str | None
    build_base: str | None
    install_data: str | None
    man_dir: str | None
    outfiles: list[str]

    def initialize_options(self):
        """Initialize default option values."""
        self.man_base = None
        self.build_base = None
        self.install_data = None
        self.man_dir = None
        self.outfiles = []

    def finalize_options(self):
        """Finalize and validate option values."""
        self.set_undefined_options("build", ("build_base", "build_base"))
        self.set_undefined_options("install", ("install_data", "install_data"))
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")
        if self.man_dir is None:
            self.man_dir = path.join(self.install_data, "share", "man", "man1")

    def run(self):
        """Install built man pages to the target directory."""
        self.mkpath(self.man_dir)
        for page in listdir(self.man_base):
            src = f"{self.man_base}/{page}"
            (out, _) = self.copy_file(src, self.man_dir)
            self.outfiles.append(out)

    def get_inputs(self):
        """Return list of input files (none for man pages)."""
        return []

    def get_outputs(self):
        """Return list of installed man page files."""
        return self.outfiles


class CheckVersion(Command):
    """Check versions validation."""

    description = "check if all all versions in all files are same"
    user_options: ClassVar[list[tuple]] = []

    def initialize_options(self):
        """Initialize default option values (none needed)."""

    def finalize_options(self):
        """Finalize and validate option values (none needed)."""

    def run(self):
        """Check that versions in all project files match."""
        # pylint: disable=import-outside-toplevel
        from packaging.version import Version

        pkg_version = Version(__version__)
        logging.info("package version is %s", pkg_version)
        ch_version = Version(self.read_changelog())
        logging.info("ChangeLog version is %s", ch_version)
        meta_version = Version(self.read_metainfo())
        logging.info("metainfo version is %s", meta_version)
        if not pkg_version == ch_version == meta_version:
            msg = "Versions are not same!"
            raise RuntimeError(msg)

    def read_changelog(self):
        """Read last version From ChangeLog."""
        with open("ChangeLog", encoding="utf-8") as chl:
            for line in chl:
                if line.startswith("Version"):
                    return line[8:].strip()
            return None

    def read_metainfo(self):
        """Read last version from formiko.metainfo.xml."""
        with open("formiko.metainfo.xml", encoding="utf-8") as meta:
            for line in meta:
                if "<release " in line:
                    vals = dict(
                        x.split("=")
                        for x in filter(lambda x: "=" in x, line.split(" "))
                    )
                    return vals.get("version", "").strip('"')
            return None


setup(
    data_files=[
        (
            "share/doc/formiko",
            ["README.rst", "COPYING", "ChangeLog", "AUTHORS"],
        ),
        ("share/applications", ["formiko.desktop", "formiko-vim.desktop"]),
        ("share/metainfo", ["formiko.metainfo.xml"]),
        ("share/formiko/icons", ["icons/formiko.svg"]),
        *icons_data(),
    ],
    cmdclass={
        "build": Build,
        "install_man": InstallMan,
        "clean_man": CleanMan,
        "check_version": CheckVersion,
    },
)
