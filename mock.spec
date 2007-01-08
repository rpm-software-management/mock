Summary: Builds packages inside chroots
Name: mock
Version: 0.6.10
Release: 1%{?dist}
License: GPL
Group: Development/Tools
Source: http://fedoraproject.org/projects/mock/releases/%{name}-%{version}.tar.gz
URL: http://fedoraproject.org/wiki/Projects/Mock
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
Requires: python, yum >= 3.0
Requires(pre): shadow-utils
BuildRequires: libselinux-devel


%description
Mock takes a srpm and builds it in a chroot

%prep
%setup -q

%build
make

%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install
# make the default.cfg link
cd $RPM_BUILD_ROOT/%{_sysconfdir}/%{name}

%if 0%{?fedora:1}
if [ -f fedora-%{fedora}-%{_target_cpu}-core.cfg ]; then
        ln -s fedora-%{fedora}-%{_target_cpu}-core.cfg default.cfg
fi
%endif

# if we haven't created a default link yet, try to do so as devel
if [ ! -f default.cfg ]; then
    if [ -f fedora-development-%{_target_cpu}-core.cfg ]; then
        ln -s fedora-development-%{_target_cpu}-core.cfg default.cfg
    elif [ -f fedora-devel-%{_target_cpu}-core.cfg ]; then
        ln -s fedora-devel-%{_target_cpu}-core.cfg default.cfg
    elif [ -f fedora-development-i386-core.cfg ]; then
        ln -s fedora-development-i386-core.cfg default.cfg
    elif [ -f fedora-devel-i386-core.cfg ]; then
        ln -s fedora-devel-i386-core.cfg default.cfg
    fi
fi

%clean
rm -rf $RPM_BUILD_ROOT

%pre
if [ $1 -eq 1 ]; then
    groupadd -r mock >/dev/null 2>&1 || :
fi

%files
%defattr(-, root, root)
%doc README ChangeLog buildsys-build.spec
%dir  %{_sysconfdir}/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/*.cfg
%{_bindir}/%{name}
%{_libexecdir}/mock-yum
%{_mandir}/man1/mock.1*
%attr(04750, root, mock) %{_sbindir}/mock-helper
%attr(02775, root, mock) %dir /var/lib/mock
%{_libdir}/libselinux-mock.so

%changelog
* Mon Jan  8 2007 Clark Williams <williams@redhat.com> - 0.6.10-1
- Added Josh Boyer's EPEL config files

* Tue Nov 21 2006 Clark Williams <williams@redhat.com> - 0.6.9-1
- applied Eric Work's patch to fix defaults vs. command line option problem
  (BZ 215168)
- use /etc/mock/defaults.cfg if --configdir specified and no defaults found
  in the specified configdir
  (BZ 209407)
- applied Jesse Keatings patch for arch specifi config files
  (BZ 213516)

* Mon Oct 30 2006 Clark Williams <williams@redhat.com> - 0.6.8-1
- respun tarballs without buildsys rpms

* Mon Oct 30 2006 Clark Williams <williams@redhat.com> - 0.6.7-1
- updated for FC6 release

* Sat Oct 21 2006 Clark Williams <williams@redhat.com> - 0.6.6-1
- bumped version to 0.6.6 (fixed tarball problem)

* Mon Sep 11 2006 Clark Williams <williams@redhat.com> - 0.6.5-1
- changed version number for patch from Karanbir Singh
  (rpm workaround on CentOS 4.4)

* Tue Aug 29 2006 Clark Williams <williams@redhat.com> - 0.6.3-1
- changed version number to indicate fix for bz 204051

* Tue Aug 29 2006 Clark Williams <williams@redhat.com> - 0.6.2-2
- bumped revision for bz 204051

* Wed Aug 23 2006 Clark Williams <williams@redhat.com> - 0.6.2-1
- Updated README
- Fixed link problem in etc/Makefile
- Bumped version number

* Wed Aug 16 2006 Clark Williams <williams@redhat.com>
- Added buildsys-build specfile to docs
- Added disttag
- Bumped release number

* Wed Jun  7 2006 Seth Vidal <skvidal at linux.duke.edu>
- version update

* Tue Apr 11 2006 Seth Vidal <skvidal at linux.duke.edu>
- specfile version iterate

* Tue Dec 27 2005 Seth Vidal <skvidal@phy.duke.edu>
- add patch from Andreas Thienemann - adds man page

* Sat Jun 11 2005 Seth Vidal <skvidal@phy.duke.edu>
- security fix in mock-helper

* Sun Jun  5 2005 Seth Vidal <skvidal@phy.duke.edu>
- clean up packaging for fedora extras

* Thu May 19 2005 Seth Vidal <skvidal@phy.duke.edu>
- second packaging and backing down the yum ver req

* Sun May 15 2005 Seth Vidal <skvidal@phy.duke.edu>
- first version/packaging
