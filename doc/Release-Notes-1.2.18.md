---
layout: default
title: Release Notes 1.2.18
---

mock-1.2.18 has several bugfixes:

* copy just content of SRPM not the attributes ([RHBZ#1301985](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1301985))
* do not fail when we cannot link default.cfg ([RHBZ#1305367](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1305367))
* Build always fails when using --nocheck ([RHBZ#1327594](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1327594))
* keep machine-id in /etc/machine-id ([RHBZ#1344305](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1344305))

And several changes:
* Unconditionally setup resolver config
* use DNF for F24 chroot
* requires rpm-python
* Escape the escape sequences in PROMPT_COMMAND, improve prompt
* Use root name instead config name for backups dir
* Add MIPS personalities
* scm plugin handle better submodules

And there are two new groups of configs. There are new [Mageia](https://www.mageia.org) configs:
* mageia-cauldron-armv5tl
* mageia-cauldron-armv7hl
* mageia-cauldron-i586
* mageia-cauldron-x86_64
* mageia-6-armv5tl
* mageia-6-armv7hl
* mageia-6-i586
* mageia-6-x86_64

And there are new custom configs:
* custom-1-aarch64
* custom-1-armhfp
* custom-1-i386
* custom-1-ppc64
* custom-1-ppc64le
* custom-1-s390
* custom-1-s390x
* custom-1-x86_64

Those configs does not have any repository configured and base is empty. I.e:

    config_opts['chroot_setup_cmd'] = ""


This is useful if you want to prepare the chroot yourself. Or when you use it with mockchain with `--addrepo=REPOS` option. This was added on request of [Koschei](https://fedoraproject.org/wiki/Koschei), which will use it.
