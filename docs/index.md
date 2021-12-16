---
layout: title
---

# Mock

Mock is a tool for building packages. It can build packages for different architectures and different [Fedora](https://getfedora.org/), [RHEL](https://www.redhat.com/en/technologies/linux-platforms/enterprise-linux), and [Mageia](https://www.mageia.org/) versions than the build host have. Mock creates chroots and builds packages in them. Its only task is to reliably populate a chroot and attempt to build a package in that chroot.

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
* [Configs](#configs)
* [Plugins](#plugins)
* [Features](#features)
* [Using Mock outside your git sandbox](#using-mock-outside-your-git-sandbox)
* [FAQ](#faq)
* [Exit codes](#exit-codes)
* [Problems](#problems)
* [Generate custom config file](#generate-custom-config-file)
* [Using file:// URLs in configs](#using-file-urls-in-configs)
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
* [1.4.1](Release-Notes-1.4.1) (2017-04-26)
* [1.3.5](Release-Notes-1.3.5) - only for EL6
* [1.3.4](Release-Notes-1.3.4)
* [1.3.3](Release-Notes-1.3.3)
* [1.3.2](Release-Notes-1.3.2)
* [1.2.21](Release-Notes-1.2.21)
* [1.2.20](Release-Notes-1.2.20)
* [1.2.19](Release-Notes-1.2.19)
* [1.2.18](Release-Notes-1.2.18)
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

Configuration files are in `/etc/mock`.  Mock caches the downloaded rpm packages (via the `yum_cache` plugin), which speeds up subsequent builds by a considerable margin. Nevertheless, you may wish to change the default configuration to point to local repositories to speed up builds (see [note below](#generate-custom-config-file)).

By default, builds are done in `/var/lib/mock`, so be sure you have room there. You can change this via the `basedir` config option.

## Configs

Mock provides `mock-core-configs` with basic configs. Other projects can provide configs. We know of:

* [mock-centos-sig-configs](https://pagure.io/centos-sig-hyperscale/mock-centos-sig-configs)


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

By default, Mock uses [systemd-nspawn](https://www.freedesktop.org/software/systemd/man/systemd-nspawn.html) to isolate the build in chroot.  This is
not necessary though if you run Mock inside a container, and Mock is the only
service running there.  NB spawning **containers inside containers** isn't
implemented in Mock, so switching to `--isolation=simple` is mandatory.  Mock
is, though, able to automatically detect a container environment, and switch to
`--isolation=simple`.

One can even run Mock in a rootless Podman container without any special tweaks - the only necessary step is to run the
container with `--privileged` option.  Read the podman-run manual page for more
info, but `--privileged` - by the Podman nature - can not give the process more
permissions than the UID running the podman process already has; in other
words - `podman run --privileged` is a completely different thing from
`docker run --privileged`!

So simply, as any **non-privileged user**, do:

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

## Generate custom config file

Mock main config file is `/etc/mock/site-defaults.cfg`, which contains all defaults setting and all possible variables you can change.
Then you have `/etc/mock/<buildroot>.cfg` for various buildroots, which contains settings for yum/dnf which are for various distribution different.

When you want to alter the config you may copy one and edit it manually, however, if koji is already using such a config, then you can use  `mock-config --help` for information how to generate one. E.g.:
 `koji mock-config --tag f21-build --arch=aarch64  f21`

You should not alter `site-defaults.cfg` unless you want to change settings for all users. You should put your changes to `~/.mock/user.cfg` or to `~/.config/mock.cfg`.

The order of reading and evaluating configuration files is:

1. `/etc/mock/site-defaults.cfg`
1. `/etc/mock/<buildroot>.cfg`
1. `~/.mock/user.cfg`
1. `~/.config/mock.cfg` (since `mock-1.2.15`)

## See Also

* [Using Mock to test package builds](https://fedoraproject.org/wiki/Using_Mock_to_test_package_builds)  has some useful tips for using mock.
* [Mock Setup Using Local Mirror](https://fedoraproject.org/wiki/Docs/Drafts/MockSetupUsingLocalMirror)  Setting up a local mirror using Mock.
* [Legacy/Mock](https://fedoraproject.org/wiki/Archive:Legacy/Mock?rd=Legacy/Mock)  has some useful tips for building packages in mock for older Fedora and Red Hat Linux releases.
* [Increase Mock performance](http://miroslav.suchy.cz/blog/archives/2015/05/28/increase_mock_performance_-_build_packages_in_memory/index.html).
* [RPM Packaging Guide](https://rpm-packaging-guide.github.io/)
* [Modularity Features in Mock](http://frostyx.cz/posts/modularity-features-in-mock)

