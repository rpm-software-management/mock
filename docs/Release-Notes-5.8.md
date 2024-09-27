---
layout: default
title: Release Notes - Mock 5.8
---

## [Release 5.8](https://rpm-software-management.github.io/mock/Release-Notes-5.8) - 2024-09-27


### Bugfixes

- Mock v5.7 introduced a regression in the `chroot_scan` plugin that prevented the
  result directory from being created properly. This issue has been
  [fixed][PR#1472] - and is the major reason for doing v5.8 bugfix release.

- The ownership of the tarball provided by `chroot_scan` (when `write_tar =
  True`) has been corrected, ensuring the file is no longer root-owned.

- The `chroot_scan` plugin now consistently uses the `util.do` method instead of
  custom `subprocess.call` calls.  This ensures that the `mock --verbose` output
  properly displays the commands (like `cp`, or `tar`) being executed.


[PR#1472]: https://github.com/rpm-software-management/mock/pull/1472
