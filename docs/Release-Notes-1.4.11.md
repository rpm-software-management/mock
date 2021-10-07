---
layout: default
title: Release Notes 1.4.11
---

Released on 2018-06-12.

## Features:

- Previously you were able to only build for compatible architectures. I.e., you can build `i386` package on `x86_64` architecture. When you tried to build for incompatible architecture, you get this error:

```
$ mock -r fedora-28-ppc64le shell
ERROR: Cannot build target ppc64le on arch x86_64, because it is not listed in legal_host_arches ('ppc64le',)
```

Now, you can build for any architecture using new option --force-arch ARCH. [GH#120](https://github.com/rpm-software-management/mock/issues/120) You have to have installed package `qemu-user-static`, which is a new soft dependence. Try this:

```
$ sudo dnf install qemu-user-static
$ mock -r fedora-28-ppc64le --forcearch ppc64le shell
```

and you get the prompt in PPC64LE Fedora. You can do this for any architecture supported by QEMU. Note: Do not confuse `--forcearch` and `--arch` which are very different options.

- Mock previously only supported GNU Tar. Now Mock supports BSD Tar as well. [GH#169](https://github.com/rpm-software-management/mock/issues/169) There is a new option in config available:

```
# You can configure which tar is used (for root cache and SCM plugin)
# valid options are: "gnutar" or "bsdtar"
# config_opts['tar'] = "gnutar"
```

Be aware that if you created a cache using gnutar then you cannot extract it using bsdtar. Therefore when changing this option, you have to scrub all caches.


- There is a new config option:

```
# name of user that is used when executing commands inside the chroot
# config_opts['chrootuser'] = 'mockbuild'
```

This can be changed to different value. E.g., 'root'. However, be aware that any other value than 'mockbuild' is not tested by upstream.

- There is initial support for MicroDnf [GH#76](https://github.com/rpm-software-management/mock/issues/76) Be aware the due MicroDNF is missing `--installroot` option, the buildroot and build dependencies are still installed by DNF. These are new options related to MicroDNF:

```
# config_opts['microdnf_command'] = '/usr/bin/microdnf'
## "dnf-install" is special keyword which tells mock to use install but with DNF
# config_opts['microdnf_install_command'] = 'dnf-install microdnf dnf dnf-plugins-core distribution-gpg-keys'
# config_opts['microdnf_builddep_command'] = '/usr/bin/dnf'
# config_opts['microdnf_builddep_opts'] = []
# config_opts['microdnf_common_opts'] = []
# config_opts['microdnf_command'] = '/usr/bin/microdnf'
config_opts['package_manager'] = 'microdnf'
```

Right now, Mock does not ship any config which use this package manager.

- There is a new option `--spec`, which you can use to build an SRPM.

```
# dnf download --source foo
# rpm2cpio foo.src.rpm | cpio -dimv
(Add/modify compilation flags in .spec file)
# mock --spec foo.spec foo.src.rpm --postinstall
(or)
# mock --spec foo.spec --sources ./
```


## Bugfixes:

- The file `/etc/resolv.conf` is now empty when networking is disabled. [RHBZ#1514028](https://bugzilla.redhat.com/show_bug.cgi?id=1514028) This reduces timeout when code tries to connect to a network. Note that option `config_opts['use_host_resolv']` changed from True to False as networking is disabled by default too. Note that `--enable-network` automatically set `config_opts['use_host_resolv']` to True now.

Following contributors contributed to this release:

* ArrayMy
* Ken Dreyer
* Neal Gompa
* Neil Horman
* Sam Fowler
* Todd Zullinger

Thank you.
