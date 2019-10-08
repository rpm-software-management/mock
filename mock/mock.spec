%bcond_with tests

%if 0%{?fedora} || 0%{?mageia} || 0%{?rhel} >= 7
%global use_python3 1
%global use_python2 0
%global __python %{__python3}
%global python_sitelib %{python3_sitelib}
%else
%global use_python3 0
%global use_python2 1
%global __python %{__python2}
%global python_sitelib %{python2_sitelib}
%endif

Summary: Builds packages inside chroots
Name: mock
Version: 1.4.20
Release: 1%{?dist}
License: GPLv2+
# Source is created by
# git clone https://github.com/rpm-software-management/mock.git
# cd mock
# git reset --hard %%{name}-%%{version}
# tito build --tgz
Source: %{name}-%{version}.tar.gz
URL: https://github.com/rpm-software-management/mock/
BuildArch: noarch
Requires: tar
Requires: pigz
%if 0%{?mageia}
Requires: usermode-consoleonly
%else
Requires: usermode
%endif
Requires: createrepo_c
Requires: mock-core-configs >= 27.4
%if 0%{?use_python2}
Requires: pyliblzma
%endif
Requires: systemd
%if 0%{?fedora} || 0%{?rhel} >= 8
Requires: systemd-container
%endif
Requires: coreutils
%if 0%{?fedora}
Suggests: iproute
%endif
%if 0%{?mageia}
Suggests: iproute2
%endif
BuildRequires: bash-completion
%if %{use_python3}
Requires: python%{python3_pkgversion}-distro
Requires: python%{python3_pkgversion}-jinja2
Requires: python%{python3_pkgversion}-six >= 1.4.0
Requires: python%{python3_pkgversion}-requests
Requires: python%{python3_pkgversion}-rpm
Requires: python%{python3_pkgversion}-pyroute2
BuildRequires: python%{python3_pkgversion}-devel
%if %{with tests}
BuildRequires: python%{python3_pkgversion}-pylint
%endif
%else
Requires: python-ctypes
Requires: python2-distro
Requires: python-jinja2
Requires: python-six >= 1.4.0
Requires: python-requests
Requires: python2-pyroute2
Requires: python >= 2.7
Requires: rpm-python
BuildRequires: python2-devel
%endif
%if 0%{?fedora} || 0%{?mageia} || 0%{?rhel} >= 8
Requires: dnf
Suggests: yum
Requires: dnf-plugins-core
Recommends: btrfs-progs
Recommends: dnf-utils
Suggests: qemu-user-static
Suggests: procenv
Suggests: podman
%else
%if 0%{?rhel} == 7
Requires: btrfs-progs
Requires: yum >= 2.4
Requires: yum-utils
%endif
%endif

%if 0%{?fedora} || 0%{?rhel} >= 8
BuildRequires: perl-interpreter
%else
BuildRequires: perl
%endif
# hwinfo plugin
Requires: util-linux
Requires: coreutils
Requires: procps-ng


%description
Mock takes an SRPM and builds it in a chroot.

%package scm
Summary: Mock SCM integration module
Requires: %{name} = %{version}-%{release}
%if 0%{?rhel} && 0%{?rhel} < 8
Requires: cvs
Requires: git
Requires: subversion
Requires: tar
%else
Recommends: cvs
Recommends: git
Recommends: subversion
Recommends: tar
%endif

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
for file in py/mock.py py/mock-parse-buildlog.py; do
  sed -i 1"s|#!/usr/bin/python3 |#!%{__python} |" $file
done

%build
for i in py/mock.py py/mock-parse-buildlog.py; do
    perl -p -i -e 's|^__VERSION__\s*=.*|__VERSION__="%{version}"|' $i
    perl -p -i -e 's|^SYSCONFDIR\s*=.*|SYSCONFDIR="%{_sysconfdir}"|' $i
    perl -p -i -e 's|^PYTHONDIR\s*=.*|PYTHONDIR="%{python_sitelib}"|' $i
    perl -p -i -e 's|^PKGPYTHONDIR\s*=.*|PKGPYTHONDIR="%{python_sitelib}/mockbuild"|' $i
done
for i in docs/mock.1 docs/mock-parse-buildlog.1; do
    perl -p -i -e 's|\@VERSION\@|%{version}"|' $i
done

%install
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_libexecdir}/mock
install mockchain %{buildroot}%{_bindir}/mockchain
install py/mock-parse-buildlog.py %{buildroot}%{_bindir}/mock-parse-buildlog
install py/mock.py %{buildroot}%{_libexecdir}/mock/mock
ln -s consolehelper %{buildroot}%{_bindir}/mock
install create_default_route_in_container.sh %{buildroot}%{_libexecdir}/mock/
 
install -d %{buildroot}%{_sysconfdir}/pam.d
cp -a etc/pam/* %{buildroot}%{_sysconfdir}/pam.d/

install -d %{buildroot}%{_sysconfdir}/mock
cp -a etc/mock/* %{buildroot}%{_sysconfdir}/mock/

install -d %{buildroot}%{_sysconfdir}/security/console.apps/
cp -a etc/consolehelper/mock %{buildroot}%{_sysconfdir}/security/console.apps/%{name}

install -d %{buildroot}%{_datadir}/bash-completion/completions/
cp -a etc/bash_completion.d/* %{buildroot}%{_datadir}/bash-completion/completions/
ln -s mock %{buildroot}%{_datadir}/bash-completion/completions/mock-parse-buildlog

install -d %{buildroot}%{_sysconfdir}/pki/mock
cp -a etc/pki/* %{buildroot}%{_sysconfdir}/pki/mock/

install -d %{buildroot}%{python_sitelib}/
cp -a py/mockbuild %{buildroot}%{python_sitelib}/

install -d %{buildroot}%{_mandir}/man1
cp -a docs/mock.1 docs/mock-parse-buildlog.1 %{buildroot}%{_mandir}/man1/
install -d %{buildroot}%{_datadir}/cheat
cp -a docs/mock.cheat %{buildroot}%{_datadir}/cheat/mock

install -d %{buildroot}/var/lib/mock
install -d %{buildroot}/var/cache/mock

%check
%if %{with tests}
# ignore the errors for now, just print them and hopefully somebody will fix it one day
pylint-3 py/mockbuild/ py/*.py py/mockbuild/plugins/* || :
%endif

%files
%defattr(0644, root, mock)
%config(noreplace) %{_sysconfdir}/mock/site-defaults.cfg
%{_datadir}/bash-completion/completions/mock
%{_datadir}/bash-completion/completions/mock-parse-buildlog

%defattr(-, root, root)

# executables
%{_bindir}/mock
%{_bindir}/mockchain
%{_bindir}/mock-parse-buildlog
%{_libexecdir}/mock

# python stuff
%{python_sitelib}/*
%exclude %{python_sitelib}/mockbuild/scm.*
%exclude %{python_sitelib}/mockbuild/plugins/lvm_root.*

# config files
%config(noreplace) %{_sysconfdir}/%{name}/*.ini
%config(noreplace) %{_sysconfdir}/pam.d/%{name}
%config(noreplace) %{_sysconfdir}/security/console.apps/%{name}

# directory for personal gpg keys
%dir %{_sysconfdir}/pki/mock
%config(noreplace) %{_sysconfdir}/pki/mock/*

# docs
%{_mandir}/man1/mock.1*
%{_mandir}/man1/mock-parse-buildlog.1*
%{_datadir}/cheat/mock

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
* Fri Oct 04 2019 Miroslav Suchý <msuchy@redhat.com> 1.4.20-1
- /bin/mockchain wrapper around 'mock --chain' (praiskup@redhat.com)
- mock: options for retrying packager managers' actions (praiskup@redhat.com)
- remove mockchain [RHBZ#1757388]
- chain: don't skip local repository (praiskup@redhat.com)
- chain: propagate local repository to bootstrap chroot (praiskup@redhat.com)
- hw_info: don't create root-owned files (praiskup@redhat.com)
- ignore ./var/log when creating root_cache - fixes #309
  (jiri.novak@ghorland.net)
- mock: don't create root files if possible (praiskup@redhat.com)
- add commandline options for using bootstrap image (frostyx@email.cz)
- Use podman to pull and export an image as a bootstrap chroot
  (dmach@redhat.com)

* Tue Sep 10 2019 Miroslav Suchý <msuchy@redhat.com> 1.4.19-1
- results should be owned by unpriv user [GH#322]
- do not build with tests by default
- Resultdir variable is missing in config. (sisi.chlupova@gmail.com)

* Tue Aug 27 2019 Miroslav Suchý <msuchy@redhat.com> 1.4.18-1
- use forcearch even when --forcearch is not specified
  (turecek.dominik@gmail.com)
- requires systemd-container on rhel8 [RHBZ#1744538]
- mock: only make /sys and /proc mounts rprivate (praiskup@redhat.com)
- Add Red Hat subscription-manager support (praiskup@redhat.com)
- Turn jinja ON a bit later, once configs are loaded (praiskup@redhat.com)
- bootstrap-chroot: always explicitly install shadow-utils
  (praiskup@redhat.com)
- Add procenv plugin for more detailed buildtime information
  (riehecky@fnal.gov)
- enable selinux plugin for nspawn [RHBZ#1740421]
- Added signals handling by calling orphansKill for signals: SIGTERM, SIGPIPE
  and SIGHUP (janbuchmaier@seznam.cz)
- Mention user configuration file in a man page (jkonecny@redhat.com)

* Thu Aug 08 2019 Miroslav Suchý <msuchy@redhat.com> 1.4.17-1
- change of exit code during transition from mockchain to mock --chain
- support run in Fedora Toolbox (otaylor@fishsoup.net)
- add cheat sheet
- Adding tool for parsing build.log (sisi.chlupova@gmail.com)
- load secondary groups [RHBZ#1264005]
- pass --allowerasing by default to DNF [GH#251]
- make include() functional for --chain [GH#263]
- Removing buildstderr from log - configurable via 
  _mock_stderr_line_prefix (sisi.chlupova@gmail.com)
- Fixup: Use rpm -qa --root instead of running rpm -qa in chroot
  (miro@hroncok.cz)
- DynamicBuildrequires: Detect when no new packages were installed
  (miro@hroncok.cz)
- Allow more loop devices (sisi.chlupova@gmail.com)
- Fix binary locations in /bin for split-usr setups (bero@lindev.ch)
- describe behaviour of resultdir together with --chain [GH#267]
- repeat dynamic requires if needed [GH#276]
- Fix compatibility with pre-4.15 RPM versions with DynamicBuildRequires
  (i.gnatenko.brain@gmail.com)
- Enable dynamic BuildRequires by default (i.gnatenko.brain@gmail.com)
- bootstrap: independent network configuration (praiskup@redhat.com)
- Update the man page about ~/.config/mock/FOO.cfg (miro@hroncok.cz)
- explicitely convert releasever to string [GH#270]
- grant anyone access to bind-mounted /etc/resolv.conf (praiskup@redhat.com)
- -r FOO will try to read first ~/.mock/FOO.cfg if exists
- enhance man page of mock about --chain
- bash completion for --chain
- respect use_host_resolv config even with use_nspawn (praiskup@redhat.com)
- Fix crash on non-ascii dnf log messages (bkorren@redhat.com)
- add deprecation warning to mockchain
- replace mockchain with `mock --chain` command (necas.marty@gmail.com)
- switch to python3 on el7 (msuchy@redhat.com)

* Wed May 22 2019 Miroslav Suchý <msuchy@redhat.com> 1.4.16-1
- switch to python3 on el7
- respect use_host_resolv config even with use_nspawn (praiskup@redhat.com)
- Fix crash on non-ascii dnf log messages (bkorren@redhat.com)

* Mon Apr 22 2019 Miroslav Suchý <msuchy@redhat.com> 1.4.15-1
- ignore weird distro.version() [RHBZ#1690374]
- switch to string rpm's API [RHBZ#1693759]
- FileNotFoundError is not defined in Python 2 [RHBZ#1696234]
- Fix python2-devel build require
- temporary do not make errors from createrepo_c fatal [GH#249]
- allow to configure disabled DNF plugins [GH#210]
- print warning when user is not in the mock group [GH#244]
- implement Dynamic Build Dependencies (msuchy@redhat.com)
- Allow mock to be built for epel 8, and without tests
  (vanmeeuwen@kolabsys.com)
- Add debug logging for systemd-nspawn and related args (riehecky@fnal.gov)
- Fix mock for non-ascii paths on python2 (a.badger@gmail.com)
- require python-jinja2 rather than python2-jinja2
- Fix --enable-network documentation in man page (directhex@apebox.org)

* Tue Feb 19 2019 Miroslav Suchý <msuchy@redhat.com> 1.4.14-1
- config['decompress_program'] default (praiskup@redhat.com)
- add example for jinja templates
- implement templated configs using jinja2
- move live defaults from site-defaults.cfg to utils.py
- introduce "decompress_program" option for root_cache for bsdtar
- fix exclude patter for bsdtar
- delete old changelog entries
- use f29 for tests
- update the default in sitec-defaults.cfg
- Recommend dnf-utils (fzatlouk@redhat.com)
- ignore useless-object-inheritance pylint warning
- add scientific linux on list of rhel clones [GH#228]
- Use 32-bit personality for armv7*/armv8* builds (bero@lindev.ch)
- create custom error message for dnf-utils not being installed
  (pjunak)

* Mon Aug 13 2018 Miroslav Suchý <msuchy@redhat.com> 1.4.13-1
- fix python_sitelib macro

* Mon Aug 13 2018 Miroslav Suchý <msuchy@redhat.com> 1.4.12-1
- Don't try to use a spec we've already cleaned up (otaylor@fishsoup.net)
- only set print_main_output when not set in configs
  (chuck.wilson+github@gmail.com)
- Try to get the proxy from environment (brunovern.a@gmail.com)
- stop after first failure if -c or --recurse is not used
- fallback to C.UTF-8 locale (tomek@pipebreaker.pl)
- completion: improve --copy(in|out), --cwd, --macro-file, --rootdir, and
  --sources (tmz@pobox.com)
- do not get spec from command line when using scm [GH#203]
- enable cap_ipc_lock in nspawn container [RHBZ#1580435]
- use host's resolv.conf when --enable-network is set on cml [RHBZ#1593212]
  (jskarvad@redhat.com)
- add --forcearch to bash_completion

* Tue Jun 12 2018 Miroslav Suchý <msuchy@redhat.com> 1.4.11-1
- fix @VERSION@ processing in man pages (ktdreyer@ktdreyer.com)
- update testing.src.rpm to recent standard
- Allow --spec arg to be used with rebuild option (sfowler@redhat.com)
- Disable use_host_resolv by default (tmz@pobox.com)
- Add support for microdnf [GH#76] (zdenekirsax@gmail.com)
- skip running groupadd if gid is 0 (nhorman@tuxdriver.com)
- Allow overriding of mock chroot build user name (nhorman@tuxdriver.com)
- do not populate /etc/resolv.conf when networking is disabled (RHBZ#1514028)
  (tmz@pobox.com)
- add version to EL check in _prepare_nspawn_command() (tmz@pobox.com)
- pass force-arch to builddep and resolvedep [GH#120]
- Support setting up foreign architecture chroots
- add support for bsdtar
- use fedora 28 for tests

* Thu May 10 2018 Miroslav Suchý <msuchy@redhat.com> 1.4.10-1
- remove executable bit from trace_decorator.py
- Change sign plugint to sign only builded rpm and not every file in results
  [RHBZ#1217495] (necas.marty@gmail.com)
- overlayfs plugin: added explicit mount support (zzambers@redhat.com)
- encode content before writing [RHBZ#1564035]
- allow to bind_mount just one file (necas.marty@gmail.com)
- added overlayfs plugin (zzambers@redhat.com)
- invoke chroot scan for 'initfailed' event (clime7@gmail.com)
- add support for .spec in --installdeps (necas.marty@gmail.com)
- revert workaround introduced in 057c51d6 [RHBZ#1544801]
- comment out macro in changelog (msuchy@redhat.com)

* Mon Feb 12 2018 Miroslav Suchý <msuchy@redhat.com> 1.4.9-1
- "setup_cmd" of bootstrap container is the actuall $pm_install_command from
  the main container [RHBZ#1540813]
- do not produce warning when we are using different PM for bootstrap container
- Honor the "cwd" flag when nspawn is being used and "chrootPath" is not set
  (matthew.prahl@outlook.com)
- do not run ccache in bootstrap chroot [RHBZ#1540813]
- use DNF on EL7 when bootstrap is used [RHBZ#1540813]
- site-defaults: fix quoting in sign_opts example [RHBZ#1537797]
  (tmz@pobox.com)
- Detect if essential mounts are already mounted (msimacek@redhat.com)
- Update Python 2 dependency declarations to new packaging standards
- improvement code/docs for opstimeout (Mikhail_Campos-Guadamuz@epam.com)
- simplifying of utils.do() (Mikhail_Campos-Guadamuz@epam.com)
- New config option 'opstimeout' has been added. (Mikhail_Campos-
  Guadamuz@epam.com)
- Don't setup user mounts in the bootstrap buildroot (bkorren@redhat.com)
- el5 is sensitive to order of params
- Default for config_opts['dnf_warning'] according to docs
  (praiskup@redhat.com)
- Avoid manual interpolation in logging of BUILDSTDERR (Mikhail_Campos-
  Guadamuz@epam.com)
- Splitting stdout and stderr in build.log. All stderr output lines are
  prefixed by 'BUILDSTDERR:' (Mikhail_Campos-Guadamuz@epam.com)

* Fri Dec 22 2017 Miroslav Suchý <msuchy@redhat.com> 1.4.8-1
- orphanskill: send SIGKILL when SIGTERM is not enough [RHBZ#1495214]
- pass --non-unique to usermod because of old targets
- remove _selinuxYumIsSetoptSupported()
- only use -R if first umount failed
- use recursive unmount for tmpfs
- do not cd to dir if nspawn is used [GH#108]
- add new option --config-opts [GH#138]
- add --enable-network to bash_completation
- Strip trailing / from mountpath in ismounted()
- new cli option --enable-network [RHBZ#1513953]
- when creating yum/dnf.conf copy timestamp from host [RHBZ#1293910]
- do not populate /etc/resolv.conf when networking is disabled [RHBZ#1514028]
- soften mock-scm dependencies [RHBZ#1515989]
- mount /proc and /sys before executing any PM command [RHBZ#1467299]

* Tue Oct 31 2017 Miroslav Suchý <msuchy@redhat.com> 1.4.7-1
- user and group is actually not used here since some logic moved to buildroot.py
- add config_opts['chrootgroup'] to site-defaults.cfg
- Enable chrootgroup as a config file option
- override some keys for bootstrap config
- Add support for DeskOS
- Delete rootdir as well when calling clean
- Fix mock & mock-core-config specs to support Mageia
- Ensure mock-core-configs will select the right default on Mageia
- ccache: use different bind mount directory
- new-chroot: set up new network namespace and add default route in it
- use primary key for F-27+ on s390x
- man: add dnf to see also
- man: escape @
- remove Seth email
- more grammar fixes
- fix typo in mock(1)
- sort debug-config output

* Fri Sep 15 2017 Miroslav Suchý <msuchy@redhat.com> 1.4.6-1
- requires mock-core-configs

* Fri Sep 15 2017 Miroslav Suchý <msuchy@redhat.com> 1.4.5-1
- introduce -N for --no-cleanup-after (jsynacek@redhat.com)
- add man page entry for --debug-config
- Added option --debug-config (matejkudera1@seznam.cz)
- site-defaults: Fix comment about nspawn/chroot default (ville.skytta@iki.fi)
- move chroot configs to mock-core-configs directory
- pass --private-network to every container spawning if specified
- add script to create default route in container to localhost
- [site-defaults] Fix umount_root documentation
- Fix keeping the LVM volume mounted
- suggest dnf-utils
- Always create /dev/loop nodes
