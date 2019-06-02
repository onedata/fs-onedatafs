OnedataFS
=========

OnedataFS is a `PyFilesystem <https://www.pyfilesystem.org/>`__
interface to `Onedata <https://onedata.org>`__ virtual file system.

As a PyFilesystem concrete class,
`OnedataFS <https://github.com/onedata/fs-onedatafs/>`__ allows you to
work with Onedata in the same way as any other supported filesystem.

Installing
----------

You can install OnedataFS from pip as follows:

::

   pip install fs-onedatafs

Opening a OnedataFS
-------------------

Open an OnedataFS by explicitly using the constructor:

.. code:: python

   from fs_onedatafs import OnedataFS
   onedata_provider_host = "..."
   onedata_access_token = "..."
   odfs = OnedataFS(onedata_provider_host, onedata_access_token)

Or with a FS URL:

.. code:: python

     from fs import open_fs
     odfs = open_fs('onedatafs://HOST?token=...')

Extended attributes
-------------------

Onedata FS supports in addition to standard PyFilesystem API operations
on metadata via POSIX compatible extended attributes API.

Documentation
-------------

-  `PyFilesystem Wiki <https://www.pyfilesystem.org>`__
-  `OnedataFS
   Reference <http://fs-onedatafs.readthedocs.io/en/latest/>`__
-  `Onedata Homepage <https://onedata.org>`__
