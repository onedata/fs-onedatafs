Release notes for project fs-onedatafs
======================================

CHANGELOG
---------

### 21.02.0-alpha26

-   **VFS-8828** Fixed conda packages for the stable branch 20.02.\*,
    starting with version 20.02.15 and Python 3.9.

### 21.02.0-alpha25

-   **VFS-8872** Dropped support for Python2 in OnedataFS.
-   **VFS-8862** Update conda package dependencies to conda-forge and
    Python 3.9.
-   **VFS-8823** Fixed improper destruction of OnedataFS instances,
    resulting in possible deadlocks during deletion of the OnedataFS
    object.


### 21.02.0-alpha24

### 21.02.0-alpha23

-   **VFS-8318** Fixed conda packaging for oneclient and onedatafs,
    switched dependencies to conda-forge channel.
-   **VFS-8073** Upgrade folly, wangle and proxygen libraries to version
    2021.01.04.00.

### 21.02.0-alpha22

### 21.02.0-alpha21

### 21.02.0-alpha20

### 21.02.0-alpha19

### 21.02.0-alpha18

### 21.02.0-alpha17

### 21.02.0-alpha16

### 21.02.0-alpha14

### 21.02.0-alpha13

### 21.02.0-alpha12

### 21.02.0-alpha11

### 21.02.0-alpha10

### 21.02.0-alpha9

### 21.02.0-alpha8

### 21.02.0-alpha7

### 21.02.0-alpha6

### 21.02.0-alpha5

### 21.02.0-alpha4

### 21.02.0-alpha3

### 21.02.0-alpha2

### 20.02.17

### 20.02.16

-   **VFS-8828** Fixed conda packages for the stable branch 20.02.\*,
    starting with version 20.02.15 and Python 3.9.
-   **VFS-8823** Fixed improper destruction of OnedataFS instances,
    resulting in possible deadlocks during deletion of the OnedataFS
    object.

### 20.02.15

### 20.02.14

### 20.02.13

### 20.02.12

### 20.02.11

### 20.02.10

### 20.02.9

### 20.02.8

### 20.02.7

-   **VFS-7466** Fixed PyFilesystem opener entrypoint allowing to create
    OnedataFS instances in Python using urls of the form
    \'onedatafs://HOST:PORT?token=\...\'.

### 20.02.6

-   **VFS-7119** Dropped support for OnedataFS Anaconda packages for
    Python 2, due to Python 2 EOL.

### 20.02.5

### 20.02.4

### 20.02.3

### 20.02.2

### 20.02.1

### 20.02.0-beta4

### 20.02.0-beta3

### 19.02.5

### 19.02.4

### 19.02.3

### 19.02.2

* VFS-6264 Added support for Python memory views
* VFS-6012 Fixed cli_args argument handling
* VFS-6012 Removed io_trace_log from OnedataFs arguments
* VFS-6012 Added new OnedataFS constructor arguments
