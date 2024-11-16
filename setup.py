"""Project setup.py."""

import logging
from gzip import open as zopen
from os import listdir, makedirs, path
from shutil import rmtree
from typing import ClassVar

from docutils.core import publish_string
from docutils.writers.manpage import Writer
from setuptools import Command, setup
from setuptools.command.build import build
from setuptools.command.install import install

from formiko import __comment__, __url__, __version__

# pylint: disable=missing-function-docstring
# ruff: noqa: D102


def doc():
    """Return documentation from README.rst."""
    with open("README.rst", encoding="utf-8") as readme:
        return readme.read().strip()


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
        super().initialize_options()
        self.man_base = None

    def finalize_options(self):
        super().finalize_options()
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")

    def run(self):
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
        self.man_base = None
        self.build_base = None

    def finalize_options(self):
        self.set_undefined_options("build", ("build_base", "build_base"))
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")

    def run(self):
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
        self.man_base = None
        self.build_base = None
        self.install_data = None
        self.man_dir = None
        self.outfiles = []

    def finalize_options(self):
        self.set_undefined_options("build", ("build_base", "build_base"))
        self.set_undefined_options("install", ("install_data", "install_data"))
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")
        if self.man_dir is None:
            self.man_dir = path.join(self.install_data, "share", "man", "man1")

    def run(self):
        self.mkpath(self.man_dir)
        for page in listdir(self.man_base):
            src = f"{self.man_base}/{page}"
            (out, _) = self.copy_file(src, self.man_dir)
            self.outfiles.append(out)

    def get_inputs(self):
        return []

    def get_outputs(self):
        return self.outfiles


class CheckVersion(Command):
    """Check versions validation."""

    description = "check if all all versions in all files are same"
    user_options: ClassVar[list[str]] = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
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
    name="formiko",
    version=__version__,
    description=__comment__,
    author="Ondrej Tuma",
    author_email="mcbig@zeropage.cz",
    url=__url__,
    packages=["formiko"],
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
    keywords=["doc", "html", "rst", "docutils", "md", "markdown", "editor"],
    license="BSD",
    long_description=doc(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Documentation",
        "Topic :: Software Development :: Documentation",
        "Topic :: Text Editors :: Documentation",
        "Topic :: Text Editors :: Text Processing",
        "Topic :: Text Processing",
        "Topic :: Text Processing :: Markup",
        "Topic :: Text Processing :: Markup :: HTML",
        "Topic :: Utilities",
    ],
    requires=["docutils (>= 0.12)", "python_gi", "webkit2", "gtksourceview"],
    extra_requires=[
        "m2r",
        "Pygments",
        "docutils-tinyhtmlwriter",
        "docutils-htmlwriter",
        "docutils-html5-writer",
    ],
    install_requires=["docutils >= 0.12"],
    entry_points={
        "gui_scripts": [
            "formiko = formiko.__main__:main",
            "formiko-vim = formiko.__main__:main_vim",
        ],
    },
    cmdclass={
        "build": Build,
        "install_man": InstallMan,
        "clean_man": CleanMan,
        "check_version": CheckVersion,
    },
)
