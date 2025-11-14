---
layout: default
title: Release Notes - Mock core configs 43.3
---

## [Release 43.3](https://rpm-software-management.github.io/mock/Release-Notes-Configs-43.3) - 2025-11-14


### Mock Core Configs changes

- Kylin OS has [updated all container images for supported
  versions](https://cr.kylinos.cn/zh/image), so use those for bootstrapping.

- Add openSUSE Leap 16.0 configurations.  Some of the packages are signed with
  the ALP Package signing key from SUSE Linux Enterprise 16.  openSUSE Leap 16.0
  does not have `leap-dnf` images available, so do not use a bootstrap image.
  At the moment of writing this, openSUSE Leap 16.0 [does not have all the other
  repositories of 15.6 available](https://en.opensuse.org/Package_repositories).


#### The following contributors have contributed to this release:

- Simone Caronni

Thank You!
