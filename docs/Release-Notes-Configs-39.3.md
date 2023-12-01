---
layout: default
title: Release Notes - Mock Core Configs 39.3
---

## [Release 39.3](https://rpm-software-management.github.io/mock/Release-Notes-Configs-39.3) - 2023-12-01

### Mock Core Configs changes

- Per the approved [Fedora 40 change](https://fedoraproject.org/wiki/Changes/BuildWithDNF5),
  [we switched][PR#1256] the default `package_manager` configuration for Fedora 40
  (Rawhide at that point in time) to `dnf5`.  DNF5 is [the future replacement for
  DNF4](https://fedoraproject.org/wiki/Changes/ReplaceDnfWithDnf5), aiming to be
  much faster than its predecessor.  Hence, the effect of this change is a
  significantly faster buildroot preparation.
- The default `fedora-eln-*` bootstrap image `quay.io/fedoraci/fedora:eln`
  [has been fixed](https://github.com/fedora-eln/eln/issues/166) to provide
  the `dnf builddep` command.  It means it is now "ready for bootstrap" right
  after the image download (no additional packages need to be installed inside)
  which makes the buildroot preparation
  [much faster](https://rpm-software-management.github.io/mock/Feature-container-for-bootstrap).
- The OpenMandriva chroots provide `python-dnf` and `python-dnf-plugins-core`
  packages, not `python3-dnf` and `python3-dnf-plugins-core`.  That's why we
  [had to fix][issue#1251] the `dnf_install_command` config option appropriately.

[PR#1256]: https://github.com/rpm-software-management/mock/pull/1256
[issue#1251]: https://github.com/rpm-software-management/mock/issues/1251
