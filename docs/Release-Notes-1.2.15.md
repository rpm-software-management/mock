---
layout: default
title: Release Notes 1.2.15
---

mock-1.2.15 introduce these changes:

* Fedora 24 chroot configs (and Fedora 21 was removed).
* ccache plugin is by default off - to copy behaviour of Koji and Copr.
* ~/.config/mock.cfg is parsed too (beside ~/.mock/user.cfg).

And several bugfixes:
* buildroot is removed as root [RHBZ#1294979](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1294979)
* "local" dnf plugin is disable [RHBZ#1264215](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1264215)
