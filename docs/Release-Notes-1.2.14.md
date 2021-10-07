---
layout: default
title: Release Notes 1.2.14
---

mock-1.2.14 is bugfix release, but some bugfix may be interesting for you:

* --new-chroot now works on rhel7
* create tmpfs with unlimited inodes [RHBZ#1266453](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1266453) - otherwise architectures with large pages (e.g. PPC64) can use only fraction of the tmpfs capacity.
* Add %(resultdir) placeholder for sign plugin. [RHBZ#1272123](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1272123)
* use --setopt=deltarpm=false as default value for dnf_common_opts [RHBZ#1281355](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1281355)
* fixed issue with /home mount on nfs [RHBZ#1281369](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1281369)
