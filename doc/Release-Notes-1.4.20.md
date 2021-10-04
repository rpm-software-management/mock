---
layout: default
title: Release Notes 1.4.20
---

Released on 2019-10-04.

## Mock new features:

### Container image for bootstrap

Previously we have some incompatibilities between host and build target. They were, in fact, small. Like using a different package manager. Some were big. Like, the introduction of Weak and Rich dependencies. For this reason, we introduced [bootstrap](Feature-bootstrap). But then comes [zstd payload](https://fedoraproject.org/wiki/Changes/Switch_RPMs_to_zstd_compression). This is a new type of payload. And to install packages with this payload, you need rpm binary, which supports this payload. This is true for all current Fedoras. Unfortunately, neither RHEL 8 nor RHEL 7 supports this payload. So even bootstrap will not help you to build Fedora packages on RHEL 8.

We come up with a nice feature. Mock will not install bootstrap chroot itself. Instead, it will download the container image, extract the image, and use this extracted directory as a bootstrap chroot. And from this bootstrapped chroot install the final one.

Using this feature, **any** incompatible feature in either RPM or DNF can be used in the target chroot. Now or in future. And you will be able to install the final chroot. You do not even need to have RPM on a host. So this should work on any system. Even Debian based. The only requirement for this feature is [Podman](https://podman.io/).

This feature is now disabled by default. You can enable it using:

    config_opts['use_bootstrap_image'] = True

It can be enabled or disabled on the command line using `--use-bootstrap-image` or `--no-bootstrap-image` options.

Note however that also this is prerequisite:

    config_opts['use_bootstrap_container'] = True # or --bootstrap-chroot option

To specify which image should be used for bootstrap container you can put in config:

    config_opts['bootstrap_image'] = 'fedora:latest'

This is a general config. Each config has specified its own image specified. E.g. CentOS 7 has `config_opts['bootstrap_image'] = 'centos:7'` in config. So unless you use your own config, you can enable this feature, and the right image will be used.

There is one known issue:

 * Neither Mageia 6 nor 7 works correctly now with this feature.

Technically, you can use any container, as long as there is the required package manager (DNF or YUM). The rest of the needed packages will be installed by mock.

### Mockchain removed

Mockchain has been removed. I wanted to keep it longer, but because of [[RHBZ#1757388](https://bugzilla.redhat.com/show_bug.cgi?id=1757388)] I decided to remove it now. You should use `mock --chain` instead of `mockchain`. There is present simple wrapper `/usr/bin/mockchain` which calls `mock --chain`. Most of the mockchain parameters are still preserved for `mock --chain`.

### New config option `package_manager_max_attempts`

When your infrastructure is not reliable and you see failing builds because of network issues, you can increase number of attemps to execute package manager's action. This can be now tuned using:

    config_opts['package_manager_max_attempts'] = 1
    config_opts['package_manager_attempt_delay'] = 10

### Bind mount local repos to bootstrap chroot

Previously when you have in your config something like:

    config_opts['yum.conf'] = """
    ...
    [myrepo]
    baseurl=file:///srv/myrepo

then the path `/srv/myrepo` was not available inside of bootstrap container. The package manager was then unable to fetch those repositories.

This is now fixed and those directories are now automatically bind-mounted to bootstrap chroot.

This was actually the last known issue with bootstrap chroots. You may expect that in a future version of Mock, the bootstrap chroot will be enabled by default.

## Mock-core-config bugfixes

 * Fix baseurl typo in centos-stream config

 * Disabled modular repo for f29 - this was accidentally enabled during transition to templates.

## Mock bugfixes

 * Several files - mainly logs - are created as unprivileged user now. This will fix several issues when you use NFS. [[#341](https://github.com/rpm-software-management/mock/issues/341)], [[#322](https://github.com/rpm-software-management/mock/issues/322)], [[RHBZ#1751944](https://bugzilla.redhat.com/show_bug.cgi?id=1751944)]

 * `/var/log` is now ignored when creating root cache.

 * `mock --chain` now creates local repositories using `skip_if_unavailable=0`

Following contributors contributed to this release:

 * Daniel Mach
 * Denis Ollier
 * Chuanhao jin
 * Jakub Kadlcik
 * Jiri 'Ghormoon' Novak
 * Pavel Raiskup
 * Silvie Chlupova

Thank you.
