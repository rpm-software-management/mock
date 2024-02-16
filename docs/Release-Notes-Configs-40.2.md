---
layout: default
title: Release Notes - Mock Core Configs 40.2
---

## [Release 40.2](https://rpm-software-management.github.io/mock/Release-Notes-Configs-40.2) - 2024-02-16

### Mock Core Configs changes

- Per the approved [Fedora 40 change](https://fedoraproject.org/wiki/Changes/BuildWithDNF5),
  [we switched][PR#1332] the default `package_manager` configuration
  for Fedora 40 or newer to `dnf5`.
  This was previously done when Fedora 40 was Rawhide,
  but it [regressed][rhbz#2264535] when Fedora 40 branched.

**Following contributors contributed to this release:**

 * Miro Hrončok

[PR#1332]: https://github.com/rpm-software-management/mock/pull/1332
[rhbz#2264535]: https://bugzilla.redhat.com/2264535
