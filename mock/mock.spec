%bcond_without tests

%if 0%{?fedora} || 0%{?mageia} || 0%{?rhel} >= 8
%global use_python3 1
%global use_python2 0
%else
%global use_python3 0
%global use_python2 1
%endif

%if %{use_python3}
%global python_sitelib %{python3_sitelib}
%else
%global python_sitelib %{python2_sitelib}
%endif

Summary: Builds packages inside chroots
Name: mock
Version: 1.4.15
Release: 1%{?dist}
License: GPLv2+
# Source is created by
# git clone https://github.com/rpm-software-management/mock.git
# cd mock
# git reset --hard %{name}-%{version}
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
%if 0%{?fedora}
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
Requires: python3
Requires: python3-distro
Requires: python3-jinja2
Requires: python3-six >= 1.4.0
Requires: python3-requests
Requires: python3-rpm
Requires: python3-pyroute2
BuildRequires: python3-devel
%if %{with tests}
BuildRequires: python3-pylint
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
%if %{use_python2}
for file in py/mock.py py/mockchain.py; do
  sed -i 1"s|#!/usr/bin/python3 |#!/usr/bin/python |" $file
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
    perl -p -i -e 's|\@VERSION\@|%{version}"|' $i
done

%install
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_libexecdir}/mock
install py/mockchain.py %{buildroot}%{_bindir}/mockchain
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
ln -s mock %{buildroot}%{_datadir}/bash-completion/completions/mockchain

install -d %{buildroot}%{_sysconfdir}/pki/mock
cp -a etc/pki/* %{buildroot}%{_sysconfdir}/pki/mock/

install -d %{buildroot}%{python_sitelib}/
cp -a py/mockbuild %{buildroot}%{python_sitelib}/

install -d %{buildroot}%{_mandir}/man1
cp -a docs/mockchain.1 docs/mock.1 %{buildroot}%{_mandir}/man1/

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
%{_datadir}/bash-completion/completions/mockchain

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
%config(noreplace) %{_sysconfdir}/%{name}/*.ini
%config(noreplace) %{_sysconfdir}/pam.d/%{name}
%config(noreplace) %{_sysconfdir}/security/console.apps/%{name}

# directory for personal gpg keys
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

* Tue Aug 22 2017 Miroslav Suchý <msuchy@redhat.com> 1.4.4-1
- Rename group inside of chroot from mockbuild to mock
- add F27 configs
- populate /etc/dnf/dnf.conf even when using yum PM
- create /etc/dnf directory
- correct path is /etc/dnf/dnf.conf instead of /etc/dnf.conf
- perl dependency renamed to perl-interpreter
  <https://fedoraproject.org/wiki/Changes/perl_Package_to_Install_Core_Modules>

* Mon Aug 07 2017 Miroslav Suchý <msuchy@redhat.com> 1.4.3-1
- selinux: do not try to import yum when PM is dnf [RHBZ#1474513]
- create /dev nodes even when using nspawn [RHBZ#1467299]
- scm: define _sourcedir to checkout directory
  (ignatenkobrain@fedoraproject.org)
- mageia-cauldron: Change releasever to 7 (ngompa13@gmail.com)
- enhance detection of RHEL [RHBZ#1470189]
- Add detection of OL (Oracle Linux) distribution
  (pixdrift@users.noreply.github.com)
- Make LVM sleep time configurable (mizdebsk@redhat.com)
- on fedoras use python3 to detect correct arch in %%post [RHBZ#1462310]
- backend.py: quote check_opt (jlebon@redhat.com)
- Grammar fixes (ville.skytta@iki.fi)
- Docstring spelling fix (ville.skytta@iki.fi)
- Document python >= 2.7 requirement (ville.skytta@iki.fi)
- Remove obsolete internal_setarch config option (ville.skytta@iki.fi)

* Sat Jun 10 2017 Miroslav Suchý <msuchy@redhat.com> 1.4.2-1
- define PermissionError for python2
- make /etc/yum.conf symlink to /etc/yum/yum.conf
- Do not use systemd-nspawn for EL6 chroots [RHBZ#1456421]
- umount all internal mounts before umounting lvm
- umountall try to umount several times in case there are deps between mounts
- unify behaviour of umount
- display which state start/stop, if normal or bootstrap
- do not umount LVM volumes if umount_root is set to true [RHBZ#1447658]
- use LC_ALL=C.UTF-8 rather than plain C
- add modularity options to custom chroots config
- initial support for modularity
- add boostrap options to bash completation
- set --no-bootstrap-chroot as default for now
- Use bash --login with systemd-nspawn as well (rhbz #1450516)
  (orion@cora.nwra.com)
- docs: add note for subscription-manager.conf (#55)
  (gitDeveloper@bitthinker.com)
- Pass canonical spelling False, not false to mock's setopt=deltarpm
  (ville.skytta@iki.fi)
- make it easier to detect if buildroot is bootstrap or not
- document other lvm options in site-defaults.cfg
- do not call yum-deprecated from bootstrap chroot [RHBZ#1446294]
- do not use bootstrap for custom chroots [RHBZ#1448321]
- hard require dnf-plugins-core on Fedora
- we do not BuildRequire autoconf and automake any more
- do not require yum and yum-utils in Fedora
- Fix calls of yum-builddep and repoquery, and use 'dnf repoquery' for dnf
  (ngompa13@gmail.com)
- call plugins of bootstrap when it has sense
- call scrub hook for bootstrap chroot too [RHBZ#1446297]

* Wed Apr 26 2017 Miroslav Suchý <msuchy@redhat.com> 1.4.1-1
- remove leading space [RHBZ#1442005]
- copy nosync libraries to /var/tmp
- use tmpdir same as in in bootstrap chroot (Issue#59)
- do not ship distribution gpg keys
- pylint has been renamed
- Fix "init_install_output" error (marc.c.dionne@gmail.com)
- Epel5 has been EOLed (Issue#66) 
- hw_info: Protect log output against non-ASCII, closes #68
  (ville.skytta@iki.fi)
- secondary arch config cleanups (dennis@ausil.us)
- Point more links to github (ville.skytta@iki.fi)
- ignore exit codes from machinectl 
- create bind mount paths just before mounting (#57) 
- always print output of error in exception 
- fix syntax in docs-examples (gitDeveloper@bitthinker.com)
- do not refer to fedorahosted.org in Source0 
- Missed an instance of outer_buildroot (michael@cullen-online.com)
- Fixed up more PR comments, mostly being more consistent with naming
  (michael@cullen-online.com)
- Fixed pylint errors introduced by previous commit and other review comments
  (michael@cullen-online.com)
- Added command line options for overriding default bootstrap setting
  (michael@cullen-online.com)
- Bootstrap package manager using outer chroot (michael@cullen-online.com)
- Add %%distro_section macro to Mageia targets (ngompa13@gmail.com)
- test: ask for sudo password, so later we do not need to wait for password
- we cannot use /tmp for testing as that is automatically mounted as tmpfs by
  systemd-nspawn 
- add /dev/prandom device to chroot (#33) 
- add /dev/hwrng device to chroot (#33) 
- enable package_state plugin by default again [RHBZ#1277187]
  (gitDeveloper@bitthinker.com)
- Use python errno module instead of hardcoding errno values.
  (marcus.sundberg@aptilo.com)
- UidManager.changeOwner: Use _tolerant_chown for top level as well
  (marcus.sundberg@aptilo.com)
- Buildroot: Ensure homedir and build dirs always have correct owner
  (marcus.sundberg@aptilo.com)
- UidManager: Use os.lchown instead of os.chown
  (marcus.sundberg@aptilo.com)
- Buildroot._init: Ensure chrootuser always has correct UID
  (marcus.sundberg@aptilo.com)
- Buildroot._init: Ensure homedir is owned by correct user.
  (marcus.sundberg@aptilo.com)
- change_home_dir: Actually set ownership of homedir
  (marcus.sundberg@aptilo.com)
- fix permissions in chroot_scan's result dir, so user can delete it
  (gitDeveloper@bitthinker.com)
- spec: simplify condition 
- remove el6 references from spec file 
- use systemd-nspawn by default

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
