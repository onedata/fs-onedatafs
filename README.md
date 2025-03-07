# OnedataFS

OnedataFS is a [PyFilesystem](https://www.pyfilesystem.org/) interface to
[Onedata](https://onedata.org) virtual file system.

As a PyFilesystem concrete class, [OnedataFS](https://github.com/onedata/fs-onedatafs/)
allows you to work with Onedata in the same way as any other supported filesystem.

## Lightweight alternative

OnedataFS contains all C++ storage drivers for direct data access, a.k.a. 
[DirectIO](https://onedata.org/#/home/documentation/21.02/user-guide/oneclient[direct-io-and-proxy-io-modes].html).
Because of that, it cannot be installed using pip. If you are using ProxyIO
(data access through a Oneprovider), consider using a lightweight cousin of 
OnedataFS - [OnedataRESTFS](https://github.com/onedata/onedatarestfs). It has 
identical functionality, can be installed using pip, and has minimal dependencies.
OnedataRESTFS uses the Onedata REST API behind the scenes, yielding comparable 
performance for ProxyIO data access mode.

## Installing

See the [docs](https://onedata.org/#/home/documentation/21.02/user-guide/onedatafs.html).

## Opening a OnedataFS

Open an OnedataFS by explicitly using the constructor:

```python
from fs.onedatafs import OnedataFS
onedata_provider_host = "..."
onedata_access_token = "..."
odfs = OnedataFS(onedata_provider_host, onedata_access_token)
```

Or with a FS URL:

```python
from fs import open_fs
odfs = open_fs('onedatafs://HOST?token=...')
```

Consult the [docs](https://onedata.org/#/home/documentation/21.02/user-guide/onedatafs[usage].html)
for further information.

## Extended attributes

Onedata FS supports in addition to standard PyFilesystem API operations
on metadata via POSIX compatible extended attributes API.


## Documentation

- [PyFilesystem Wiki](https://www.pyfilesystem.org)
- [Onedata Homepage](https://onedata.org)
- [OnedataFS Documentation](https://onedata.org/#/home/documentation/21.02/user-guide/onedatafs.html)
