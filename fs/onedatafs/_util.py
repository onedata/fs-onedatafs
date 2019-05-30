# coding: utf-8
"""OnedataFS PyFilesystem utility functions."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "Bartek Kryza"
__copyright__ = "Copyright (C) 2019 ACK CYFRONET AGH"
__license__ = (
    "This software is released under the MIT license cited in LICENSE.txt"
)

__all__ = ["stat_to_permissions", "ensure_unicode", "to_ascii"]

import stat

from fs.permissions import Permissions

import six


def stat_to_permissions(attr):
    """
    Convert PyFilesystem Info instance `attr` to permissions string.

    :param Info attr: The PyFilesystem Info instance.
    """
    # 'other' permissions
    other = ""
    other += "r" if stat.S_IROTH & attr.mode else "-"
    other += "w" if stat.S_IWOTH & attr.mode else "-"
    other += "x" if stat.S_IXOTH & attr.mode else "-"

    # 'group' permission
    group = ""
    group += "r" if stat.S_IRGRP & attr.mode else "-"
    group += "w" if stat.S_IWGRP & attr.mode else "-"
    group += "x" if stat.S_IXGRP & attr.mode else "-"

    # 'user' permission
    user = ""
    user += "r" if stat.S_IRUSR & attr.mode else "-"
    user += "w" if stat.S_IWUSR & attr.mode else "-"
    user += "x" if stat.S_IXUSR & attr.mode else "-"

    sticky = stat.S_ISVTX & attr.mode
    setuid = stat.S_ISUID & attr.mode
    setguid = stat.S_ISGID & attr.mode

    return Permissions(
        user=user,
        group=group,
        other=other,
        sticky=sticky,
        setuid=setuid,
        setguid=setguid,
    )


def ensure_unicode(path):
    """
    Make sure that the value is in Unicode.

    On Python 2, it means converting the `str` instance to `unicode` instance.

    :param path str: The string to convert to Unicode.
    """
    if six.PY2:
        if isinstance(path, str):
            return six.u(path)
    return path


def to_ascii(path):
    """
    Convert unicode instance to ascii.

    :param path str: The string to convert to ascii
    """
    return path.encode("ascii", "replace")
