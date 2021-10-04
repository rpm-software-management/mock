---
layout: default
title: Release Notes 1.4.1
---

There are new features:

* Mock previously used chroot technology. Few past releases Mock offered systemd-nspawn which is modern container technology for better isolation. This release use systemd-nspawn as default. If you want to preserve previous behaviour you can use `--old-chroot` option. *NOTE*: network is disabled inside container by default now; take a look into `site-defaults.cfg` for desired options (like `rpmbuild_networking`).
* Mock now uses bootstrap chroot to install target chroot. This is big change and see special paragraph at the bottom of this release notes.
* Chroot now contains `/dev/hwrng` and `/dev/prandom` when they exists in host [[#33](https://github.com/rpm-software-management/mock/issues/33)].
* We added `%distro_section` macro to Mageia configs.

There are some bugfixes:

* Resultdir is now chowned to user who executed mock so they can delete the files.
* `hw_info` plugin chown logs to user who executed mock also.
* Previously we declared that *package state plugin* is enabled by default, but the plugin was in fact disabled. It is now enabled by default (as stated in mock documentation) [[RHBZ#1277187](https://bugzilla.redhat.com/show_bug.cgi?id=1277187)].
* Creating directories for mount points have been delayed after mount of tmpfs [[#57](https://github.com/rpm-software-management/mock/issues/57)].
* Exit code of `machinectl` is now ignored as `machinectl` set non-zero code even for non-fatal errors. Errors which are quite often not relevant nor important for mock.
* `hw_info` plugin does not crash when output contains non-ASCII characters [[#68](https://github.com/rpm-software-management/mock/issues/68)].


Notes:
* This version has not been released for EL6. If you are using EL6 and you want to use latest Mock, please upgrade you infrastructure to EL7.
* Configs for `s390` architecture has been removed as it is not supported any more.
* Configs for `aarch64` and `ppc64le` now use different GPG key as those architectures has been moved from Secondary to Primary.
* Epel5 config points now to vault.centos.org. Note that EL5 has been EOLed. We will keep epel-5 config for some time. But any issue with building for epel-5 target will not be fixed.

## Bootstrap chroot

Mock is calling `dnf --installroot` to install packages for target architecture into target directory. This works. Mostly. The only problem that use host DNF and rpm to install packages. But this can cause problem when new RPM feature is introduces. Like Soft dependencies or Rich dependencies. When you have EL6 host and try to install Fedora rawhide package with Rich dependency then rpm will fail and you cannot do anything about it. You can upgrade your build machine to Fedora rawhide, but that is often not possible when it is part of critical infrastructure.

So we introduced Boostrap chroot. And 'we' actually means Michael Cullen who implement it. And Igor Gnatenko who proposed this idea. Big kudos for both of them.

Bootstrap chroot means that we first create very minimal chroot for target platform and we call DNF/YUM from that platform. For example: when you are on RHEL7 and you want to build package for `fedora-26-x86_64`, mock will first create chroot called `fedora-26-x86_64-bootstrap`, it will install DNF and rpm there (fc26 versions). Then it will call DNF from `fedora-26-x86_64-bootstrap` to install all needed packages to `fedora-26-x86_64` chroot.

The disadvantage is that you will need more storage in `/var/lib/mock`, the build is little bit slower. But you will hardly notice that unless you disabled `yum_cache` and `root_cache` plugins for some reasons.

The advantage is that you can use stable version of OS to build packages for even most recent OS. And vice versa.

If you want to preserve previous behaviour you can use `--no-bootstrap-chroot` command line option or set:

```
    config_opts['use_bootstrap_container'] = False
```

in your configuration.
