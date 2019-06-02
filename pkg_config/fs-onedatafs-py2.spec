%global _scl_prefix /opt/onedata

%{?scl:%scl_package python2-fs-onedatafs}
%{!?scl:%global pkg_name %{name}}

%define version {{version}}
%define unmangled_version %{version}
%define onedatafs_version {{onedatafs_version}}
%define release 1

Summary: Onedata filesystem implementation for PyFilesystem2
Name: %{?scl_prefix}python2-fs-onedatafs
Version: %{version}
Release: 1%{?dist}
Source0: fs-onedatafs-%{version}.tar.gz
Source1: __init__.py
License: MIT
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Onedata <support@onedata.org>
Url: https://github.com/onedata/fs-onedatafs

Requires: epel-release
Requires: scl-utils
Requires: %scl_require_package %{scl} python2-onedatafs = %{onedatafs_version}
Requires: python-six
Requires: python-typing
BuildRequires: python
BuildRequires: python-setuptools

%description
OnedataFS is an implementation of PyFilesystem interface to Onedata virtual
file system.  OnedataFS allows you to work with Onedata using PyFilesystem API,
directly without any local mountpoints.

%prep
%setup -n fs-onedatafs-%{version}

%build
python2 setup.py build

%install
python2 setup.py install --single-version-externally-managed -O1 --root=$RPM_BUILD_ROOT --prefix=/opt/onedata/%{scl}/root/usr --record=INSTALLED_FILES
install -p -D -m 644 %{SOURCE1} $RPM_BUILD_ROOT/opt/onedata/%{scl}/root/usr/lib/python2.7/site-packages/fs/__init__.py

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
/opt/onedata/%{scl}/root/usr/lib/python2.7/site-packages/fs/__init__.*
%defattr(-,root,root)
