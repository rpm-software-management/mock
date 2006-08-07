#
# Spec file for mock buildsys configuration
#
Summary: The base set of packages for a mock chroot
Name: buildsys-build
Version: 0.5
Release: 3%{?dist}
License: GPL
Group: Development/Build Tools
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

# packages that populate a buildsys chroot
Requires: bash
Requires: buildsys-macros
Requires: bzip2
Requires: cpio
Requires: diffutils
Requires: gcc
Requires: gcc-c++
Requires: gzip
Requires: make
Requires: patch
Requires: perl
Requires: rpm-build
Requires: sed
Requires: tar
Requires: unzip
Requires: which

# The rather long-winded format of the conditionals is needed for compatbility
# with old rpm versions such as were supplied with Red Hat Linux 7
%if "%{?fedora}" != ""
Requires: coreutils
Requires: fedora-release
Requires: redhat-rpm-config
%if "%{?fedora}" == "4" ||  "%{?fedora}" == "3" || "%{?fedora}" == "2" || "%{?fedora}" == "1" || "%{?el}" == "3"
Requires: elfutils
%endif
%if "%{?fedora}" == "4" ||  "%{?fedora}" == "3" || "%{?el}" == "4"
Requires: python
%endif
%endif

%if "%{?rhl}" != "" || "%{?el}" != ""
Requires: redhat-release
%if "%{?rhl}" == "9" || "%{?el}" == "3" || "%{?el}" == "4"
Requires: coreutils
Requires: elfutils
Requires: redhat-rpm-config
%else
Requires: file
Requires: fileutils
Requires: findutils
%endif
# Cater for alternative versions of buildsys-macros
%if "%{?rhl}" == "8" || "%{?rhl}" == "8.0" || "%{?el}" != ""
Requires: redhat-rpm-config
%endif
%endif

%description
The base set of packages for a mock chroot.

%build

%install
%{__rm} -rf %{buildroot}
%{__mkdir_p} %{buildroot}

%clean
%{__rm} -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc

%changelog
* Mon Aug  7 2006 Clark Williams <williams@redhat.com> - 0.5-3
- added rhel build tags

* Sun Aug 06 2006 Thorsten Leemhuis <fedora[AT]leemhuis.info> - 0.5-3
- For FC4 and FC3 include python

* Thu Jun 22 2006 Paul Howarth <paul@city-fan.org> - 0.5-2
- For FC < 5 or Red Hat Linux 9, include elfutils
- For non-Fedora distrbutions, require redhat-release instead of fedora-release
- For Red Hat Linux 8 and earlier, require fileutils instead of coreutils
- Red Hat Linux 8 requires findutils for brp-strip
