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
    """
    Convert PyFilesystem Info instance `attr` to permissions
    string.

    :param Info attr: The PyFilesystem Info instance.
    """

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
    """
    Makes sure that the value is in Unicode. On Python 2, it means
    converting the `str` instance to `unicode` instance.

    :param path str: The string to convert to Unicode.
    """

    if six.PY2:
        if isinstance(path, str):
            return unicode(path)
    return path


def toAscii(path):
    """
    Converts unicode instance to ascii.

    :param path str: The string to convert to ascii
    """

    return path.encode('ascii', 'replace')


class OnedataFile(io.RawIOBase):
    """
    This class is a wrapper over OnedataFS file handle. As long
    as an instance of the class is references, the file is
    considered opened, including all buffers allocated by it internally.

    The handle can be explicitly closed using `close()` method.
    """

    def __init__(self, odfs, handle, path, mode):
        """
        `OnedataFile` constructor.

        `OnedataFile` is intentended to be constructed manually, but
        rather using `open()` or `openbin()` methods of `OnedataFS`.

        :param OnedataFS odfs: Reference to OnedataFS instance
        :param OnedataFileHandle handle: Instance of the OnedataFileHandle
        :param str path: Full path to file or directory,
                         relative to the filesystem root
        :param int mode: File open mode
        """
        # type: (OnedataFS, Text, Text) -> None
        super(OnedataFile, self).__init__()
        self.odfs = odfs
        self.handle = handle
        self.path = path
        self.mode = Mode(mode)
        self.pos = 0
        self._lock = threading.Lock()

    def __repr__(self):
        """
        Returns unique representation of the file handle
        """

        # type: () -> str
        _repr = "<onedatafile {!r} {!r}>"
        return _repr.format(self.path, self.mode)

    def close(self):
        """
        Closes the file handle.

        This operation may invoke flushing of internall buffers.
        """
        # type: () -> None
        
        if not self.closed:
            with self._lock:
                try:
                    self.handle.close()
                finally:
                    super(OnedataFile, self).close()

    def tell(self):
        """
        Return current position in the file.
        """
        # type: () -> int

        return self.pos

    def readable(self):
        """
        True if the file was opened for reading
        """
        # type: () -> bool

        return self.mode.reading

    def read(self, size=-1):
        """
        Read `size` bytes starting from current position in the file.

        If size is negative, read until end of file.

        :param int size: Number of bytes to read.
        """
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
        """
        Read `size` bytes from the file starting from current position
        in the file until the end of the line.

        If `size` is negative read until end of the line.

        :param int size: Number of bytes to read from the current line.
        """
        # type: (int) -> bytes

        return next(line_iterator(self, size))  # type: ignore

    def readlines(self, hint=-1):
        """
        Read `hint` lines from the file starting from current position.

        If `hint` is negative read until end of the line.

        :param int hint: Number of lines to read.
        """
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
        """
        True if the file was opened for writing.
        """
        # type: () -> bool

        return self.mode.writing

    def write(self, data):
        """
        Write `data` to file starting from current position in the file

        :param bytes data: Data to write to the file
        """
        # type: (bytes) -> int

        if not self.mode.writing:
            raise IOError("File not open for writing")

        with self._lock:
            self.handle.write(data, self.pos)
            self.pos += len(data)

        return len(data)

    def writelines(self, lines):
        """
        Write `lines` to file starting at the current position in the file.
        The elements of `lines` list do not need to contain new line
        characters.

        :param list lines: Lines to wrie to the file
        """
        # type: (Iterable[bytes]) -> None

        self.write(b"".join(lines))

    def truncate(self, size=None):
        """
        Change the size of the file to `size`.

        If `size` is smaller than the current size of the file,
        the remaining data will be deleted, if the `size` is larger than the
        current size of the file the file will be padded with zeros.

        :param int size: The new size of the file
        """
        # type: (Optional[int]) -> int

        if size is None:
            size = 0
        self._opfs.truncate(self.path, size)
        return size

    def seekable(self):
        """
        True if the file is seekable.
        """
        # type: () -> bool

        return True

    def seek(self, pos, whence=Seek.set):
        """
        Change current position in an opened file.

        The position can point beyond the current size of the file.
        In such case the file will be contain holes.

        :param int pos: New position in the file.
        """
        # type: (int, SupportsInt) -> int

        _whence = int(whence)
        if _whence not in (Seek.set, Seek.current, Seek.end):
            raise ValueError("invalid value for whence")

        size = self.odfs.getinfo(self.path).size

        with self._lock:
            self.pos = pos

        return self.tell()


@six.python_2_unicode_compatible
class OnedataFS(FS):
    """
    Construct a `Onedata <https://onedata.org>` filesystem for
    `PyFilesystem <https://pyfilesystem.org>`_
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
            provider_timeout=30,
            log_dir = None
    ):
        """
        OnedataFS constructor.

        `OnedataFS` instance maintains an active connection pool to the
        Oneprovider specified in the `host` parameter as long as it
        is referenced in the code. To close the connection call `close()`
        directly or use context manager.

        :param str host: The Onedata Oneprovider host name
        :param str token: The Onedata user access token
        :param int port: The Onedata Oneprovider port
        :param list space: The list of space names which should be opened.
                        By default, all spaces are opened.
        :param list space_id: The list of space id's which should be opened.
                            By default, all spaces are opened.
        :param bool insecure: When `True`, allow connecting to Oneproviders without
                            valid SSL certificate.
        :param bool force_proxy_io: When `True`, forces all data transfers to go
                                    via Oneproviders.
        :param bool force_direct_io: When `True`, forces all data transfers to go
                                    directly via the target storage API. If storage
                                    is not available, for instance due to network
                                    firewalls, error will be returned for all
                                    `read` and `write` operations
        :param bool no_buffer: When `True`, disable all internal buffering in the
                            OnedataFS
        :param bool io_trace_log: When `True`, the OnedataFS will log all requests
                                in a CSV file in the directory specified by
                                `log_dir`
        :param int provider_timeout: Specifies the timeout for waiting for
                                    Oneprovider responses, in seconds.
        :param str log_dir: Path in the filesystem, where internal OnedataFS logs
                            should be stored. When `None`, no logging will be
                            generated.
        """

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
        """
        Return unique representation of the OnedataFS instance.
        """

        return self.__str__()

    def __str__(self):
        """
        Return unique representation of the OnedataFS instance.
        """

        return "<onedatafs '{}:{}/{}'>".format(self._host, self._port,
                                               self.session_id())

    def session_id(self):
        """
        Return unique session id representing the connection with
        Oneprovider.
        """

        return self._odfs.session_id()

    def isdir(self, path):
        """
        Returns `True` when the resource under `path` is an existing directory

        :param str path: Path pointing to a file or directory.
        """

        path = ensureUnicode(path)
        _path = self.validatepath(path)
        try:
            return self.getinfo(_path).is_dir
        except errors.ResourceNotFound:
            return False

    def getinfo(self, path, namespaces=None):
        """
        Return an Info instance for the resource (file or directory).

        :param str path: Path pointing to a file or directory.
        :param set namespaces: The list of PyFilesystem `Info` namespaces
                               which should be included in the response.
        """

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
        """
        Open file under `path` in binary mode.

        :param str path: Path pointing to a file.
        :param str mode: Text representation of open mode e.g. "rw+"
        :param int buffering: Whether the BaseIO instance should be buffered
                              or not
        :param map options: Additional PyFilesystem options
        """
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
        """
        Return the contents of directory under `path`.

        POSIX entries such as `.` and `..` are not returned.

        :param str path: Path pointing to a file.
        """
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
        """
        Create a directory under `path`.

        :param str path: Path pointing to a file.
        :param Permissions permissions: PyFilesystem permission instance
        :param bool recreate: Not supported
        """

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
        """
        Remove file under path.

        :param str path: Path pointing to a file.
        """

        path = ensureUnicode(path)
        self.check()
        _path = toAscii(self.validatepath(path))
        info = self.getinfo(path)
        if info.is_dir:
            raise errors.FileExpected(path)
        self._odfs.unlink(_path)

    def isempty(self, path):
        """
        Return `True` when directory is empty

        :param str path: Path pointing to a directory.
        """

        path = ensureUnicode(path)
        self.check()
        _path = toAscii(self.validatepath(path))
        return self._odfs.readdir(_path, 1, 0)

    def removedir(self, path):
        """
        Remove directory under `path`.

        The directory must be empty.

        :param str path: Path pointing to a directory.
        """

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
        """
        Set file attributes.

        :param str path: Path pointing to a file or directory.
        :param Info info: A PyFilesystem `Info` instance
        """
        path = ensureUnicode(path)
        # TODO
        self.getinfo(path)

    def move(self, src_path, dst_path, overwrite=False):
        """
        Rename file from `src_path` to `dst_path`.

        :param str src_path: The old file path
        :param str dst_path: The new file path
        :param bool overwrite: When `True`, existing file at `dst_path` will be
                               replaced by contents of file at `src_path`
        """

        src_path = ensureUnicode(src_path)
        dst_path = ensureUnicode(dst_path)

        if not overwrite and self.exists(dst_path):
            raise errors.FileExists(dst_path)

        self._odfs.rename(toAscii(src_path), toAscii(dst_path))

    def listxattr(self, path):
        """
        Returns the list of extended attributes on a file

        :param str path: Path pointing to a file or directory.
        """

        path = ensureUnicode(path)
        _path = toAscii(path)

        self.getinfo(path)

        result = set()
        xattrs = self._odfs.listxattr(_path)
        for xattr in xattrs:
            result.add(xattr)

        return list(result)

    def getxattr(self, path, name):
        """
        Return the value of extended attribute with `name` from file
        or directory at `path`.

        :param str path: Path pointing to a file or directory.
        :param str name: Name of the extended attribute.
        """

        path = ensureUnicode(path)
        _path = toAscii(path)
        _name = toAscii(name)

        self.getinfo(path)

        return self._odfs.getxattr(_path, _name)

    def setxattr(self, path, name, value):
        """
        Set the value of extended attribute with `name` from file
        or directory at `path` to `value`.

        :param str path: Path pointing to a file or directory.
        :param str name: Name of the extended attribute.
        :param str name: New value of the extended attribute.
        """

        path = ensureUnicode(path)
        _path = toAscii(path)
        _name = toAscii(name)

        self.getinfo(path)

        return self._odfs.getxattr(_path, _name)

    def removexattr(self, path, name):
        """
        Remove an extended attribute with `name` from file
        or directory at `path`.

        :param str path: Path pointing to a file or directory.
        :param str name: Name of the extended attribute.
        """

        path = ensureUnicode(path)
        _path = toAscii(path)
        _name = toAscii(name)

        self.getinfo(path)

        self._odfs.removexattr(_path, _name)
