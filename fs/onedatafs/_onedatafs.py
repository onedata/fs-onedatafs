# coding: utf-8
"""OnedataFS PyFilesystem implementation."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

__author__ = "Bartek Kryza"
__copyright__ = "Copyright (C) 2019 ACK CYFRONET AGH"
__license__ = (
    "This software is released under the MIT license cited in LICENSE.txt"
)

__all__ = ["OnedataFS"]

import io
import stat
import threading
from typing import Any, BinaryIO, Iterable, Optional, SupportsInt, Text

from fs.base import FS
from fs.constants import DEFAULT_CHUNK_SIZE
from fs.enums import ResourceType, Seek
from fs.errors import DirectoryExists, DirectoryExpected, DirectoryNotEmpty
from fs.errors import FileExists, FileExpected
from fs.errors import RemoveRootError, ResourceInvalid, ResourceNotFound
from fs.info import Info
from fs.iotools import line_iterator
from fs.mode import Mode
from fs.path import basename, dirname
from fs.permissions import Permissions
from fs.subfs import SubFS

import six

import onedatafs # noqa

from ._util import ensure_unicode, info_to_stat, stat_to_permissions, to_ascii


class OnedataSubFS(SubFS):
    """
    Subdirectory filesystem for OnedataFS.

    Provides a subclass of SubFS delegating custom OnedataFS methods to
    SubFS delegate.
    """

    def listxattr(self, path):
        """Call :func:`~OnedataFS.listxattr`."""
        # type: (Text) -> list

        return self.delegate_fs().listxattr(self.delegate_path(path)[1])

    def getxattr(self, path, name):
        """Call :func:`~OnedataFS.getxattr`."""
        # type: (Text, Text) -> Text

        return self.delegate_fs().getxattr(self.delegate_path(path)[1], name)

    def setxattr(self, path, name, value):
        """Call :func:`~OnedataFS.setxattr`."""
        # type: (Text, Text, bytes) -> None

        return self.delegate_fs().setxattr(self.delegate_path(path)[1], name)

    def removexattr(self, path, name):
        """Call :func:`~OnedataFS.removexattr`."""
        # type: (Text, Text) -> None

        return self.delegate_fs().removexattr(self.delegate_path(path)[1], name)

    def location(self, path):
        """Call :func:`~OnedataFS.location`."""
        # type: (Text) -> dict

        return self.delegate_fs().location(self.delegate_path(path)[1])


class OnedataFile(io.RawIOBase):
    """
    Wrapper over OnedataFS file handle.

    As long as an instance of the class is referenced, the file is
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
        """Return unique representation of the file handle."""
        # type: () -> str

        _repr = "<onedatafile {!r} {!r}>"
        return _repr.format(self.path, self.mode)

    def close(self):
        """
        Close the file handle.

        This operation may invoke flushing of internal buffers.
        """
        # type: () -> None

        if not self.closed:
            with self._lock:
                try:
                    self.handle.close()
                finally:
                    super(OnedataFile, self).close()

    def tell(self):
        """Return current position in the file."""
        # type: () -> int

        return self.pos

    def readable(self):
        """Return True if the file was opened for reading."""
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
                if not chunk:
                    break
                chunks.append(chunk)
                self.pos += len(chunk)
                remaining -= len(chunk)

        return b''.join(chunks)

    def readline(self, size=-1):
        """
        Read a single line from file.

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
        # type: (int) -> [bytes]

        lines = []
        size = 0
        for line in line_iterator(self):  # type: ignore
            lines.append(line)
            size += len(line)
            if hint != -1 and size > hint:
                break
        return lines

    def writable(self):
        """Return True if the file was opened for writing."""
        # type: () -> bool

        return self.mode.writing

    def write(self, data):
        """
        Write `data` to file starting from current position in the file.

        :param bytes data: Data to write to the file
        """
        # type: (bytes) -> int

        if not self.mode.writing:
            raise IOError("File not open for writing")

        with self._lock:
            if six.PY2 and isinstance(data, unicode):  # noqa
                self.handle.write(data.encode("utf-8"), self.pos)
            else:
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
            size = self.pos

        _path = self.path.encode("ascii", "replace")

        self.odfs.truncate(_path, size)

        return self.odfs.stat(_path).size

    def seekable(self):
        """Return `True` if the file is seekable."""
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

        if _whence == Seek.current or _whence == Seek.set:
            if pos < 0:
                raise ValueError("Negative seek position {}".format(pos))
        elif _whence == Seek.end:
            if pos > 0:
                raise ValueError("Positive seek position {}".format(pos))

        with self._lock:
            if _whence == Seek.set:
                self.pos = pos
            if _whence == Seek.current:
                self.pos = self.pos + pos
            if _whence == Seek.end:
                _path = self.path.encode("ascii", "replace")
                size = self.odfs.stat(_path).size
                self.pos = size + pos

        return self.tell()


@six.python_2_unicode_compatible
class OnedataFS(FS):
    """
    Implementation of Onedata virtual filesystem for PyFilesystem.

    Implementation of `Onedata <https://onedata.org>` filesystem for
    `PyFilesystem <https://pyfilesystem.org>`.
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
        host,  # type: Text
        token,  # type: Text
        port=443,  # type: int
        space=[],  # type: [Text]
        space_id=[],  # type: [Text]
        insecure=False,  # type: bool
        force_proxy_io=False,  # type: bool
        force_direct_io=False,  # type: bool
        no_buffer=False,  # type: bool
        io_trace_log=False,  # type: bool
        provider_timeout=30,  # type: int
        log_dir=None,  # type: Text
    ):
        """
        Onedata client OnedataFS constructor.

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
        :param bool insecure: When `True`, allow connecting to Oneproviders
                              without valid SSL certificate.
        :param bool force_proxy_io: When `True`, forces all data transfers to
                                    go via Oneproviders.
        :param bool force_direct_io: When `True`, forces all data transfers to
                                     go directly via the target storage API. If
                                     storage is not available, for instance due
                                     to network firewalls, error will
                                     be returned for all `read` and `write`
                                     operations.
        :param bool no_buffer: When `True`, disable all internal buffering in
                               the OnedataFS.
        :param bool io_trace_log: When `True`, the OnedataFS will log all
                                  requests in a CSV file in the directory
                                  specified by `log_dir`.
        :param int provider_timeout: Specifies the timeout for waiting for
                                     Oneprovider responses, in seconds.
        :param str log_dir: Path in the filesystem, where internal OnedataFS
                            logs should be stored. When `None`, no logging will
                            be generated.
        """
        # type: (...) -> OnedataFS

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
            provider_timeout=self._provider_timeout,
        )

        super(OnedataFS, self).__init__()

    def __repr__(self):
        """Return unique representation of the OnedataFS instance."""
        # type: () -> Text

        return self.__str__()

    def __str__(self):
        """Return unique representation of the OnedataFS instance."""
        # type: () -> Text

        return "<onedatafs '{}:{}/{}'>".format(
            self._host, self._port, self.session_id()
        )

    def session_id(self):
        """
        Get Onedata session id.

        Return unique session id representing the connection with
        Oneprovider.
        """
        # type: () -> Text

        return self._odfs.session_id()

    def isdir(self, path):
        """
        Check if directory exists under `path`.

        Returns `True` when the resource under `path` is an existing directory

        :param str path: Path pointing to a file or directory.
        """
        # type: (Text) -> bool

        path = ensure_unicode(path)
        _path = self.validatepath(path)
        try:
            return self.getinfo(_path).is_dir
        except ResourceNotFound:
            return False

    def getinfo(self, path, namespaces=None):
        """
        Return an Info instance for the resource (file or directory).

        :param str path: Path pointing to a file or directory.
        :param set namespaces: The list of PyFilesystem `Info` namespaces
                               which should be included in the response.
        """
        # type: (Text, list) -> bool

        path = ensure_unicode(path)
        self.check()
        namespaces = namespaces or ()
        path = self.validatepath(path)
        _path = path.encode("ascii", "replace") if six.PY2 else path

        try:
            attr = self._odfs.stat(_path)
        except RuntimeError:
            raise ResourceNotFound(path)

        # `info` must be JSON serializable dictionary, so all
        # values must be valid JSON types
        info = {
            "basic": {
                "name": basename(_path),
                "is_dir": stat.S_ISDIR(attr.mode),
            }
        }

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
            "type": int(rt),
        }

        info["access"] = {
            "uid": attr.uid,
            "gid": attr.gid,
            "permissions": stat_to_permissions(attr).dump(),
        }

        return Info(info)

    def opendir(self, path):
        """
        Open directory.

        Opens a directory and returns a SubOnedataFS object representing
        its contents.

        :param path: path to directory to open
        :type path: string
        """
        # type: (Text) -> OnedataSubFS

        path = ensure_unicode(path)

        if not self.exists(path):
            raise ResourceNotFound(path)
        if not self.isdir(path):
            raise ResourceInvalid(
                "Path {} should reference a directory".format(path,))
        return OnedataSubFS(self, path)

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

        path = ensure_unicode(path)
        _mode = Mode(mode)
        _mode.validate_bin()
        _path = to_ascii(self.validatepath(path))
        seek = 0

        with self._lock:
            try:
                info = self.getinfo(path, namespaces=['details'])
                seek = info.size
            except ResourceNotFound:
                if _mode.reading:
                    raise ResourceNotFound(path)
                if _mode.writing and not self.isdir(dirname(path)):
                    raise ResourceNotFound(path)
            else:
                if info.is_dir:
                    raise FileExpected(path)
                if _mode.exclusive:
                    raise FileExists(path)
                if _mode.truncate:
                    self._odfs.truncate(_path, 0)

            handle = self._odfs.open(_path)
            onedata_file = OnedataFile(self._odfs, handle, path, mode)
            if _mode.appending:
                onedata_file.seek(seek)

        return onedata_file  # type: ignore

    def listdir(self, path):
        """
        Return the contents of directory under `path`.

        POSIX entries such as `.` and `..` are not returned.

        :param str path: Path pointing to a file.
        """
        # type: (Text) -> list

        path = ensure_unicode(path)

        if not self.exists(path):
            raise ResourceNotFound(path)

        if self.isfile(path):
            raise DirectoryExpected(path)

        _path = to_ascii(self.validatepath(path))

        _directory = set()
        offset = 0
        batch_size = 2500
        batch = self._odfs.readdir(_path, batch_size, offset)

        while True:
            if len(batch) == 0:
                break

            for dir_entry in batch:
                _directory.add(ensure_unicode(dir_entry))

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
        # type: (Text, Permissions, bool) -> SubFS

        path = ensure_unicode(path)
        self.check()
        _path = to_ascii(self.validatepath(path))

        if self.exists(path) and not recreate:
            raise DirectoryExists(path)

        if not self.isdir(dirname(path)):
            raise ResourceNotFound(path)

        if permissions is None:
            permissions = Permissions(user="rwx", group="rwx", other="r-x")

        if not self.exists(path):
            self._odfs.mkdir(_path, permissions.mode)

        return SubFS(self, path)

    def remove(self, path):
        """
        Remove file under path.

        :param str path: Path pointing to a file.
        """
        # type: (Text) -> None

        path = ensure_unicode(path)
        self.check()
        _path = to_ascii(self.validatepath(path))
        info = self.getinfo(path)
        if info.is_dir:
            raise FileExpected(path)
        self._odfs.unlink(_path)

    def isempty(self, path):
        """
        Check if directory is empty.

        Returns `True` when directory under `path` is empty.

        :param str path: Path pointing to a directory.
        """
        # type: (Text) -> bool

        path = ensure_unicode(path)
        self.check()
        _path = to_ascii(self.validatepath(path))

        return len(self._odfs.readdir(_path, 2, 0)) == 0

    def removedir(self, path):
        """
        Remove directory under `path`.

        The directory must be empty.

        :param str path: Path pointing to a directory.
        """
        # type: (Text) -> None

        path = ensure_unicode(path)
        self.check()
        _path = to_ascii(self.validatepath(path))
        if _path == "/":
            raise RemoveRootError()
        info = self.getinfo(path)
        if not info.is_dir:
            raise DirectoryExpected(path)
        if not self.isempty(path):
            raise DirectoryNotEmpty(path)

        try:
            self._odfs.unlink(_path)
        except RuntimeError as error:
            if str(error) == "Directory not empty":
                raise DirectoryNotEmpty(path)
            raise error

    def setinfo(self, path, info):
        """
        Set file attributes.

        :param str path: Path pointing to a file or directory.
        :param Info info: A PyFilesystem `Info` instance
        """
        # type: (Text, Info) -> None

        if not self.exists(path):
            raise ResourceNotFound(path)

        path = ensure_unicode(path)
        _path = to_ascii(self.validatepath(path))

        stat, to_set = info_to_stat(info)

        self._odfs.setattr(_path, stat, to_set)

    def move(self, src_path, dst_path, overwrite=False):
        """
        Rename file from `src_path` to `dst_path`.

        :param str src_path: The old file path
        :param str dst_path: The new file path
        :param bool overwrite: When `True`, existing file at `dst_path` will be
                               replaced by contents of file at `src_path`
        """
        # type: (Text, Text, bool) -> None

        if not self.exists(src_path):
            raise ResourceNotFound(src_path)

        if dirname(dst_path) and not self.exists(dirname(dst_path)):
            raise ResourceNotFound(src_path)

        if self.isdir(src_path):
            raise FileExpected(src_path)

        if not overwrite and self.exists(dst_path):
            raise FileExists(dst_path)

        src_path = ensure_unicode(src_path)
        dst_path = ensure_unicode(dst_path)

        self._odfs.rename(to_ascii(src_path), to_ascii(dst_path))

    def listxattr(self, path):
        """
        Get extended attribute names.

        Returns the list of extended attribute names attached to a file.

        :param str path: Path pointing to a file or directory.
        """
        # type: (Text) -> list

        path = ensure_unicode(path)
        _path = to_ascii(path)

        self.getinfo(path)

        result = set()
        xattrs = self._odfs.listxattr(_path)
        for xattr in xattrs:
            result.add(xattr)

        return list(result)

    def getxattr(self, path, name):
        """
        Get value of an extended attribute.

        Returns the value of extended attribute with `name` from file
        or directory at `path`.

        :param str path: Path pointing to a file or directory.
        :param str name: Name of the extended attribute.
        """
        # type: (Text, Text) -> Text

        path = ensure_unicode(path)
        _path = to_ascii(path)
        _name = to_ascii(name)

        self.getinfo(path)

        return self._odfs.getxattr(_path, _name)

    def setxattr(self, path, name, value):
        """
        Set an extended attribute.

        Set the value of extended attribute with `name` from file
        or directory at `path` to `value`.

        :param str path: Path pointing to a file or directory.
        :param str name: Name of the extended attribute.
        :param str name: New value of the extended attribute.
        """
        # type: (Text, Text, bytes) -> None

        path = ensure_unicode(path)
        _path = to_ascii(path)
        _name = to_ascii(name)

        self.getinfo(path)

        return self._odfs.getxattr(_path, _name)

    def removexattr(self, path, name):
        """
        Remove an extended attribute.

        Removes an extended attribute with `name` from file or directory at
        `path`.

        :param str path: Path pointing to a file or directory.
        :param str name: Name of the extended attribute.
        """
        # type: (Text, Text) -> None

        path = ensure_unicode(path)
        _path = to_ascii(path)
        _name = to_ascii(name)

        self.getinfo(path)

        self._odfs.removexattr(_path, _name)

    def location(self, path):
        """
        Return file block location map.

        Returns the location map which provides information on which
        blocks of the file are replicated to the storage of the
        Oneprovider to which the OnedataFS is currently connected to.

        The indexes of the map are storage id's.

        Example:
        {
            "ASCNJGKDSA": [[0,5], [10, 15]]
        }

        :param str path: Path pointing to a file or directory.
        :param str name: Name of the extended attribute.
        """
        # type: (Text) -> dict

        _path = to_ascii(path)
        return self._odfs.location_map(_path)
