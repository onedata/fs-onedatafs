# coding: utf-8
"""Defines the OnedataFS opener."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

__all__ = ['OnedataFSOpener']

from fs.opener import Opener
from fs.opener.errors import OpenerError

from six.moves.urllib.parse import urlparse, parse_qs

from ._onedatafs import OnedataFS


class OnedataFSOpener(Opener):
    protocols = ['onedatafs']

    def open_fs(self, fs_url, parse_result, writeable, create, cwd):
        ofs = urlparse(fs_url)
        if ofs.scheme != 'onedatafs':
            raise 'Invalid OnedataFS scheme'

        host = ofs.hostname
        port = ofs.port
        token = parse_qs(o.query)['token']

        onedatafs = OnedataFS(
            host,
            token,
            port=port
        )
        return onedatafs
