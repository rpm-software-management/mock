Name:           test-F
Version:        0
Release:        1%{?dist}
Summary:        Test of external builddeps

License:        WTFPL

BuildRequires:  external:pypi:copr
BuildRequires:  external:pypi:bokeh
BuildRequires:  external:crate:bat


%description
Nothing to see here

%prep


%build


%install


%files


%changelog
* Sun Oct 18 01:00:13 CEST 2020 msuchy <msuchy@redhat.com>
- initial package
