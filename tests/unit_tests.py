# coding: utf-8
"""OnedataFS PyFilesystem unit tests."""

from __future__ import absolute_import
from __future__ import unicode_literals

from fs.onedatafs._util import stat_to_permissions


class StatMock:
    """Mock for Stat class."""

    atime = 0
    mtime = 0
    ctime = 0
    gid = 0
    uid = 0
    mode = 0
    size = 0


def test_stat_to_permissions():
    """Test conversion from stat to permissions."""
    attr = StatMock()

    attr.mode = 0o777
    assert stat_to_permissions(attr).as_str() == "rwxrwxrwx"

    attr.mode = 0o700
    assert stat_to_permissions(attr).as_str() == "rwx------"

    attr.mode = 0o644
    assert stat_to_permissions(attr).as_str() == "rw-r--r--"
