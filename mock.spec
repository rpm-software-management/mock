%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

%if 0%{?fedora}
%global use_python3 1
%global use_python2 0
%else
%global use_python3 0
%global use_python2 1
%endif

%if %{use_python3}
%global python_sitelib %{python3_sitelib}
%else
%global python_sitelib %{python_sitelib}
%endif

# mock group id allocate for Fedora
%global mockgid  135

Summary: Builds packages inside chroots
Name: mock
Version: 1.4.0
Release: 0%{?dist}
License: GPLv2+
Source: https://fedorahosted.org/releases/m/o/mock/%{name}-%{version}.tar.gz
URL: https://github.com/rpm-software-management/mock/
BuildArch: noarch
%if 0%{?fedora}
Requires: yum >= 3.4.3-505
%else
Requires: yum >= 2.4
%endif
Requires: tar
Requires: pigz
Requires: usermode
Requires: yum-utils
Requires: createrepo_c
Requires: distribution-gpg-keys >= 1.9
%if 0%{?use_python2}
Requires: pyliblzma
%endif
Requires: systemd
%if 0%{?fedora}
Requires: systemd-container
%endif
Requires(pre): shadow-utils
Requires(post): coreutils
%if 0%{?fedora}
Requires(post): system-release
%endif
%if 0%{?rhel} == 7
Requires(post): /etc/os-release
%endif
BuildRequires: autoconf, automake
BuildRequires: bash-completion
%if %{use_python3}
Requires: python3
Requires: python3-distro
Requires: python3-six >= 1.4.0
Requires: python3-requests
Requires: rpm-python3
BuildRequires: python3-devel
#check
BuildRequires: python3-pylint
%else
Requires: python-ctypes
Requires: python2-distro
Requires: python-six >= 1.4.0
Requires: python-requests
Requires: python >= 2.6
Requires: rpm-python
%endif
BuildRequires: python-devel
%if 0%{?fedora}
Recommends: dnf
Recommends: dnf-plugins-core
Recommends: btrfs-progs
%endif
%if 0%{?rhel} == 7
Requires: btrfs-progs
%endif
BuildRequires: perl

# hwinfo plugin
Requires: util-linux
Requires: coreutils
Requires: procps-ng


%description
Mock takes an SRPM and builds it in a chroot.

%package scm
Summary: Mock SCM integration module
Requires: %{name} = %{version}-%{release}
Requires: cvs
Requires: git
Requires: subversion
Requires: tar

%description scm
Mock SCM integration module.

%package lvm
Summary: LVM plugin for mock
Requires: %{name} = %{version}-%{release}
Requires: lvm2

%description lvm
Mock plugin that enables using LVM as a backend and support creating snapshots
of the buildroot.

%prep
%setup -q
%if %{use_python3}
for file in py/mock.py py/mockchain.py; do
  sed -i 1"s|#!/usr/bin/python |#!/usr/bin/python3 |" $file
done
%endif

%build
for i in py/mock.py py/mockchain.py; do
    perl -p -i -e 's|^__VERSION__\s*=.*|__VERSION__="%{version}"|' $i
    perl -p -i -e 's|^SYSCONFDIR\s*=.*|SYSCONFDIR="%{_sysconfdir}"|' $i
    perl -p -i -e 's|^PYTHONDIR\s*=.*|PYTHONDIR="%{python_sitelib}"|' $i
    perl -p -i -e 's|^PKGPYTHONDIR\s*=.*|PKGPYTHONDIR="%{python_sitelib}/mockbuild"|' $i
done
for i in docs/mockchain.1 docs/mock.1; do
    perl -p -i -e 's|@VERSION@|%{version}"|' $i
done

%install
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_libexecdir}/mock
install py/mockchain.py %{buildroot}%{_bindir}/mockchain
install py/mock.py %{buildroot}%{_libexecdir}/mock/mock
ln -s consolehelper %{buildroot}%{_bindir}/mock

install -d %{buildroot}%{_sysconfdir}/pam.d
cp -a etc/pam/* %{buildroot}%{_sysconfdir}/pam.d/

install -d %{buildroot}%{_sysconfdir}/mock
cp -a etc/mock/* %{buildroot}%{_sysconfdir}/mock/

install -d %{buildroot}%{_sysconfdir}/security/console.apps/
cp -a etc/consolehelper/mock %{buildroot}%{_sysconfdir}/security/console.apps/%{name}

install -d %{buildroot}%{_datadir}/bash-completion/completions/
cp -a etc/bash_completion.d/* %{buildroot}%{_datadir}/bash-completion/completions/
ln -s mock %{buildroot}%{_datadir}/bash-completion/completions/mockchain

install -d %{buildroot}%{_sysconfdir}/pki/mock
cp -a etc/pki/* %{buildroot}%{_sysconfdir}/pki/mock/

install -d %{buildroot}%{python_sitelib}/
cp -a py/mockbuild %{buildroot}%{python_sitelib}/

install -d %{buildroot}%{_mandir}/man1
cp -a docs/mockchain.1 docs/mock.1 %{buildroot}%{_mandir}/man1/

install -d %{buildroot}/var/lib/mock
install -d %{buildroot}/var/cache/mock

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
# fix cache permissions from old installs
chmod 2775 %{_localstatedir}/cache/%{name}

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
mock_arch=$(python -c "import rpmUtils.arch; baseArch = rpmUtils.arch.getBaseArch(); print baseArch")
cfg=%{?fedora:fedora}%{?rhel:epel}-$ver-${mock_arch}.cfg
if [ -e %{_sysconfdir}/%{name}/$cfg ]; then
    if [ "$(readlink %{_sysconfdir}/%{name}/default.cfg)" != "$cfg" ]; then
        ln -s $cfg %{_sysconfdir}/%{name}/default.cfg 2>/dev/null || ln -s -f $cfg %{_sysconfdir}/%{name}/default.cfg.rpmnew
    fi
else
    echo "Warning: file %{_sysconfdir}/%{name}/$cfg does not exists."
    echo "         unable to update %{_sysconfdir}/%{name}/default.cfg"
fi
:

%check
# ignore the errors for now, just print them and hopefully somebody will fix it one day
python3-pylint py/mockbuild/ py/*.py py/mockbuild/plugins/* || :

%files -f %{name}.cfgs
%defattr(-, root, root)

# executables
%{_bindir}/mock
%{_bindir}/mockchain
%{_libexecdir}/mock

# python stuff
%{python_sitelib}/*
%exclude %{python_sitelib}/mockbuild/scm.*
%exclude %{python_sitelib}/mockbuild/plugins/lvm_root.*

# config files
%dir  %{_sysconfdir}/%{name}
%ghost %config(noreplace,missingok) %{_sysconfdir}/%{name}/default.cfg
%config(noreplace) %{_sysconfdir}/%{name}/*.ini
%config(noreplace) %{_sysconfdir}/pam.d/%{name}
%config(noreplace) %{_sysconfdir}/security/console.apps/%{name}

# gpg keys
%dir %{_sysconfdir}/pki/mock
%config(noreplace) %{_sysconfdir}/pki/mock/*

# docs
%{_mandir}/man1/mock.1*
%{_mandir}/man1/mockchain.1*

# cache & build dirs
%defattr(0775, root, mock, 02775)
%dir %{_localstatedir}/cache/mock
%dir %{_localstatedir}/lib/mock

%files scm
%{python_sitelib}/mockbuild/scm.py*
%if %{use_python3}
%{python3_sitelib}/mockbuild/__pycache__/scm.*.py*
%endif

%files lvm
%{python_sitelib}/mockbuild/plugins/lvm_root.*
%if %{use_python3}
%{python3_sitelib}/mockbuild/plugins/__pycache__/lvm_root.*.py*
%endif

%changelog
* Mon Feb 27 2017 Miroslav Suchý <msuchy@redhat.com> 1.3.4-1
- add support for dist-git to scm plugin (clime@redhat.com)
- preserve mode of files when doing chroot_scan [RHBZ#1297430]
  (msuchy@redhat.com)
- spec: add to package pycache for subpackages (msuchy@redhat.com)
- restore permissions on chroot_scan dir (drop to unprivUid, unprivGid)
  (gitDeveloper@bitthinker.com)
- add fedora 26 configs (msuchy@redhat.com)
- config: add best=1 also into rawhide configs (praiskup@redhat.com)
- rename package_state's log to have .log suffix (gitDeveloper@bitthinker.com)
- systemd-nspawn: run as PID2 #36 (msuchy@redhat.com)
- fix defaults for yum_builddep_opts (gitDeveloper@bitthinker.com)
- Support nspawn_args (walters@verbum.org)
- return exit code 2 when /usr/libexec/mock/mock run directly without
  consolehelper (msuchy@redhat.com)
- change path of /usr/sbin/mock in error message (msuchy@redhat.com)
- Fix debuginfo repo naming (msimacek@redhat.com)
- more examples of PS1 [RHBZ#1183733] (msuchy@redhat.com)
- simplify PROMPT_COMMAND string (msuchy@redhat.com)
- "Rawhide" has been changed to "rawhide" in os-release file in current rawhide
  (F26) [RHBZ#1409735] (msuchy@redhat.com)
- Update local repo URLs for rawhide (mizdebsk@redhat.com)
- Switch kojipkgs URLs to https (mizdebsk@redhat.com)
- run pylint on plugins too (msuchy@redhat.com)
- introduce hw_info plugin (msuchy@redhat.com)
- remove fedora-23 configs (msuchy@redhat.com)

* Sun Jan 01 2017 Miroslav Suchý <msuchy@redhat.com> 1.3.3-1
- use F25 for tests
- handle cwd directories with spaces [RHBZ#1389663]
- add config option `hostname` to set hostname
  (constantine.peresypk@rackspace.com)
- use DNF on RHEL, when it is installed and configured [RHBZ#1405783]
- use best=1 for DNF
- error is not iterable [RHBZ#1387895]
- use best=true for dnf.conf for repos passed to mockchain using -a
- add epel-7-aarch64 config
- better naming for tmp directories
- Remove tmpdirs regardless of buildroot existence (msimacek@redhat.com)
- clarify examples of using more_buildreqs feature
  (gitDeveloper@bitthinker.com)
- fix more_buildreqs case: correctly compare if req is basestring
  (gitDeveloper@bitthinker.com)
- fix formating a bit (gitDeveloper@bitthinker.com)
- add missing step in 'getting & compiling' part (gitDeveloper@bitthinker.com)
- Add bash completion for .cfg files outside /etc/mock (#20)
  (github@kayari.org)
- man: example how to use --plugin-option
- require most recent distribution-gpg-keys to get F25 keys
- man: state that shell does not produce logs
- Delay mounting of user-defined mountpoints (rhbz#1386544)
  (msimacek@redhat.com)
- man: clarify chroot cleanups

* Mon Oct 17 2016 Miroslav Suchý 1.3.2-1
- flake8 fixes
- correctly escape --nocheck [GH#2] (msuchy@redhat.com)
- change hostname in container [RHBZ#1302040] (msuchy@redhat.com)
- example how to change hostname in container [RHBZ#1302040]
  (msuchy@redhat.com)
- skip unshare() if running inside of Docker [RHBZ#1336750] (msuchy@redhat.com)
- Bring back logging.raiseExceptions = 0 (ville.skytta@iki.fi)
- Purge no longer needed Python < 2.5 workarounds (ville.skytta@iki.fi)
- Purge no longer needed six < 1.4.0 workaround (ville.skytta@iki.fi)
- run pylint during %%check phase (msuchy@redhat.com)

* Tue Sep 27 2016 Miroslav Suchý <msuchy@redhat.com> 1.3.1-1
- remove F21 GPG keys
- remove F22 configs
- update upstream URL
- move /usr/sbin/mock to /usr/libexec/mock/mock [RHBZ#1246810]
- Initialized to use tito.
- add pylint config
* Tue Sep 13 2016 Miroslav Suchý <msuchy@redhat.com> - 1.2.21-1
- CVE-2016-6299 - fixed root rights escalation in mock-scm
- root_cache: Mention _root_ cache being created in state updates
- Rename mageia pubkey to RPM-GPG-KEY-Mageia
- require generic system-release rather than fedora-release [RHBZ#1367746]

* Wed Aug 17 2016 Miroslav Suchý <msuchy@redhat.com> - 1.2.20-1
- use epel GPG keys for epel

* Wed Aug 10 2016 Miroslav Suchý <msuchy@redhat.com> - 1.2.19-1
- disable tmpfs plugin for init-clean test
- pass cwd option to systemd-nspawn [RHBZ#1264508]
- pass unpriv id to doshell() [RHBZ#1298220]
- enable package_state plugin by default and create installed_pkgs file [RHBZ#1277187]
- installed_pkgs can be created even in offline mode
- Use context manager for drop/restore calls of uid manager [RHBZ#1362478]
- require /etc/os-release during post section [RHBZ#1358397]
- use mageia gpg keys from distribution-gpg-keys package
- use fedora gpg keys from distribution-gpg-keys package
- use epel gpg keys from distribution-gpg-keys package
- add F25 configs
- 'include' statement has been added [RHBZ#1272381]
- Handle file open/close more with "with", close more eagerly
- Use logging.warning instead of deprecated warn
- add chroot_additional_packages to custom chroots
- chroot_additional_packages: new option

* Fri Jun 10 2016 Miroslav Suchý <msuchy@redhat.com> - 1.2.18-1
- add custom config
- add Mageia configs
- copy just content of SRPM not the attributes [RHBZ#1301985]
- do not fail when we cannot link default.cfg [RHBZ#1305367]
- Build always fails when using --nocheck [RHBZ#1327594]
- Escape the escape sequences in PROMPT_COMMAND, improve prompt
- requires rpm-python
- Use root name instead config name for backups dir
- Unconditionally setup resolver config
- keep machine-id in /etc/machine-id [RHBZ#1344305]
- use DNF for F24
- Add MIPS personalities
- scm plugin: fix handling of submodules

* Fri Mar 11 2016 Miroslav Suchý <msuchy@redhat.com> - 1.2.17-1
- call rpmbuild correctly

* Tue Mar  8 2016 Miroslav Suchý <msuchy@redhat.com> - 1.2.16-1
- remove old %if statements
- systemd-nspawn is now in systemd-container package
- become root user correct way [RHBZ#1312820][RHBZ#1311796]
- remove the sparc config
- Let logging format messages on demand
- tell nspawn which variables it should set [RHBZ#1311796]
- do not call /bin/su and rather utilize --user of systemd-nspawn [RHBZ#1301953]

* Mon Feb 22 2016 Miroslav Suchý <msuchy@redhat.com> - 1.2.15-1
- ccache plugin disabled by default
- F21 configs removed
- F24 configs added
- typo fixed [RHBZ#1285630]
- read user config from ~/.config/mock.cfg too
- disable "local" dnf plugin [RHBZ#1264215]
- when removing buildroot, do that as root [RHBZ#1294979]

* Fri Nov 20 2015 Miroslav Suchý <msuchy@redhat.com> - 1.2.14-1
- after unpacking chroot, change back to $CWD [RHBZ#1281369]
- Fix package manager version handling for CentOS
- use --setopt=deltarpm=false as default value for dnf_common_opts [RHBZ#1281355]
- add arguments, do not over ride previous ones
- Add %%(resultdir) placeholder for sign plugin. [RHBZ#1272123]
- decode shell output when running under Python3 [RHBZ#1267161]
- create tmpfs with unlimited inodes [RHBZ#1266453]
- typo [RHBZ#1241827]
- do not use machinectl --no-legend as it is not el7 compatible [RHBZ#1241827]
- directly tell yum which yum.conf he should use [RHBZ#1264462]

* Wed Sep 16 2015 Miroslav Suchý <msuchy@redhat.com> - 1.2.13-1
- Use 'machinectl terminate' inside orphanskill() when systemd-nspawn used [RHBZ#1171737]
- use quite systemd-nspawn in quite mode [RHBZ#1262889]
- when calling systemd-nspawn become root first [RHBZ#1241827]
- revert F23 configs back to yum
- Give user hint what to do if he miss scm plugin.
- when cleaning up /dev/ do not fail on mountpoins
- warn (but not fail) on RHELs when you try to use DNF
- migrate package_state to use dnf when package_manager is set to dnf
- redownload metadata if they changed on server [RHBZ#1230508]
- provide --scrub=dnf-cache as alias for yum-cache [RHBZ#1241296]
- copy files to correct location [RHBZ#1252088]
- do not install weak deps in chroot [RHBZ#1254634]
- Try to set PTY window size [RHBZ#1155199]
- Set default LVM pool name [RHBZ#1163008]
- better parsing of content-disposition header [RHBZ#1248344]
- backend: Ensure output files are owned by unpriv user with nspawn
- Add "rpmbuild_networking" key (False by default) for nspawn backend
- fdfd464 Update Fedora Wiki URLs
- use yum-deprecated as the yum_command if it exists

* Tue Jul 14 2015 clark Williams <williams@redhat.com> - 1.2.12-1
- from Dennis Gilmore <dennis@ausil.us>:
  - setup support so loopback devices can work [RHBZ#1245401]
- from Miroslav Suchý <msuchy@redhat.com>:
  - clarify path [RHBZ#1228751]
  - document target_arch and legal_host_arches in site-defaults.cfg [RHBZ#1228751]
  - document "yum.conf" in site-defaults.cfg [RHBZ#1228751]
  - correctly specify requires of yum [RHBZ#1244475]
  - bump up releasever in rawhide targets
  - remove EOLed gpg keys
  - add f23 configs
  - removing EOLed f19 and f20 configs

* Tue Jul 14 2015 clark Williams <williams@redhat.com> - 1.2.11-1
- dropped code that does stray mount cleanup of chroot [RHBZ#1208092]
- modified package_manager resolvedep cmd to use repoquery when dnf is installed
