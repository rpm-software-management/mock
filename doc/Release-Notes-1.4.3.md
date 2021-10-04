---
layout: default
title: Release Notes 1.4.3
---

This is bug fix release, we fixed following issues:

* `--nocheck` macro was not properly escaped [[RHBZ#1473359](https://bugzilla.redhat.com/show_bug.cgi?id=1473359)].
* Use python3 and dnf module on Fedoras to guess architecture in `%post` scriptlet [[RHBZ#1462310](https://bugzilla.redhat.com/show_bug.cgi?id=1462310)].
* enhanced detection of RHEL [[RHBZ#1470189](https://bugzilla.redhat.com/show_bug.cgi?id=1470189)].
* scm: define `_sourcedir` to checkout directory [[PR#98](https://github.com/rpm-software-management/mock/pull/98)].
* Mageia Cauldron `releasever` is now 7 [[PR#95](https://github.com/rpm-software-management/mock/pull/95)]
* Create `/dev` nodes even when using `nspawn` [[RHBZ#1467299](https://bugzilla.redhat.com/show_bug.cgi?id=1467299)].
* SELinux: do not try to import yum when PM is dnf [[RHBZ#1474513](https://bugzilla.redhat.com/show_bug.cgi?id=1474513)].
* When you have hundreds of volumes in LVM you can tell mock to wait longer using `config_opts['plugin_conf']['lvm_root_opts']['sleep_time'] = 1`.

Thanks to following contributors:

* Igor Gnatenko
* Jonathan Lebon
* Mikolaj Izdebski
* Neal Gompa
* Ville Skyttä
* pixdrift
