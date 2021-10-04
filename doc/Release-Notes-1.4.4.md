---
layout: default
title: Release Notes 1.4.4
---

This is bug fix release, we fixed following issues:

* Fedora 27 configs have been added.
* /etc/dnf/dnf.conf is used instead of /etc/dnf.conf
* /etc/dnf/dnf.conf is populated even when yum is used
* Rename group inside of chroot from mockbuild to mock - this will allow you to install mock inside of mock' chroot. Please invalidate your previous caches.
