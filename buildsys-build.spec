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
Requires: bash
Requires: buildsys-macros
Requires: bzip2
Requires: coreutils
Requires: cpio
Requires: diffutils
Requires: fedora-release
Requires: gcc
Requires: gcc-c++
Requires: gzip
Requires: make
Requires: patch
Requires: perl
Requires: rpm-build
Requires: redhat-rpm-config
Requires: sed
Requires: tar
Requires: unzip
Requires: which

%description
The base set of packages for a mock chroot

%build
%install
%clean

%files
%defattr(-,root,root,-)
%doc
