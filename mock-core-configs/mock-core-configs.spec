# mock group id allocate for Fedora
%global mockgid 135

Name:		mock-core-configs
Version:	28.4
Release:	1%{?dist}
Summary:	Mock core config files basic chroots

License:	GPLv2+
URL:		https://github.com/rpm-software-management/mock/
# Source is created by
# git clone https://github.com/rpm-software-management/mock.git
# cd mock/mock-core-configs
# git reset --hard %{name}-%{version}
# tito build --tgz
Source:		https://github.com/rpm-software-management/mock/releases/download/%{name}-%{version}-1/%{name}-%{version}.tar.gz
BuildArch:	noarch

# distribution-gpg-keys contains GPG keys used by mock configs
Requires:	distribution-gpg-keys >= 1.22

Requires(pre):	shadow-utils
Requires(post): coreutils
%if 0%{?fedora} || 0%{?mageia} || 0%{?rhel} > 7
# to detect correct default.cfg
Requires(post):	python3-dnf
Requires(post):	python3-hawkey
Requires(post):	system-release
Requires(post):	python3
Requires(post):	sed
%endif
%if 0%{?rhel} && 0%{?rhel} <= 7
# to detect correct default.cfg
Requires(post):	python
Requires(post):	yum
Requires(post):	/etc/os-release
%endif

%description
Config files which allow you to create chroots for:
 * Fedora
 * Epel
 * Mageia
 * Custom chroot
 * OpenSuse Tumbleweed and Leap

%prep
%setup -q


%build
# nothing to do here


%install
mkdir -p %{buildroot}%{_sysconfdir}/mock
cp -a etc/mock/*.cfg %{buildroot}%{_sysconfdir}/mock

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
    # fedora and rhel7+
    if grep -Fiq Rawhide /etc/os-release; then
        ver=rawhide
    # mageia
    elif [ -s /etc/mageia-release ]; then
        if grep -Fiq Cauldron /etc/mageia-release; then
           ver=cauldron
        fi
    else
        ver=$(source /etc/os-release && echo $VERSION_ID | cut -d. -f1 | grep -o '[0-9]\+')
    fi
else
    # something obsure, use buildtime version
    ver=%{?rhel}%{?fedora}%{?mageia}
fi
%if 0%{?fedora} || 0%{?mageia} || 0%{?rhel} > 7
if [ -s /etc/mageia-release ]; then
    mock_arch=$(sed -n '/^$/!{$ s/.* \(\w*\)$/\1/p}' /etc/mageia-release)
else
    mock_arch=$(python3 -c "import dnf.rpm; import hawkey; print(dnf.rpm.basearch(hawkey.detect_arch()))")
fi
%else
mock_arch=$(python -c "import rpmUtils.arch; baseArch = rpmUtils.arch.getBaseArch(); print baseArch")
%endif
cfg=%{?fedora:fedora}%{?rhel:epel}%{?mageia:mageia}-$ver-${mock_arch}.cfg
if [ -e %{_sysconfdir}/mock/$cfg ]; then
    if [ "$(readlink %{_sysconfdir}/mock/default.cfg)" != "$cfg" ]; then
        ln -s $cfg %{_sysconfdir}/mock/default.cfg 2>/dev/null || ln -s -f $cfg %{_sysconfdir}/mock/default.cfg.rpmnew
    fi
else
    echo "Warning: file %{_sysconfdir}/mock/$cfg does not exist."
    echo "         unable to update %{_sysconfdir}/mock/default.cfg"
fi
:


%files -f %{name}.cfgs
%license COPYING
%dir  %{_sysconfdir}/mock
%ghost %config(noreplace,missingok) %{_sysconfdir}/mock/default.cfg

%changelog
* Wed May 02 2018 Miroslav Suchý <msuchy@redhat.com> 28.4-1
- requires distribution-gpg-keys with opensuse keys
- Add initial openSUSE distribution targets (ngompa13@gmail.com)
- provide fedora-29 configs as symlinks to fedora-rawhide
- use cp instead of install to preserve symlinks
- use correct url for local repos for s390x for F27+ [RHBZ#1553678]
- add CentOS SCL repositories to EPEL 7 (aarch64 & ppc64le)
  (tmz@pobox.com)

* Thu Mar 01 2018 Miroslav Suchý <msuchy@redhat.com> 28.3-1
- bump up releasever in rawhide configs
- add CentOS SCL repositories to EPEL 6 & 7 (x86_64)
  (tmz@pobox.com)

* Mon Jan 22 2018 Miroslav Suchý <msuchy@redhat.com> 28.2-1
- fix wrong RHEL condition

* Mon Jan 22 2018 Miroslav Suchý <msuchy@redhat.com> 28.1-1
- bump up version to 28.1

* Mon Jan 22 2018 Miroslav Suchý <msuchy@redhat.com> 27.5-1
- add fedora 28 configs
- remove failovermethod=priority for repos which use dnf
- remove fedora 24 configs
- set skip_if_unavailable=False for all repos

* Mon Oct 09 2017 Miroslav Suchý <msuchy@redhat.com> 27.4-1
- Fix mock & mock-core-config specs to support Mageia (ngompa13@gmail.com)
- Ensure mock-core-configs will select the right default on Mageia
  (ngompa13@gmail.com)

* Wed Sep 27 2017 Miroslav Suchý <msuchy@redhat.com> 27.3-1
- use primary key for F-27+ on s390x (dan@danny.cz)

* Tue Sep 12 2017 Miroslav Suchý <msuchy@redhat.com> 27.2-1
- add source url
- grammar fix

* Thu Sep 07 2017 Miroslav Suchý <msuchy@redhat.com> 27.1-1
- Split from Mock package.


