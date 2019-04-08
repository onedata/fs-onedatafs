.. OnedataFS documentation master file, created by
   sphinx-quickstart on Sat Aug  5 12:55:45 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

OnedataFS
====

OnedataFS is a `PyFilesystem interface
<https://docs.pyfilesystem.org/en/latest/reference/base.html>`_ to
Onedata virtual filesystem.

As a PyFilesystem concrete class, OnedataFS allows you to work with Onedata in the same as any other supported filesystem.

Installing
==========

OnedataFS may be installed from pip with the following command::

    pip install fs-onedatafs

This will install the most recent stable version.

Alternatively, if you want the cutting edge code, you can check out
the GitHub repos at https://github.com/pyfilesystem/OnedataFS


Opening an Onedata Filesystem
========================

There are two options for constructing a :ref:`OnedataFS` instance. The simplest way
is with an *opener*, which is a simple URL like syntax. Here is an example::

    from fs import open_fs
    odfs = open_fs('onedatafs://10.1.1.1?token=TOKEN')

For more granular control, you may import the OnedataFS class and construct
it explicitly::

    from fs_OnedataFS import OnedataFS
    OnedataFS = OnedataFS('10.1.1.1', 'TOKEN', force_proxy_io=True, no_buffer=True)

OnedataFS Constructor
----------------

.. autoclass:: fs_onedatafs.OnedataFS
    :members:


More Information
================
See `Onedata home page <https://onedata.org>`_ for more information about Onedata.

See the `PyFilesystem Docs <https://docs.pyfilesystem.org>`_ for documentation on the rest of the PyFilesystem interface.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
