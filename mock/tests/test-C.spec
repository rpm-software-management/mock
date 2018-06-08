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
mkdir -p %{buildroot}/%{_sysconfdir}
echo "A is here" >> %{buildroot}/%{_sysconfdir}/%{name}-installed

%files
%{_sysconfdir}/%{name}-installed

%changelog
* Sat May 26 2018 Sam Fowler <sfowler at redhat.com>
- Remove unnecessary lines
* Thu May 16 2013 Seth Vidal <skvidal at fedoraproject.org>
- test pkg
