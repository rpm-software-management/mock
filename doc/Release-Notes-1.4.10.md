---
layout: default
title: Release Notes 1.4.10
---

Released on 2018-05-10.

Features:
- There is a new plugin [overlayfs](Plugin-Overlayfs). This plugin implements mock's snapshot functionality using overlayfs. From a user perspective, it works similar to LVM plugin, but unlike LVM plugin, it only needs a directory (not a volume group) for its data (snapshots).
- Previously a [bind_mount](Plugin-BindMount) plugin allowed to mount just a directory. Now, you can bind mount even a single file.
- Previously a [chroot_scan](Plugin-ChrootScan) allowed retrieving artifacts from chroot where build started. Now, it can extract objects even from chroot which failed to initialize.

Bugfixes:
- Change sign plugin to sign only built RPMs and not every file in results directory [RHBZ#1217495](https://bugzilla.redhat.com/show_bug.cgi?id=1217495)
- encode content before writing [GH#176](https://github.com/rpm-software-management/mock/issues/176)
- revert workaround introduced in 057c51d6 [RHBZ#1544801](https://bugzilla.redhat.com/show_bug.cgi?id=1544801)

Note:

Few weeks ago, I released a new `mock-core-configs` package and there is a new feature.

It contains:

```
$ ls -l /etc/mock
...
lrwxrwxrwx. 1 root mock    26 May  2 09:13 fedora-29-aarch64.cfg -> fedora-rawhide-aarch64.cfg
lrwxrwxrwx. 1 root mock    25 May  2 09:13 fedora-29-armhfp.cfg -> fedora-rawhide-armhfp.cfg
lrwxrwxrwx. 1 root mock    23 May  2 09:13 fedora-29-i386.cfg -> fedora-rawhide-i386.cfg
lrwxrwxrwx. 1 root mock    24 May  2 09:13 fedora-29-ppc64.cfg -> fedora-rawhide-ppc64.cfg
lrwxrwxrwx. 1 root mock    26 May  2 09:13 fedora-29-ppc64le.cfg -> fedora-rawhide-ppc64le.cfg
lrwxrwxrwx. 1 root mock    24 May  2 09:13 fedora-29-s390x.cfg -> fedora-rawhide-s390x.cfg
lrwxrwxrwx. 1 root mock    25 May  2 09:13 fedora-29-x86_64.cfg -> fedora-rawhide-x86_64.cfg
```

The plan is that during Fedora branching event I will:

* remove those symlinks and create regular files pointing to Fedora 29 repos
* create fedora-30-* as symlinks to fedora-rawhide-*

This will give you a choice to target rawhide using "rawhide" string or using the number.

Following contributors contributed to this release:

* Martin Necas
* Michal Novotný
* Neal Gompa
* Todd Zullinger
* Zdenek Zambersky

Thank you.
