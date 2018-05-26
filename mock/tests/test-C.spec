Summary: test-C
Name: test-C
Version: 1.1
Release: 0
License: GPL

%description
Test package for mockchain building chains

%prep

%build

%install
[ "$RPM_BUILD_ROOT" != "/" ] && rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/etc
echo "A is here" >> %{_sysconfdir}/%{name}-installed

%files

%changelog
* Sat May 26 2018 Sam Fowler <sfowler at redhat.com>
- Remove unnecessary lines
* Thu May 16 2013 Seth Vidal <skvidal at fedoraproject.org>
- test pkg
