#
# Spec file for mock buildsys configuration
#
Summary: The base set of packages for a mock chroot
Name: buildsys-build
Version: 0.5
Release: 1%{?dist}
License: GPL
Group: Development/Build Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

# packages that populate a buildsys chroot
Requires: coreutils
Requires: findutils
Requires: openssh-server
Requires: which
Requires: bash
Requires: glibc
Requires: python
Requires: createrepo
Requires: rpm
Requires: rpm-python
Requires: initscripts
Requires: chkconfig
Requires: fedora-release
Requires: buildsys-macros
Requires: perl-XML-SAX
Requires: tar
Requires: diffstat
Requires: perl-XML-Parser
Requires: perl-XML-Dumper
Requires: udev
Requires: gdb
Requires: automake15
Requires: gcc
Requires: intltool
Requires: redhat-rpm-config
Requires: automake17
Requires: pkgconfig
Requires: gettext
Requires: automake
Requires: automake16
Requires: automake14
Requires: patchutils
Requires: ctags
Requires: gcc-c++
Requires: flex
Requires: unzip
Requires: bzip2
Requires: cpio
Requires: byacc
Requires: doxygen
Requires: indent
Requires: strace
Requires: rpm-build
Requires: elfutils
Requires: patch
Requires: bison
Requires: diffutils
Requires: gzip
Requires: libtool
Requires: autoconf
Requires: make
Requires: binutils

%description
The base set of packages for a mock chroot

%prep
%build
%install
%clean

%files
%defattr(-,root,root,-)
%doc
