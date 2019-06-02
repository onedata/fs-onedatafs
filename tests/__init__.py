# coding: utf-8
"""OnedataFS PyFilesystem tests."""

from __future__ import absolute_import
from __future__ import unicode_literals

import os

import fs

# Add the local code directory to the `fs` module path
fs.__path__.insert(0, os.path.realpath(
    os.path.join(__file__, '..', '..', 'fs')))
