---
layout: default
title: Release Notes 1.4.8
---

Released on 2017-12-22.

Features:
* There is a new option --config-opts [GH#138](https://github.com/rpm-software-management/mock/issues/138)

You can run:

```
    mock --config-opts yum_command=/usr/bin/yum-deprecated --enable-network
```

which will set:

```
    config_opts['system_yum_command'] = '/usr/bin/yum'
```

or for a list:

```
    mock --config-opts extra_chroot_dirs=/mnt/b --config-opts extra_chroot_dirs=/mnt/a
```

which will set

```
    config_opts['extra_chroot_dirs'] = ['/mnt/b', '/mnt/a']
```

or list with a single item:

```
    mock --config-opts extra_chroot_dirs=/mnt/b --config-opts extra_chroot_dirs=
```

which will set

```
    config_opts['extra_chroot_dirs'] = ['/mnt/b']
```

It can detect boolean:

```
    mock --config-opts nosync=False --debug-config |grep nosync
    config_opts['nosync'] = False
```

A specialized option has priority. Therefore:

```
    mock --config-opts rpmbuild_networking=False --enable-network --debug-config |grep rpmbuild_networking
    config_opts['rpmbuild_networking'] = True
```

It is unable to set complicated variables. Like config_opts['plugin_conf']['package_state_opts'] or anything which has dictionary as value.

* There is a new option. `--enable-network` which is equivalent to `config_opts['rpmbuild_networking'] = True`

Bugfixes:
* orphanskill now emits SIGKILL when SIGTERM is not enough [RHBZ#1495214](https://bugzilla.redhat.com/show_bug.cgi?id=1495214)
* when mock tries to force umount, it will try umount recursively
* do not change to directory if nspawn is used [GH#108](https://github.com/rpm-software-management/mock/issues/108)
* when creating yum/dnf.conf, mock now copy timestamp from the host [RHBZ#1293910](https://bugzilla.redhat.com/show_bug.cgi?id=1293910)
* We now mount /proc and /sys in chroot before executing any package manager command (outside of chroot)[RHBZ#1467299](https://bugzilla.redhat.com/show_bug.cgi?id=1467299)
* Dependencies of mock-scm (git, cvs, tar, subversion) are now soft dependencies (Recommends) [RHBZ#1515989](https://bugzilla.redhat.com/show_bug.cgi?id=1515989)
* Previously job control in `mock shell` does not work. [RHBZ#1468837](https://bugzilla.redhat.com/show_bug.cgi?id=1468837). This was a glibc bug and it is resolved in rawhide now.

Following contributors contributed to this release:

* Matt Wheeler
* Matthew Stoltenberg
