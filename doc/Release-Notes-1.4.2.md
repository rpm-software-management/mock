---
layout: default
title: Release Notes 1.4.2
---

There are new features:

* The bootstrap feature is now disabled by default. There were too many issues with it. You can enable it locally with `--bootstrap-chroot`, but first see knows [bugs](https://bugzilla.redhat.com/buglist.cgi?bug_status=NEW&bug_status=ASSIGNED&component=mock&known_name=mock-all&list_id=7491839&product=Fedora&product=Fedora%20EPEL&query_based_on=mock-all&query_format=advanced) and [issues](https://github.com/rpm-software-management/mock/issues).
* There is initial support for Fedora Modularity. You can add to config:

```
config_opts['module_enable'] = ['list', 'of', 'modules']
config_opts['module_install'] = ['module1/profile', 'module2/profile']
```

This will call `dnf module enable list of modules` and `dnf module install module1/profile module2/profile` during the init phase. EDIT: If you want to use this feature you have to have experimental DNF, it can be obtained from this [Copr project](https://copr.fedorainfracloud.org/coprs/mhatina/DNF-Modules/).

There are some bugfixes:

* NSpawn chroot is switched off for EL6 targets [[RHBZ#1456421](https://bugzilla.redhat.com/show_bug.cgi?id=1456421)].
* LVM root is not umounted when `umount_root` is set to false [[RHBZ#1447658](https://bugzilla.redhat.com/show_bug.cgi?id=1447658)]
* Shell in NSpawn container is now called with `--login` so `profile.d` scripts are executed [[RHBZ#1450516](https://bugzilla.redhat.com/show_bug.cgi?id=1450516)] [[RHBZ#1462373](https://bugzilla.redhat.com/show_bug.cgi?id=1462373)]
* yum rather then yum-deprecated is used when using bootstrap chroot [[RHBZ#1446294](https://bugzilla.redhat.com/show_bug.cgi?id=1446294)]
* Custom chroot does not use bootstrap [[RHBZ#1448321](https://bugzilla.redhat.com/show_bug.cgi?id=1448321)]
* Mock now use `dnf repoquery` instead of repoquery for chroots which uses DNF.
* LVM's scrub hook for bootstrap chroot is called [[RHBZ#1446297](https://bugzilla.redhat.com/show_bug.cgi?id=1446297)]
* `--mount` will mount LVM volumes [[RHBZ#1448017](https://bugzilla.redhat.com/show_bug.cgi?id=1448017)]

