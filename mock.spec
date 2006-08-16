Summary: Builds packages inside chroots
Name: mock
Version: 0.7
Release: 2%{?dist}
License: GPL
Group: Development/Tools
Source: http://fedoraproject.org/projects/mock/releases/%{name}-%{version}.tar.gz
URL: http://fedoraproject.org/wiki/Projects/Mock
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
Requires: python, yum >= 2.2.1
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
    else
        ln -s fedora-development-i386-core.cfg default.cfg
    fi
fi

cd $RPM_BUILD_ROOT/%{_bindir}

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
%attr(04750, root, mock) %{_bindir}/%{name}
%{_bindir}/%{name}.py*
%{_libexecdir}/mock-yum
%{_mandir}/man1/mock.1*
%attr(02775, root, mock) %dir /var/lib/mock
%{_libdir}/libselinux-mock.so


%changelog
* Wed Aug 16 2006 Clark Williams <williams@redhat.com> - 0.7-2
- Added buildsys-build.spec to docs
- Added disttag
- Bumped release number

* Wed Jun 28 2006 Clark Williams <williams@redhat.com> - 0.7-1
- updated version to 0.7
- removed /usr/sbin/mock-helper
- added /usr/bin/mock launcher

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
