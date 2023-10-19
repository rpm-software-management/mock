---
layout: default
title: Release Notes - Mock configs 39.2
---

### Mock Core Configs changes

- The set of GPG keys used for openSUSE Leap 15.5 was updated to include
  the correct key used for the openSUSE Backports repository.
- Previous versions of mock-core-configs referenced `fedora:latest` bootstrap
  images for `fedora-eln-ARCH` chroots, which led to preparation errors
  caused by [package incompatibilities][issue#1238].  ELN folks though already
  provide a better and
  ["native" ELN image](https://docs.fedoraproject.org/en-US/eln/deliverables/#_container_image),
  so the new Mock configs have been switched to use it.
- The `/etc/mock/default.cfg` link installation [has been fixed][pull#1236] for
  Fedora ELN.

[issue#1238]: https://github.com/rpm-software-management/mock/issues/1238
[pull#1236]: https://github.com/rpm-software-management/mock/pull/1236
