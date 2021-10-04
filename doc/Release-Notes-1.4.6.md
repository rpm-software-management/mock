---
layout: default
title: Release Notes 1.4.6
---

Released on 2017-09-15.

This is mostly a bugfix release, but there are some features too:

Features:

* All chroot configs have been moved to new package mock-base-configs. This will allow us to release new chroot configs independently of Mock main code.
* There is a new command --debug-config available. This command print current mock config (including defaults) to standard output and exit. This can be useful when you experience some issue, which you cannot reproduce anywhere else.
* There is a new script, which can add a default route to loopback for a container with private-network. This is an experimental feature, not used automatically, and will very likely change in future.
* There is short option `-N` for `--no-cleanup-after`.


Bugfixes:

* Mock again create /dev/loop nodes. This caused a lot of pain to Lorax users. [RHBZ#1481370](https://bugzilla.redhat.com/show_bug.cgi?id=1481370)
* Comment about nspawn/chroot default in site-defaults.cfg was previously incorrect, this has been fixed now.
* Previously when you used --private-network then the isolated network was used only during rpm build phase. And, e.g., for shell command, it was not used. This caused some confusion. Now the network is always switched when you specify --private-network.
* The bug "The buildroot LVM volume is not kept mounted after build" [RHBZ#1447658](https://bugzilla.redhat.com/show_bug.cgi?id=1447658) has been fixed once again. Hopefully this time correctly.

Following contributors contributed to this release:

* Brian C. Lane
* Jan Synacek
* Matej Kudera
* Michael Simacek
* Ville Skyttä

P.S. I did not skip 1.4.5. I just find a serious bug in requirement just after the release. So I made two releases in one day. :) This is united release notes.
