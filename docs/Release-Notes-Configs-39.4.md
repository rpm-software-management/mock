---
layout: default
title: Release Notes - Mock Core Configs 39.4
---

## [Release 39.4](https://rpm-software-management.github.io/mock/Release-Notes-Configs-39.4) - 2024-01-11

### Mock Core Configs changes

- The DNF4 caches downloaded RPMs in `/var/cache/dnf`.  This path has been
  changed in DNF5 to `/var/cache/libdnf5` and this change confuses some packages
  [rhbz#2256945][].  Thus, the Fedora mock configuration files have been fixed
  to use the same cache directory even with DNF5 — using the
  `system_config=/var/cache/dnf` DNF5 option.  See [PR#1150][] for more info. 

- The chroot configuration for Fedora 37 [has been EOLed][PR#1270], according to
  the [F39 schedule](https://fedorapeople.org/groups/schedule/f-39/f-39-all-tasks.html).

[PR#1270]: https://github.com/rpm-software-management/mock/pull/1270
[PR#1150]: https://github.com/rpm-software-management/mock/pull/1150
[rhbz#2256945]: https://bugzilla.redhat.com/2256945
