# mock group id allocate for Fedora
%global mockgid 135

Name:		mock-core-configs
Version:	27.0
Release:	1%{?dist}
Summary:	Mock core config files basic chroots

License:	GPLv2+
URL:		https://github.com/rpm-software-management/mock/
# Source is created by
# git clone https://github.com/rpm-software-management/mock.git
# cd mock/mock-core-configs
# git reset --hard %{name}-%{version}
# tito build --tgz
Source:		%{name}-%{version}.tar.gz
BuildArch:	noarch
Requires(pre):	shadow-utils
Requires(post): coreutils
%if 0%{?fedora}
# to detect correct default.cfg
Requires(post):	python3-dnf
Requires(post):	python3-hawkey
Requires(post):	system-release
Requires(post):	python3
%endif
%if 0%{?rhel}
# to detect correct default.cfg
Requires(post):	python
Requires(post):	yum
Requires(post):	/etc/os-release
%endif

%description
Config files which allows you to create chroots for:
 * Fedora
 * Epel
 * Mageia
 * Custom chroot

%prep
%setup -q


%build
# nothing to do here


%install
mkdir -p %{buildroot}%{_sysconfdir}/mock
install -pm 0644 etc/mock/*.cfg %{buildroot}%{_sysconfdir}/mock

# generate files section with config - there is many of them
echo "%defattr(0644, root, mock)" > %{name}.cfgs
find %{buildroot}%{_sysconfdir}/mock -name "*.cfg" \
    | sed -e "s|^%{buildroot}|%%config(noreplace) |" >> %{name}.cfgs
# just for %%ghosting purposes
ln -s fedora-rawhide-x86_64.cfg %{buildroot}%{_sysconfdir}/mock/default.cfg
# bash-completion
if [ -d %{buildroot}%{_datadir}/bash-completion ]; then
    echo %{_datadir}/bash-completion/completions/mock >> %{name}.cfgs
    echo %{_datadir}/bash-completion/completions/mockchain >> %{name}.cfgs
elif [ -d %{buildroot}%{_sysconfdir}/bash_completion.d ]; then
    echo %{_sysconfdir}/bash_completion.d/mock >> %{name}.cfgs
fi

%pre
# check for existence of mock group, create it if not found
getent group mock > /dev/null || groupadd -f -g %mockgid -r mock
exit 0

%post
if [ -s /etc/os-release ]; then
    # fedora and rhel7
    if grep -Fiq Rawhide /etc/os-release; then
        ver=rawhide
    else
        ver=$(source /etc/os-release && echo $VERSION_ID | cut -d. -f1 | grep -o '[0-9]\+')
    fi
else
    # something obsure, use buildtime version
    ver=%{?rhel}%{?fedora}
fi
%if 0%{?fedora}
mock_arch=$(python3 -c "import dnf.rpm; import hawkey; print(dnf.rpm.basearch(hawkey.detect_arch()))")
%else
mock_arch=$(python -c "import rpmUtils.arch; baseArch = rpmUtils.arch.getBaseArch(); print baseArch")
%endif
cfg=%{?fedora:fedora}%{?rhel:epel}-$ver-${mock_arch}.cfg
if [ -e %{_sysconfdir}/mock/$cfg ]; then
    if [ "$(readlink %{_sysconfdir}/mock/default.cfg)" != "$cfg" ]; then
        ln -s $cfg %{_sysconfdir}/mock/default.cfg 2>/dev/null || ln -s -f $cfg %{_sysconfdir}/mock/default.cfg.rpmnew
    fi
else
    echo "Warning: file %{_sysconfdir}/mock/$cfg does not exists."
    echo "         unable to update %{_sysconfdir}/mock/default.cfg"
fi
:


%files -f %{name}.cfgs
%defattr(-, root, root, -)
%license COPYING
%dir  %{_sysconfdir}/mock
%ghost %config(noreplace,missingok) %{_sysconfdir}/mock/default.cfg

%changelog

