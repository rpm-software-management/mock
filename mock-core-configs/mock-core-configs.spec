# mock group id allocate for Fedora
%global mockgid 135

Name:       mock-core-configs
Version:    31.7
Release:    1%{?dist}
Summary:    Mock core config files basic chroots

License:    GPLv2+
URL:        https://github.com/rpm-software-management/mock/
# Source is created by
# git clone https://github.com/rpm-software-management/mock.git
# cd mock/mock-core-configs
# git reset --hard %{name}-%{version}
# tito build --tgz
Source:     https://github.com/rpm-software-management/mock/releases/download/%{name}-%{version}-1/%{name}-%{version}.tar.gz
BuildArch:  noarch

# distribution-gpg-keys contains GPG keys used by mock configs
Requires:   distribution-gpg-keys >= 1.29

Requires(post): coreutils
%if 0%{?fedora} || 0%{?mageia} || 0%{?rhel} > 7
# to detect correct default.cfg
Requires(post): python3-dnf
Requires(post): python3-hawkey
Requires(post): system-release
Requires(post): python3
Requires(post): sed
%endif
Requires(pre):  shadow-utils
%if 0%{?rhel} && 0%{?rhel} <= 7
# to detect correct default.cfg
Requires(post): python
Requires(post): yum
Requires(post): /etc/os-release
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
mkdir -p %{buildroot}%{_sysusersdir}

mkdir -p %{buildroot}%{_sysconfdir}/mock/eol/templates
mkdir -p %{buildroot}%{_sysconfdir}/mock/templates
cp -a etc/mock/*.cfg %{buildroot}%{_sysconfdir}/mock
cp -a etc/mock/templates/*.tpl %{buildroot}%{_sysconfdir}/mock/templates
cp -a etc/mock/eol/*cfg %{buildroot}%{_sysconfdir}/mock/eol
cp -a etc/mock/eol/templates/*.tpl %{buildroot}%{_sysconfdir}/mock/eol/templates

# generate files section with config - there is many of them
echo "%defattr(0644, root, mock)" > %{name}.cfgs
find %{buildroot}%{_sysconfdir}/mock -name "*.cfg" -o -name '*.tpl' \
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
%dir  %{_sysconfdir}/mock/eol
%dir  %{_sysconfdir}/mock/templates
%ghost %config(noreplace,missingok) %{_sysconfdir}/mock/default.cfg

%changelog
* Fri Nov 01 2019 Miroslav Suchý <msuchy@redhat.com> 31.7-1
- Add configs for epel8-playground (mmathesi@redhat.com)
- add 3 base packages to epel-playground buildroot [RHBZ#1764445]
- add 3 base packages to epel buildroot [RHBZ#1764445]

* Fri Oct 04 2019 Miroslav Suchý <msuchy@redhat.com> 31.6-1
- disable modular repo for f29
- configure podman containers for Fedora, EPEL and Mageia (frostyx@email.cz)
- Fix baseurl typo in centos-stream config (dollierp@redhat.com)

* Thu Sep 26 2019 Miroslav Suchý <msuchy@redhat.com> 31.5-1
- expand contentdir for now
- expand $stream for now
- add extra_chroot_dirs to centos8
- use dnf for centos8
- add centos-stream-8
- rhelepel: reuse epel-8.tpl (praiskup@redhat.com)
- Add Amazon Linux 2 configs (haroldji@amazon.com)
- centos-8: enable PowerTools repo (praiskup@redhat.com)

* Tue Sep 24 2019 Miroslav Suchý <msuchy@redhat.com> 31.4-1
- provide explanation why modular repos are disabled
- add epel-8
- Changing cfg files for fedora rawhide to use tpl file
  (sisi.chlupova@gmail.com)
- Changing cfg files for fedora 31 to use tpl file (sisi.chlupova@gmail.com)
- Changing cfg files for fedora 29 to use tpl file (sisi.chlupova@gmail.com)

* Sat Sep 14 2019 Miroslav Suchý <msuchy@redhat.com> 31.3-1
- mock-core-configs: installroot fix for fedora 31+ i386 (praiskup@redhat.com)
- Moving templates into templates dir (sisi.chlupova@gmail.com)
- Changing cfg files for fedora 30 to use tpl file (sisi.chlupova@gmail.com)
- Moving fedora-30-x86_64.cfg into templates/fedora-30.tpl
  (sisi.chlupova@gmail.com)
- baseurl for f30-build was changed (sisi.chlupova@gmail.com)
- no i686 repositories [GH#325]
- adds equation sign to --disablerepo (thrnciar@reedhat.com)

* Mon Aug 26 2019 Miroslav Suchý <msuchy@redhat.com> 31.2-1
- revert sysusers setting [RHBZ#1740545]
- add rhelepel-8 configs (praiskup@redhat.com)
- add RHEL 7/8 (praiskup@redhat.com)

* Mon Aug 19 2019 Miroslav Suchý <msuchy@redhat.com> 31.1-1
- add fedora 31 configs and rawhide is now 32
- Add local-source repo definition to Fedora Rawhide (miro@hroncok.cz)

* Mon Aug 19 2019 Miroslav Suchý <msuchy@redhat.com>
- add fedora 31 configs and rawhide is now 32
- Add local-source repo definition to Fedora Rawhide (miro@hroncok.cz)

* Thu Aug 08 2019 Miroslav Suchý <msuchy@redhat.com> 30.5-1
- disable updates-modulare repos for now
- buildrequire systemd-srpm-macros to get _sysusersdir
- removed info about metadata expire (khoidinhtrinh@gmail.com)
- added updates-modular to 29 and 30 (khoidinhtrinh@gmail.com)
- replace groupadd using sysusers.d
- core-configs: epel-7 profiles to use mirrorlists (praiskup@redhat.com)
- EOL Fedora 28
- do not protect packages in chroot [GH#286]
- Fix value for dist for OpenMandriva 4.0 configs (ngompa13@gmail.com)
- Add initial OpenMandriva distribution targets (ngompa13@gmail.com)

* Thu Jun 06 2019 Miroslav Suchý <msuchy@redhat.com> 30.4-1
- Add 'fastestmirror=1' to Mageia mock configs (ngompa13@gmail.com)
- bootstrap: disable sclo* repos for epel --installroot (praiskup@redhat.com)
- drop Fedora ppc64 configs [RHBZ#1714489]

* Thu May 16 2019 Miroslav Suchý <msuchy@redhat.com> 30.3-1
- Allow AArch64 systems to build 32-bit ARM packages (ngompa13@gmail.com)
- Fix openSUSE Tumbleweed DistTag definition (ngompa13@gmail.com)

* Fri Mar 01 2019 Miroslav Suchý <msuchy@redhat.com> 30.2-1
- disable modular repos
- Add openSUSE Leap AArch64 configs (ngompa13@gmail.com)
- Add openSUSE Leap 15.1 configuration (ngompa13@gmail.com)
- Bump releasever in Cauldron to 8 and create symlinks to cauldron configs
  (ngompa13@gmail.com)
- Add Mageia 7 configs (ngompa13@gmail.com)

* Tue Feb 19 2019 Miroslav Suchý <msuchy@redhat.com> 30.1-1
- default for config['decompress_program'] (praiskup@redhat.com)
- require recent distribution-gpg-keys which has F31 key
- add examples how to enable/install module in F29+ configs
- add module_platform_id
- add modular repos
- enable gpgcheck for debuginfo for rawhide
- enable gpgcheck for testing and debuginfo for F30
- EOL Fedora 27 configs
- remove mdpolicy from F30
- add Fedora 30 configs
- add link to distribution-gpg-keys for rhel8 bootstrap

* Fri Nov 16 2018 Miroslav Suchý <msuchy@redhat.com> 29.4-1
- use correct gpg keys for rhelbeta-8
- add virtual platform module

* Thu Nov 15 2018 Miroslav Suchý <msuchy@redhat.com> 29.3-1
- add rhelbeta-8-* configs
- move EOLed configs to /etc/mock/eol directory
- Add source repos to all fedora configs (sfowler@redhat.com)
- add epel-7-ppc64.cfg

* Thu Aug 16 2018 Miroslav Suchý <msuchy@redhat.com> 29.2-1
- add gpg keys for release rawhide-1 (msuchy@redhat.com)

* Mon Aug 13 2018 Miroslav Suchý <msuchy@redhat.com> 29.1-1
- add fedora 29 configs and change rawhide to F30
- defattr is not needed since rpm 4.2
- Replace armv5tl with aarch64 for Mageia Cauldron (ngompa13@gmail.com)
- check gpg keys for rawhide

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


