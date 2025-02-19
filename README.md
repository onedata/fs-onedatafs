# OnedataFS

OnedataFS is a [PyFilesystem](https://www.pyfilesystem.org/) interface to
[Onedata](https://onedata.org) virtual file system.

As a PyFilesystem concrete class, [OnedataFS](https://github.com/onedata/fs-onedatafs/)
allows you to work with Onedata in the same way as any other supported filesystem.

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
