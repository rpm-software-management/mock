---
layout: default
title: Release Notes - Mock 40.3
---

## [Release 40.3](https://rpm-software-management.github.io/mock/Release-Notes-40.3) - 2024-04-05


### Mock Core Configs changes

- Mock chroots for CentOS Stream 10 were added.
  They only use the Koji buildroot for now.
- The modular repositories have been dropped from Fedora releases,
  as Fedora Modularity has been retired, and these repositories
  are no longer maintained. ([PR#1340][])
- The modular repositories have been dropped from Fedora Rawhide,
  as Fedora Modularity has been retired, and these repositories
  are no longer maintained. ([PR#1340][])
- The openSUSE config files have been updated to use the [new `repo_arch` Jinja
  template](Release-Notes-5.5) instead of `target_arch`.  This change ensures that
  the bootstrap-from-image feature works correctly, always choosing the native
  architecture (regardless of multilib or forcearch builds).  It also ensures that
  multilib bootstrap installation works correctly even when the bootstrap image is
  OFF.


#### Following contributors contributed to this release:

- Miro Hrončok
- Neal Gompa
- Pavel Raiskup


[PR#1340]: https://github.com/rpm-software-management/mock/pull/1340
