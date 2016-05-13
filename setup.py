#!/usr/bin/env python

from setuptools import setup

from formiko import __version__, __url__


def doc():
    with open('README.rst', 'r') as readme:
        return readme.read().strip()

setup(
    name="formiko",
    version=__version__,
    description="reStructuredText editor and live previewer",
    author="Ondrej Tuma",
    author_email="mcbig@zeropage.cz",
    url=__url__,
    packages=['formiko'],
    # data_files=[('css', ['tiny-writer.css'])],
    keywords=["doc", "html", "rst", "editor"],
    license="BSD",
    long_description=doc(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop"
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Natural Language :: Czech",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Topic :: Documentation",
        "Topic :: Software Development :: Documentation",
        "Topic :: Text Editors :: Documentation",
        "Topic :: Text Editors :: Text Processing",
        "Topic :: Text Processing",
        "Topic :: Text Processing :: Markup",
        "Topic :: Utilities"],
    requires=['docutils (>= 0.12)', 'python_gi'],
    install_requires=['docutils >= 0.12'],
    entry_points={
        'gui_scripts': [
            'formiko = formiko.main:main',
        ]
    }
)
