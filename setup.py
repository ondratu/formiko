#!/usr/bin/env python

from distutils import log
from distutils.command.build import build
from distutils.command.clean import clean
from distutils.command.install_data import install_data
from distutils.core import Command
from distutils.errors import DistutilsError
from distutils.version import StrictVersion
from gzip import open as zopen
from os import listdir, makedirs, path
from shutil import rmtree

from docutils.core import publish_string
from docutils.writers.manpage import Writer
from setuptools import setup

from formiko import __comment__, __url__, __version__


def doc():
    with open("README.rst", encoding="utf-8") as readme:
        return readme.read().strip()


def icons_data():
    path = "share/icons/hicolor"
    icons = [("%s/scalable/apps" % path, ["icons/formiko.svg"])]
    for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        icons.append(("%s/%dx%d/apps" % (path, size, size),
                     ["icons/%dx%d/formiko.png" % (size, size)]))
    return icons


def man_page(writer, src, dst):
    with open(src, encoding="utf-8") as source:
        rst = source.read().format(version=__version__)
    with zopen(dst, "wb") as destination:
        destination.write(publish_string(source=rst, writer=writer))


class XBuild(build):
    def initialize_options(self):
        build.initialize_options(self)
        self.man_base = None

    def finalize_options(self):
        build.finalize_options(self)
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")

    def run(self):
        build.run(self)
        log.info("building man pages")
        if self.dry_run:
            return

        writer = Writer()
        if not path.exists(self.man_base):
            makedirs(self.man_base)
        for page in ("formiko", "formiko-vim"):
            log.info(f"manpage {page}.rst -> {self.man_base}/{page}.1.gz")
            man_page(writer, page+".rst", f"{self.man_base}/{page}.1.gz")


class XClean(clean):
    def initialize_options(self):
        clean.initialize_options(self)
        self.man_base = None

    def finalize_options(self):
        clean.finalize_options(self)
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")

    def run(self):
        clean.run(self)
        log.info("clean man pages")
        if self.dry_run:
            return

        if path.exists(self.man_base):
            rmtree(self.man_base)


class XInstallData(install_data):
    def initialize_options(self):
        install_data.initialize_options(self)
        self.man_base = None
        self.build_base = None

    def finalize_options(self):
        install_data.finalize_options(self)
        self.set_undefined_options("build", ("build_base", "build_base"))
        if self.man_base is None:
            self.man_base = path.join(self.build_base, "man")

    def run(self):
        self.data_files.append(
            ("share/man/man1",
             [f"{self.man_base}/{page}"
                  for page in listdir(self.man_base)]))
        install_data.run(self)
        return False


class XCheckVersion(Command):
    description = "check if all all versions in all files are same"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        pkg_version = StrictVersion(__version__)
        log.info("package version is %s", pkg_version)
        ch_version = StrictVersion(self.read_changelog())
        log.info("ChangeLog version is %s", ch_version)
        meta_version = StrictVersion(self.read_metainfo())
        log.info("metainfo version is %s", meta_version)
        if not pkg_version == ch_version == meta_version:
            msg = "Versions are not same!"
            raise DistutilsError(msg)

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
                    vals = dict(x.split("=") for x in
                                filter(lambda x: "=" in x, line.split(" ")))
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
    data_files=[("share/doc/formiko", ["README.rst", "COPYING", "ChangeLog", "AUTHORS"]), ("share/applications", ["formiko.desktop", "formiko-vim.desktop"]), ("share/metainfo", ["formiko.metainfo.xml"]), ("share/formiko/icons", ["icons/formiko.svg"]), *icons_data()],
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
        "Topic :: Utilities"],
    requires=["docutils (>= 0.12)", "python_gi", "webkit2", "gtksourceview"],
    extra_requires=["m2r", "recommonmark", "Pygments",
                    "docutils-tinyhtmlwriter", "docutils-htmlwriter",
                    "docutils-html5-writer"],
    install_requires=["docutils >= 0.12"],
    entry_points={
        "gui_scripts": [
            "formiko = formiko.__main__:main",
            "formiko-vim = formiko.__main__:main_vim",
        ],
    },
    cmdclass={"build": XBuild, "clean": XClean, "install_data": XInstallData,
              "check_version": XCheckVersion},
)
