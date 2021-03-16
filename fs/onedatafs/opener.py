# coding: utf-8
"""Defines the OnedataFS opener."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

__all__ = ["OnedataFSOpener"]

from fs.opener import Opener

from six.moves.urllib.parse import parse_qs, urlparse

from ._onedatafs import OnedataFS


class OnedataFSOpener(Opener):
    """
    Opener for OnedataFS.

    Implementation of PyFilesystem opener for OnedataFS. Allows to
    pass URI's in the form:
    `onedatafs://ONEPROVIDER_HOST:PORT?token=ACCESS_TOKEN&...`
    """

    protocols = ["onedatafs"]

    def open_fs(self, fs_url, parse_result, writeable, create, cwd):
        """Create instance of OnedataFS using opener URI."""
        ofs = urlparse(fs_url)
        if ofs.scheme != "onedatafs":
            raise "Invalid OnedataFS scheme"

        host = ofs.hostname
        port = ofs.port or 443
        args = parse_qs(ofs.query)
        token = args["token"][0]
        del args["token"]
        cli_args = ""
        for k in args:
            v = args[k][0]
            if v == 'false':
                continue
            elif v == 'true':
                cli_args += " --" + k
            else:
                cli_args += " --" + k + " " + v

        return OnedataFS(host, token, port=port, cli_args=cli_args)
