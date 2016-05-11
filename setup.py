#!/usr/bin/env python

try:
    from setuptools import setup
except:
    from distutils.core import setup

__version__ = "0.1.0"
__url__ = "https://github.com/ondratu/formiko"


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
    # py_modules=['formiko'],
    scripts=['formiko.py'],
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
    install_requires=['docutils >= 0.12']
)
