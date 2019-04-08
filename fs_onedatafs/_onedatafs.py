# coding: utf-8
"""
OnedataFS PyFilesystem implementation.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "Bartek Kryza"
__copyright__ = "Copyright (C) 2019 ACK CYFRONET AGH"
__license__ = "This software is released under the MIT license cited in " \
              "LICENSE.txt"

__all__ = ["OnedataFS"]

import contextlib
from datetime import datetime
import io
import itertools
import os
from ssl import SSLError
import tempfile
import threading
import mimetypes
import onedatafs
import stat

import six
from six import text_type

from fs import ResourceType
from fs import Seek
from fs.iotools import line_iterator
from fs.constants import DEFAULT_CHUNK_SIZE
from fs.permissions import Permissions
from fs.base import FS
from fs.info import Info
from fs import errors
from fs.mode import Mode
from fs.subfs import SubFS
from fs.path import basename, dirname, forcedir, join, normpath, relpath
from fs.time import datetime_to_epoch


def statToPermissions(attr):

    # 'other' permissions
    other = ''
    other += 'r' if stat.S_IROTH & attr.mode else '-'
    other += 'w' if stat.S_IWOTH & attr.mode else '-'
    other += 'x' if stat.S_IXOTH & attr.mode else '-'

    # 'group' permission
    group = ''
    group += 'r' if stat.S_IRGRP & attr.mode else '-'
    group += 'w' if stat.S_IWGRP & attr.mode else '-'
    group += 'x' if stat.S_IXGRP & attr.mode else '-'

    # 'user' permission
    user = ''
    user += 'r' if stat.S_IRUSR & attr.mode else '-'
    user += 'w' if stat.S_IWUSR & attr.mode else '-'
    user += 'x' if stat.S_IXUSR & attr.mode else '-'

    sticky = stat.S_ISVTX & attr.mode
    setuid = stat.S_ISUID & attr.mode
    setguid = stat.S_ISGID & attr.mode

    return Permissions(user=user, group=group, other=other, sticky=sticky,
                       setuid=setuid, setguid=setguid)


def ensureUnicode(path):
    if six.PY2:
        if isinstance(path, str):
            return unicode(path)
    return path


def toAscii(path):
    return path.encode('ascii', 'replace')


class OnedataFile(io.RawIOBase):
    def __init__(self, odfs, handle, path, mode):
        # type: (OnedataFS, Text, Text) -> None
        super(OnedataFile, self).__init__()
        self.odfs = odfs
        self.handle = handle
        self.path = path
        self.mode = Mode(mode)
        self.pos = 0
        self._lock = threading.Lock()

    def __repr__(self):
        # type: () -> str
        _repr = "<onedatafile {!r} {!r}>"
        return _repr.format(self.path, self.mode)

    def close(self):
        # type: () -> None
        if not self.closed:
            with self._lock:
                try:
                    self.handle.close()
                finally:
                    super(OnedataFile, self).close()

    def tell(self):
        # type: () -> int
        return self.pos

    def readable(self):
        # type: () -> bool
        return self.mode.reading

    def read(self, size=-1):
        # type: (int) -> bytes
        if not self.mode.reading:
            raise IOError("File not open for reading")

        chunks = []
        remaining = size

        with self._lock:
            while remaining:
                if remaining < 0:
                    read_size = DEFAULT_CHUNK_SIZE
                else:
                    read_size = min(DEFAULT_CHUNK_SIZE, remaining)

                chunk = self.handle.read(self.pos, read_size)
                if chunk == b"":
                    break
                chunks.append(chunk)
                self.pos += len(chunk)
                remaining -= len(chunk)
        return b"".join(chunks)

    def readline(self, size=-1):
        # type: (int) -> bytes
        return next(line_iterator(self, size))  # type: ignore

    def readlines(self, hint=-1):
        # type: (int) -> List[bytes]
        lines = []
        size = 0
        for line in line_iterator(self):  # type: ignore
            lines.append(line)
            size += len(line)
            if hint != -1 and size > hint:
                break
        return lines

    def writable(self):
        # type: () -> bool
        return self.mode.writing

    def write(self, data):
        # type: (bytes) -> int
        if not self.mode.writing:
            raise IOError("File not open for writing")

        with self._lock:
            self.handle.write(data, self.pos)
            self.pos += len(data)

        return len(data)

    def writelines(self, lines):
        # type: (Iterable[bytes]) -> None
        self.write(b"".join(lines))

    def truncate(self, size=None):
        # type: (Optional[int]) -> int
        if size is None:
            size = 0
        self._opfs.truncate(self.path, size)
        return size

    def seekable(self):
        # type: () -> bool
        return True

    def seek(self, pos, whence=Seek.set):
        # type: (int, SupportsInt) -> int
        _whence = int(whence)
        if _whence not in (Seek.set, Seek.current, Seek.end):
            raise ValueError("invalid value for whence")

        size = self.odfs.getinfo(self.path).size

        with self._lock:
            self.pos = min(pos, size)

        return self.tell()


@six.python_2_unicode_compatible
class OnedataFS(FS):
    """
    Construct a `Onedata <https://onedata.org>` filesystem for
    `PyFilesystem <https://pyfilesystem.org>`_

    :param str host: The Onedata Oneprovider host name.
    :param str token: The Onedata user access token.

    """

    _meta = {
        "case_insensitive": False,
        "invalid_path_chars": "\0",
        "network": True,
        "read_only": False,
        "thread_safe": True,
        "unicode_paths": False,
        "virtual": False,
    }

    def __init__(
            self,
            host,
            token,
            port=443,
            space=[],
            space_id=[],
            insecure=False,
            force_proxy_io=False,
            force_direct_io=False,
            no_buffer=False,
            io_trace_log=False,
            provider_timeout=30
    ):
        self._host = host
        self._token = token
        self._port = port
        self._space = space
        self._space_id = space_id
        self._insecure = insecure
        self._force_proxy_io = force_proxy_io
        self._force_direct_io = force_direct_io
        self._no_buffer = no_buffer
        self._io_trace_log = io_trace_log
        self._provider_timeout = provider_timeout
        self._tlocal = threading.local()

        self._odfs = onedatafs.OnedataFS(
            self._host,
            self._token,
            insecure=self._insecure,
            force_proxy_io=self._force_proxy_io,
            force_direct_io=self._force_direct_io,
            space=self._space,
            space_id=self._space_id,
            no_buffer=self._no_buffer,
            io_trace_log=self._io_trace_log,
            provider_timeout=self._provider_timeout)

        super(OnedataFS, self).__init__()

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "<onedatafs '{}:{}/{}'>".format(self._host, self._port,
                                               self.session_id())

    def session_id(self):
        return self._odfs.session_id()

    def isdir(self, path):
        path = ensureUnicode(path)
        _path = self.validatepath(path)
        try:
            return self.getinfo(_path).is_dir
        except errors.ResourceNotFound:
            return False

    def getinfo(self, path, namespaces=None):
        path = ensureUnicode(path)
        self.check()
        namespaces = namespaces or ()
        _path = self.validatepath(path).encode('ascii', 'replace')

        try:
            attr = self._odfs.stat(_path)
        except RuntimeError as error:
            if error.message == 'No such file or directory':
                raise errors.ResourceNotFound(path)
            raise error

        info = {"basic": {
            "name": basename(_path),
            "is_dir": stat.S_ISDIR(attr.mode)}}

        rt = ResourceType.unknown
        if stat.S_ISREG(attr.mode):
            rt = ResourceType.file
        if stat.S_ISDIR(attr.mode):
            rt = ResourceType.directory

        info["details"] = {
            "accessed": attr.atime,
            "modified": attr.mtime,
            "size": attr.size,
            "uid": attr.uid,
            "gid": attr.gid,
            "type": rt}

        info["access"] = {
            "uid": attr.uid,
            "gid": attr.gid,
            "permissions": statToPermissions(attr)}

        return Info(info)

    def openbin(self, path, mode="r", buffering=-1, **options):
        # type: (Text, Text, int, **Any) -> BinaryIO
        path = ensureUnicode(path)
        _mode = Mode(mode)
        _mode.validate_bin()
        _path = toAscii(self.validatepath(path))

        with self._lock:
            try:
                info = self.getinfo(path)
            except errors.ResourceNotFound:
                if _mode.reading:
                    raise errors.ResourceNotFound(path)
                if _mode.writing and not self.isdir(dirname(_path)):
                    raise errors.ResourceNotFound(path)
            else:
                if info.is_dir:
                    raise errors.FileExpected(path)
                if _mode.exclusive:
                    raise errors.FileExists(path)
            # TODO support mode
            handle = self._odfs.open(_path)
            onedata_file = OnedataFile(self._odfs, handle, path, mode)
        return onedata_file  # type: ignore

    def listdir(self, path):
        # type: (Text) -> list
        path = ensureUnicode(path)
        _path = toAscii(self.validatepath(path))

        _directory = set()
        offset = 0
        batch_size = 2500
        batch = self._odfs.readdir(_path, batch_size, offset)

        while True:
            if len(batch) == 0:
                break

            for dir_entry in batch:
                _directory.add(dir_entry)

            offset += len(batch)
            batch = self._odfs.readdir(_path, batch_size, offset)

        return list(_directory)

    def makedir(self, path, permissions=None, recreate=False):
        path = ensureUnicode(path)
        self.check()
        _path = toAscii(self.validatepath(path))

        if not self.isdir(dirname(_path)):
            raise errors.ResourceNotFound(path)

        if permissions is None:
            permissions = Permissions(user='rwx', group='r-x', other='r-x')

        try:
            self.getinfo(path)
        except errors.ResourceNotFound:
            self._odfs.mkdir(_path, permissions.mode)

        return SubFS(self, path)

    def remove(self, path):
        path = ensureUnicode(path)
        self.check()
        _path = toAscii(self.validatepath(path))
        info = self.getinfo(path)
        if info.is_dir:
            raise errors.FileExpected(path)
        self._odfs.unlink(_path)

    def isempty(self, path):
        path = ensureUnicode(path)
        self.check()
        _path = toAscii(self.validatepath(path))
        return self._odfs.readdir(_path, 1, 0)

    def removedir(self, path):
        path = ensureUnicode(path)
        self.check()
        _path = toAscii(self.validatepath(path))
        if _path == "/":
            raise errors.RemoveRootError()
        info = self.getinfo(path)
        if not info.is_dir:
            raise errors.DirectoryExpected(path)
        if not self.isempty(path):
            raise errors.DirectoryNotEmpty(path)

        self._odfs.unlink(_path)

    def setinfo(self, path, info):
        path = ensureUnicode(path)
        # TODO
        self.getinfo(path)

    def move(self, src_path, dst_path, overwrite=False):
        src_path = ensureUnicode(src_path)
        dst_path = ensureUnicode(dst_path)

        if not overwrite and self.exists(dst_path):
            raise errors.FileExists(dst_path)

        self._odfs.rename(toAscii(src_path), toAscii(dst_path))

    def listxattr(self, path):
        path = ensureUnicode(path)
        _path = toAscii(path)

        self.getinfo(path)

        result = set()
        xattrs = self._odfs.listxattr(_path)
        for xattr in xattrs:
            result.add(xattr)

        return list(result)

    def getxattr(self, path, name):
        path = ensureUnicode(path)
        _path = toAscii(path)
        _name = toAscii(name)

        self.getinfo(path)

        return self._odfs.getxattr(_path, _name)

    def setxattr(self, path, name, value):
        path = ensureUnicode(path)
        _path = toAscii(path)
        _name = toAscii(name)

        self.getinfo(path)

        return self._odfs.getxattr(_path, _name)

    def removexattr(self, path, name):
        path = ensureUnicode(path)
        _path = toAscii(path)
        _name = toAscii(name)

        self.getinfo(path)

        self._odfs.removexattr(_path, _name)


