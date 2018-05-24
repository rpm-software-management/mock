Summary: test-A
Name: test-A
Version: 1.1
Release: 0
License: GPL
Group: System Environment/Base
BuildRequires: test-B

%description
Test packge for mockchain building chains




%prep

%build

%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/etc
touch $RPM_BUILD_ROOT/etc/%{name}-installed
echo "A is here" >> $RPM_BUILD_ROOT/etc/%{name}-installed

%clean
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT


%files
%defattr(-, root, root)
%{_sysconfdir}/%{name}-installed

%changelog
* Thu May 16 2013 Seth Vidal <skvidal at fedoraproject.org>
- test pkg
