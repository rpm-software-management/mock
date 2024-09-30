---
layout: default
title: Release Notes - Mock 5.9 (+configs v41.4)
---

## [Release 5.9](https://rpm-software-management.github.io/mock/Release-Notes-5.9) - 2024-09-30

### Bugfixes

- A fix for the DNF → DNF4 fallback has been applied.  Now Mock correctly
  selects DNF4, even when the `--no-bootstrap-chroot` command is used.  See
  [issue#1475][] for more info.

### Mock Core Configs changes

- The Fedora ELN configuration has been updated to download repositories using
  mirrors from the Fedora MirrorManager system.

#### Following contributors contributed to this release:

- Yaakov Selkowitz

Thank you!

[issue#1475]: https://github.com/rpm-software-management/mock/issues/1475
