#!/usr/bin/env python
"""OnedataFS is a Python client to Onedata virtual filesystem."""

from setuptools import setup

__version__ = '21.02.7'

CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Topic :: System :: Filesystems",
]

with open("README.rst", "rt") as f:
    DESCRIPTION = f.read()

REQUIREMENTS = ["fs", "six"]

setup(
    name="fs.onedatafs",
    author="Bartek Kryza",
    author_email="bkryza@gmail.com",
    classifiers=CLASSIFIERS,
    description="Onedata filesystem for PyFilesystem2",
    install_requires=REQUIREMENTS,
    license="MIT",
    long_description=DESCRIPTION,
    packages=["fs.onedatafs"],
    keywords=["pyfilesystem", "Onedata", "oneclient"],
    platforms=["linux"],
    test_suite="nose.collector",
    url="https://github.com/onedata/fs-onedatafs",
    version=__version__,
    entry_points={
        "fs.opener": ["onedatafs = fs.onedatafs.opener:OnedataFSOpener"]
    },
)
