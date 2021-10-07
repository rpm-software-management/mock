---
layout: default
title: Release Notes 1.4.7
---

Released on 2017-10-31.

Features:

* There is a new option in config `config_opts['chrootgroup']`, which allows you to change name of group inside of chroot.
* Any key for `config_opts` you specify with 'bootstrap_*' will be copied to bootstrap config e.g., `config_opts['bootstrap_system_yum_command'] = '/usr/bin/yum-deprecated'` will become `config_opts['system_yum_command'] = '/usr/bin/yum-deprecated'` for bootstrap config.
* There are three new default:
```
    config_opts['bootstrap_chroot_additional_packages'] = []
    config_opts['bootstrap_module_enable'] = []
    config_opts['bootstrap_module_install'] = []
```
  This will not install any additional packages or modules into bootstrap chroot.
* Mock now recognize DeskOS.
* Previously when `config_opts['rpmbuild_networking']` was enabled we passed `--private-network` to systemd-nspawn. However that lead there was no default route. And you cannot bind() UDP socket to all IP addresses and then join multicast group, without having default route. Now we do onot add `--private-network` to systemd-nspawn, instead we setup network namespace ourselves and we also add default route pointing to loopback interface (only interface in the new namespace). This feature introduce new dependency on pyroute2.

Bugfixes:

* Delete rootdir as well when calling clean. In case one overrides the rootdir option, and the rootdir is located outside of basedir, it was not cleaned up when calling --clean. Fix this case by checking if the rootdir is outside basedir. If that is the case, run an extra rmtree() on it.
* Choose good symbolic link of default.cfg on Mageia.
* Ccache is now mounted to /var/tmp as /tmp gets over-mounted with tmpfs when system-nspawn is used.
* Output of `--debug-config` is now sorted.
* Use primary key for Fedora 27+ on s390x.

Following contributors contributed to this release:

* Andreas Thienemann
* Dan Horák
* Jan Pokorný
* Mark D Horn
* Michal Sekletar
* Neal Gompa
* Ricardo Arguello
