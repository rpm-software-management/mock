---
layout: default
title: Release Notes 1.2.16
---

mock-1.2.16 has been released to get rid of annoying errors due selinux [RHBZ#1312820](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1312820).

Additionally mock-1.2.16 introduces these changes:

* sparc configs has been removed
* instead of systemd-nspawn mock now requires systemd-container in F24+

And several bugfixes:
* do not call /bin/su and rather utilize --user of systemd-nspawn [RHBZ#1301953](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1301953)
* tell nspawn which variables it should set [RHBZ#1311796](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1311796)

Known issue:

* When you run mockchain with several SRPMs, then it may fails due deluser bug [RHBZ#1315864](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1315864)
