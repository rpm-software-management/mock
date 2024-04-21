---
layout: title
---

# Mock

Mock is a tool for building packages. It can build packages for different architectures and different [Fedora](https://getfedora.org/), [RHEL](https://www.redhat.com/en/technologies/linux-platforms/enterprise-linux), and [Mageia](https://www.mageia.org/) versions than the build host have. Mock creates chroots and builds packages in them. Its only task is to reliably populate a chroot and attempt to build a package in that chroot.

```
$ mock -r fedora-35-x86_64 package.src.rpm
...
Finish: rpmbuild packagei-1.98-1.fc35.src.rpm
Finish: build phase for package-1.98-1.fc35.src.rpm
INFO: Done(package.src.rpm) Config(fedora-35-x86_64) 2 minutes 14 seconds
INFO: Results and/or logs in: /var/lib/mock/fedora-35-x86_64/result
$  ls /var/lib/mock/fedora-35-x86_64/result
build.log  package-1.98-1.fc35.noarch.rpm  package-1.98-1.fc35.src.rpm  hw_info.log  installed_pkgs.log  root.log  state.log

$ mock -r centos-stream+epel-9-s390x package.src.rpm
...
$ mock -r alma+epel-8-x86_64 package.src.rpm
...
```

Mock also offers a multi-package command (`--chain`), that can build chains of packages that depend on each other.

Mock is capable of building SRPMs from source configuration management if the `mock-scm` package is present, then building the SRPM into RPMs. See `--scm-enable` in the documentation.

## Scope

 * Mock is a [`rpmbuild(8)`](https://linux.die.net/man/8/rpmbuild) wrapper. Mock tries to simplify some steps, which would otherwise be boring or complicated.
 * Mock runs `rpmbuild(8)` in an isolated environment consisting of a minimal set of packages.
 * Mock helps you find missing [`BuildRequires`](https://rpm-packaging-guide.github.io/#what-is-a-spec-file) - if it is missing and the package needs it, then the build fails.
 * Mock can build packages for various platforms and architectures. Some combinations of hosts and targets may need an additional configuration depending on your host platform.
 * Mock can prepare a fresh build/development environment for specific RPM-based operating systems.
 * Mock needs to execute some tasks under root privileges, therefore malicious RPMs can put your system at risk. Mock is not safe for unknown RPMs. If you want to build packages from untrusted sources, then use some wrapper around Mock like [OBS](https://openbuildservice.org/), [Copr](https://pagure.io/copr/copr/) or run Mock in a virtual machine.
 * Mock is neither container nor VM. Mock does some isolation, but it does not aim to be fully isolated.
 * Mock helps you open a shell within the buildroot to retrieve artifacts, or run commands for the purpose of debugging the build. It is not intended to run any production or developer application from there. For such purposes, you can use [podman](https://podman.io/) or [Flatpak](https://www.flatpak.org/).

## Content

* [Status](#status)
* [Release Notes](#release-notes)
* [Tarballs](#tarballs)
* [Download](#download)
* [Setup](#setup)
* [Chroot configuration files](Mock-Core-Configs)
* [Plugins](#plugins)
* [Features](#features)
* [Using Mock outside your git sandbox](#using-mock-outside-your-git-sandbox)
* [Mock inside Podman, Fedora Toolbox or Docker container](#mock-inside-podman-fedora-toolbox-or-docker-container)
* [FAQ](#faq)
* [Exit codes](#exit-codes)
* [Problems](#problems)
* [Mock configuration](configuration)
* [See Also](#see-also)

## Status

Mock is currently being used for all Fedora builds. It is called by [Koji](https://fedoraproject.org/wiki/Koji) and [Copr](https://copr.fedorainfracloud.org) to build chroots and packages.

Versions in Linux distributions:

<table border="0"><tr><td valign="top">
<img src="https://repology.org/badge/vertical-allrepos/mock.svg?exclude_unsupported=1&header=mock" alt="mock versions" />
</td><td  valign="top">
<img src="https://repology.org/badge/vertical-allrepos/mock-core-configs.svg?exclude_unsupported=1&header=mock-core-configs" alt="mock-core-configs versions" />
</td></tr></table>


## Release Notes
* [Configs 40.3](Release-Notes-Configs-40.3) - Added C10s chroots, Dropped Fedora modular repositories, fix bootstrap from image for openSUSE
* [Configs 40.2](Release-Notes-Configs-40.2) - Fixed Fedora 40 builds that regressed back to `dnf` (instead of expected `dnf5`).
* [5.5](Release-Notes-5.5) (2024-02-14) - The `{{ repo_arch }}` support added, chroot_scan supports tarballs, ownership during `--init` fixed, fixed `root_cache` tarball invalidation problem.
* [5.4](Release-Notes-5.4) (2024-01-04) - Bugfix the rpmautospec plugin.
* [5.3](Release-Notes-5.3) (2023-12-13) - New "rpmautospec" plugin added, `%generate_buildrequries` fixes landed.
* [Configs 39.3](Release-Notes-Configs-39.3) - Fedora 40+ configuration uses DNF5, Fedora ELN and OpenMandriva fixes.
* [Configs 39.2](Release-Notes-39.2) - Fedora ELN and openSUSE fixes.
* [5.2](Release-Notes-5.2) (2023-09-27) - Compatibility fix with EPEL 8, logging fixes, `--copyout` files with tilde in name.
* [5.1.1](Release-Notes-5.1.1) (2023-09-18) - If Mock does multiple builds at once, root directory is re-created for each of them.
* [5.1](Release-Notes-5.1) (2023-09-15) - Fixes for `--use-bootstrap-image`, it now retries pulling, and fallbacks to a normal bootstrap.
* [5.0](Release-Notes-5.0) (2023-08-09) - The `--use-bootstrap-image` feature enabled by default, using `/sbin/useradd` from host (not in chroot) and configurable.
* [4.1](Release-Notes-4.1) (2023-06-05) - Bug-fix v4.0 for bootstrap with custom SSL certificates, bug-fix 4.0 the --dnf-cmd option. Newly we use /bin/dnf-3 if `package_manager=dnf`, and dnf5 is used to install bootrap (if found on host).
* [4.0](Release-Notes-4.0) (2023-05-22) - Support for DNF5 added, the '--use-bootstrap-image' feature now works even if Mock is run in container.
* [3.5](Release-Notes-3.5) (2022-12-01) - Fixed detection of qemu-user-static* packages for the `--forcearch` feature.
* [3.4](Release-Notes-3.4) (2022-11-15) - Device Mapper control file exposed, better detection for qemu-user-static.
* [3.3](Release-Notes-3.3) (2022-10-17) - Mock can again be run by `root`, even though this is discouraged.
* [3.2](Release-Notes-3.2) (2022-10-14) - Optimized --list-chroots option, directories in `/var/lib` dropped SGID bit, `rpmbuild --noclean` is not used for old chroots (EL6 and older).
* [3.1](Release-Notes-3.1) (2022-07-22) - Fixes for new RPM with --no-cleanup-after, a new config `tar_binary` added, more convenient work with `/bin/bsdtar`.
* [3.0](Release-Notes-3.0) (2022-04-07) - Added --list-chroots command, a new seccomp option, Mock is not installable on EL7, dropped Python 2 compatibility.
* [2.16](Release-Notes-2.16) (2021-12-16) - EPEL 8 chroots removed, alternatives added.  New `ssl_extra_certs` option.  Bugfixes.
* [2.15](Release-Notes-2.15) (2021-11-18) - Fix for old-style `mock shell -- commands` variant.
* [2.14](Release-Notes-2.14) (2021-11-04) - Fix for broken `--enablerepo` and `--disablerepo` options.
* [2.13](Release-Notes-2.13) (2021-11-02) - New options `--additional-package` and `--debug-config-expanded`. Bugfixing.
* [2.12](Release-Notes-2.12) (2021-07-19) - bugfixes in Mock, but new config files in mock-core-configs
* [2.11](Release-Notes-2.11) (2021-06-09) - introduced `%{_platform_multiplier}` macro
* [2.10](Release-Notes-2.10) (2021-04-27) - smaller bugfixes
* [2.9](Release-Notes-2.9) (2021-01-18) - bugfixes, EOLed Fedora 31 and EPEL 6 chroots
* [2.8](Release-Notes-2.8) (2020-12-15) - bugfix in --isolation=nspawn, --isolation=simple was used instead
* [2.7](Release-Notes-2.7) (2020-12-01) - external build requires implemented, new rpkg_preprocessor plugin, bugfixes
* [2.6](Release-Notes-2.6) (2020-09-15) - bugfixing --chain mode and --isolation=nspawn
* [2.5](Release-Notes-2.5) (2020-09-03) - setting DNFs user_agent, a new showrc plugin added, new mock-filesystem package introduced
* [2.4](Release-Notes-2.4) (2020-07-21) - exposed btrfs-control, `module_setup_commands` configuration option, copy source CA certificates
* [2.3](Release-Notes-2.3) (2020-05-22) - bugfixes, mostly related to (by default on) bootstrap
* [2.2](Release-Notes-2.2) (2020-04-02) - bugfixing, mostly --bootstrap-chroot issues and mock-in-container use-cases
* [2.1](Release-Notes-2.1) (2020-03-11) - bugfixing
* [2.0](Release-Notes-2.0) (2020-02-07) - new major version, default --bootstrap-chroot
* [1.4.21](Release-Notes-1.4.21) (2019-11-01) - bugfixing
* [1.4.20](Release-Notes-1.4.20) (2019-10-04) - Container image for bootstrap, Mockchain removed, New config option package_manager_max_attempts, Bind mount local repos to bootstrap chroot
* [1.4.19](Release-Notes-1.4.19) (2019-09-10) - bugfixing
* [1.4.18](Release-Notes-1.4.18) (2019-08-27) - subscription-manager support; procenv plugin; automatic forcearch; signals propagated in chroot
* [1.4.17](Release-Notes-1.4.17) (2019-08-08) - Toolbox support, OpenMandriva, `mock --chain`, Dynamic Build Requires enabled by default
* [1.4.16](Release-Notes-1.4.16) (2019-05-22) - python3 on el7
* [1.4.15](Release-Notes-1.4.15) (2019-04-22) - Dynamic Build Requires; configurable list of disabled plugins; nice error for people not in mock group
* [1.4.14](Release-Notes-1.4.14) (2019-02-19) - Jinja2 templates; choose decompress program for root_cache
* [1.4.13](Release-Notes-1.4.13) (2018-08-13) - rawhide is gpg checked; new option `print_main_output`; proxy environmnet variables passed to mock; improved bash completation
* [1.4.11](Release-Notes-1.4.11) (2018-06-12) - new options `--force-arch`, `--spec`, `chrootuser`; MicroDNF support; BSDTar support
* [1.4.10](Release-Notes-1.4.10) (2018-05-10) - new overlayfs plugin; bind_mount can mount even files; chroot_scan can retrieve artifacts even from failed builds; introduced symlinks to rawhide configs
* [1.4.9](Release-Notes-1.4.9) (2018-02-12) - split of stdout and stderr; new option `optstimeout`
* [1.4.8](Release-Notes-1.4.8) (2017-12-22) - new option `--config-opts`
* [1.4.7](Release-Notes-1.4.7) (2017-10-31) - new option `chrootgroup`; config options for bootstrap; recognize DeskOS; handle network namespace in systemd container on our own
* [1.4.6](Release-Notes-1.4.6) (2017-09-15) - separation of mock-core-configs; new command `--debug-config`; short option `-N` for `--no-cleanup-after`
* [1.4.4](Release-Notes-1.4.4) (2017-08-22) - rename group inside of chroot from mockbuild to mock
* [1.4.3](Release-Notes-1.4.3) (2017-08-7)
* [1.4.2](Release-Notes-1.4.2) (2017-06-20)
* [1.4.1](Release-Notes-1.4.1) (2017-04-26) - introduced systemd-nspawn and `--old-chroot`option; new option `/dev/hwrng`, `/dev/prandom`; added `%distro_section` for Mageia; bugfixing
* [1.3.5](Release-Notes-1.3.5) (2017-03-02)- only for EL6; change path to the “df” in hw-info plugin
* [1.3.4](Release-Notes-1.3.4) (2017-02-27) - `.log` extension for the `available_pkgs` and `installed_pkgs` log files, support for custom nspawn args, new hw_info plugin, best=1 used for Rawhide, added Fedora 26 configs
* [1.3.3](Release-Notes-1.3.3) (2017-01-01) - bugfixing; a new config option for the builder hostname; upgraded temporary directories, chroot contains `best=1`
* [1.3.2](Release-Notes-1.3.2) (2016-10-17) - move /usr/sbin/mock/ to /usr/libexec/mock/mock; script in /usr/libexec/ are not in $PATH; F22 configs have been removed; --nocheck works; run mock in Docker; a lot of flake8/pep8/pycodestyle clean-ups
* [1.2.21](Release-Notes-1.2.21) (2016-09-12) - fix privilege escalation via mock-scm; rename of mageia pubkey
* [1.2.20](Release-Notes-1.2.20) (2016-08-17) - just a bugfix release, which uses correct gpg keys for epel in epel* configs.
* [1.2.19](Release-Notes-1.2.19)
* [1.2.18](Release-Notes-1.2.18) (2016-06-10) - Unconditional setup resolver config, added MPS personalities, requires rpm=pyton, use root name instead config name for backups dir, use DNF for F24 chroot, scm plugging handles better submodes and improve prompt
* [1.2.17](Release-Notes-1.2.17)
* [1.2.16](Release-Notes-1.2.16)
* [1.2.15](Release-Notes-1.2.15)
* [1.2.14](Release-Notes-1.2.14)
* [1.2.13](Release-Notes-1.2.13) (2016-08-17)

### Tarballs

Tarballs can be found at https://github.com/rpm-software-management/mock/releases

You can retrieve tarball from the command line:

```
git checkout --hard mock-1.4.20-1
cd mock
tito build --tgz
```

## Download

If you want to contribute to the code, please checkout https://github.com/rpm-software-management/mock for more information.

Otherwise, just run

    dnf install mock

For nightly builds, please refer to [developer documentation](https://github.com/rpm-software-management/mock#nightly)


## Setup

All users that are to use mock must be added to the *mock* group.

    usermod -a -G mock [User name]

:warning: _Mock runs some parts of its code with root privileges. There are known ways to get root access once a user is in the mock group (and once he is able to run mock). This is possible when a user abuses the mock configuration options. Please do not add anyone who is not trustworthy to the mock group!_

:notebook:  To have this change take effect you have to either log out and log back in or run command `newgrp -`

Mock caches the downloaded rpm packages (via the `yum_cache` plugin), which
speeds up subsequent builds by a considerable margin.  Nevertheless, you may
wish to [change the default configuration](configuration) to point to local
repositories to speed up builds.

By default, builds are done in `/var/lib/mock`, so be sure you have room there. You can change this via the `basedir` config option.

## Chroot config files

See a [separate document](Mock-Core-Configs).

## Plugins

* [bind_mount](Plugin-BindMount) - bind mountpoints inside the chroot
* [ccache](Plugin-CCache) - compiler cache plugin
* [chroot_scan](Plugin-ChrootScan) - allows you to retrieve build artifacts from buildroot (e.g. additional logs, coredumps)
* [compress_logs](Plugin-CompressLogs) - compress logs
* [hw_info](Plugin-HwInfo) - prints HW information of builder
* [lvm_root](Plugin-LvmRoot) - caching buildroots using LVM
* [mount](Plugin-Mount) - allows you to mount directories into chroot
* [overlayfs](Plugin-Overlayfs) - plugin implementing snapshot functionality (similary to lvm_root)
* [package_state](Plugin-PackageState) - dumps list of available and installed packages
* [pm_request](Plugin-PMRequest) - executes package manager commands requested by processes running in the chroot
* [procenv](Plugin-ProcEnv) - dumps the build process runtime within the chroot.
* [rpkg_preprocessor](Plugin-rpkg-preprocessor) - preprocess the input spec file just before srpm build starts
* [root_cache](Plugin-RootCache) - cache buildroots (as tar file)
* [scm](Plugin-Scm) - SCM integration module - builds directly from Git or Svn
* [selinux](Plugin-SELinux) - on SELinux enabled box, this plugin will pretend, that SELinux is disabled in build environment
* [showrc](Plugin-Showrc) - Log the content of `rpm --showrc` for capturing all defined macros
* [sign](Plugin-Sign) - call command on the produced rpm
* [tmpfs](Plugin-Tmpfs) - mount buildroot directory as tmpfs
* [yum_cache](Plugin-YumCache) - mount `/var/cache/{dnf,yum}` of your host machine to chroot

Plugins can be enabled on command line e.g `--enable-plugin=chroot_scan`. And you can set plugin options using e.g. `'--plugin-option=root_cache:age_check=False'`

Every plugin has a corresponding wiki page with docs.

[Order of plugins hooks](Plugin-Hooks).

## Features

* [container image for bootstrap](Feature-container-for-bootstrap) - set up bootstrap chroot using Podman.
* [bootstrap](Feature-bootstrap) - bootstrapping chroot. I.e., when building F28 on RHEL7, then first install very minimal bootstrap chroot with DNF and rpm from F28 and then use F28's rpm to install final F28 chroot.
* [external dependencies](Feature-external-deps) - use of external dependencies, e.g., `BuildRequires external:pypi:foo`.
* [forcearch](Feature-forcearch) - build for foreign architecture using emulated virtualization.
* [nosync](Feature-nosync) - speed up build by making `fsync`(2) no-op.
* [modularity](Feature-modularity) - support for Fedora Modularity.
* [package managers](Feature-package-managers) - supported package managers
* [rhel chroots](Feature-rhelchroots) - builds for RHEL
* [GPG keys and SSL](feature-gpg-and-ssl) - how to get your GPG keys and SSL certificates to buildroot

## Using Mock outside your git sandbox

Create your SRPM using `rpmbuild -bs`. Then change to the directory where your SRPM was created.

Now you can start mock with
```
mock -r <configname> --rebuild package-1.2-3.src.rpm
```

where `<configname>` is the name of a configuration file from `/etc/mock/`, without the `/etc/mock` path prefix and without the `.cfg` suffix.

Note that you can track the progress of mock using the logs stored in `/var/lib/mock/<configfile>/result`

## Mock inside Podman, Fedora Toolbox or Docker container

First, we need to state that Mock, in a nutshell, is a tool that (a) prepares an
appropriate RPM build environment (aka "build chroot" or "buildroot"), and then
it (b) just executes the RPM build inside (`rpmbuild` run).

The build environment is (again a bit simplified) defined by a set of RPM
packages that need to be installed in such environment (build dependencies, or
also `BuildRequires:` in RPM spec files).

Mock is a generic tool to build **any** RPM out there.  And each RPM has a
different set of requirements (so we can not just pre-generate one environment
for all packages and share it).  Here comes the important implication:  If you
want to **build an RPM**, you need to install **other RPMs**, and for that,
you need to have **root access**.

Normally, Mock uses `dnf --installroot /some/directory install ...` (on host)
to prepare the environment.  Then it switches into the environment using the
[systemd-nspawn](https://www.freedesktop.org/software/systemd/man/systemd-nspawn.html)
container (default `--isolation=nspawn`, but you can fallback to `--isolation=simple`
which is just `man (2) chroot`).  Again [simplified a bit](Feature-bootstrap).

The build itself (`rpmbuild` process) is a non-root operation, Mock
intentionally drops the privileges there.

All that said, using Mock inside a container to build RPMs is totally possible!
You just need to have permissions to install RPMs, and be able to switch UID
when needed (from `root` to non-privileged and back, `man (2) seteuid`).  As a
benefit, we don't need to run `systemd-nspawn` and still have even better
isolation because now even the `dnf --installroot` is executed inside the
container.  This statement assumes the container is dedicated to the Mock build
and no other task(s) that could be compromised by a rogue build (even subsequent
builds!).  So ideally, considering how easy is to start new containers from
images, each build should have its own dedicated container (especially if you
are a generic build system where you can not fully trust all your users, or even
the packages that your users with the best intentions build or install).  Then
the build can only affect the container, not the whole host.

So, Mock can be run in a rootless Podman container (with [user
namespaces](https://man7.org/linux/man-pages/man7/user_namespaces.7.html))
without any special tweaks.  The only necessary step is to run the container
with `--privileged` option.  Read the podman-run manual page for more info, but
`--privileged` - by the Podman nature - can not give the process more
permissions than the UID running the podman process already has; in other words
- `podman run --privileged` is a completely different thing from `docker run
--privileged`!

So simply, as any **non-privileged system user**, do:

```
$ podman run --rm --privileged -ti fedora:32 bash
# dnf install -y mock
# useradd mockbuilder
# usermod -a -G mock mockbuilder
# su - mockbuilder
$ mock https://some/online.src.rpm
$ mock --shell
#> ...
# etc
```

And similarly in `toolbox enter`.

But running Mock in an OpenShift POD isn't [typically
allowed](https://access.redhat.com/solutions/6375251).
Cluster admin typically keeps `SETUID` and `SETGID` [capabilities
dropped](https://docs.openshift.com/container-platform/4.12/authentication/managing-security-context-constraints.html),
`allowPrivilegeEscalation` disabled (no root access).  User namespaces are
[not yet available](https://access.redhat.com/solutions/6977863).  Per previous
implications, with the default security configuration, you can not install RPMs
in OpenShift POD containers and thus neither build RPMs.

You can run Mock in Docker container, however, you need to add `SYS_ADMIN`
capability to the docker container (or use `--privileged`).  I.e. run the
container like:

```
docker run --cap-add=SYS_ADMIN ...
```

:warning: Please note that Mock run inside of Docker container skips unsharing
of a namespace, so it runs in the same namespace as any other program in the
same container.  That means you should not run any other application inside of
that container.  Mock prints warning about this.  You can suppress this warning
when you put in the config

```
config_opts['docker_unshare_warning'] = False
```

## FAQ

See separate page: [FAQ](FAQ)

## Exit codes

Mock has various exit codes to signal a problem in the build. See https://github.com/rpm-software-management/mock/blob/master/mock/py/mockbuild/exception.py#L26

## Problems

[List of known issues](https://bugzilla.redhat.com/buglist.cgi?bug_status=NEW&bug_status=ASSIGNED&component=mock&known_name=mock-all&list_id=6164173&product=Fedora&product=Fedora%20EPEL&query_based_on=mock-all&query_format=advanced)

If you encounter a bug running mock, please file it in [Bugzilla](https://bugzilla.redhat.com/enter_bug.cgi?product=Fedora&component=mock): product "Fedora", component mock ([Open Bugs](https://bugzilla.redhat.com/buglist.cgi?query_format=advanced&product=Fedora&component=mock&bug_status=NEW&bug_status=ASSIGNED&bug_status=MODIFIED&bug_status=ON_DEV&bug_status=ON_QA&bug_status=VERIFIED&bug_status=FAILS_QA&bug_status=RELEASE_PENDING&bug_status=POST)).

If your problem is specific to EPEL, then [file it](https://bugzilla.redhat.com/enter_bug.cgi?product=Fedora%20EPEL&component=mock) against the "Fedora EPEL" product instead ([Open Bugs](https://bugzilla.redhat.com/buglist.cgi?query_format=advanced&product=Fedora%20EPEL&component=mock&bug_status=NEW&bug_status=ASSIGNED&bug_status=MODIFIED&bug_status=ON_DEV&bug_status=ON_QA&bug_status=VERIFIED&bug_status=FAILS_QA&bug_status=RELEASE_PENDING&bug_status=POST)).

## Users

If you use Mock, we'd love to hear from you and add you to this [wiki page](https://github.com/rpm-software-management/mock/wiki/Users). It will motivate our future work.

## See Also

* [Using Mock to test package builds](https://fedoraproject.org/wiki/Using_Mock_to_test_package_builds)  has some useful tips for using mock.
* [Mock Setup Using Local Mirror](https://fedoraproject.org/wiki/Docs/Drafts/MockSetupUsingLocalMirror)  Setting up a local mirror using Mock.
* [Legacy/Mock](https://fedoraproject.org/wiki/Archive:Legacy/Mock?rd=Legacy/Mock)  has some useful tips for building packages in mock for older Fedora and Red Hat Linux releases.
* [Increase Mock performance](http://miroslav.suchy.cz/blog/archives/2015/05/28/increase_mock_performance_-_build_packages_in_memory/index.html).
* [RPM Packaging Guide](https://rpm-packaging-guide.github.io/)
* [Modularity Features in Mock](http://frostyx.cz/posts/modularity-features-in-mock)
