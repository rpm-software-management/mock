---
layout: default
title: Release Notes - Mock v3.5
---

Released on 2022-12-01.

## News in Mock v3.5:

- For cross-arch builds (see manual page for the `--forcearch` option), Mock
  tries to detect if the (potentially missing) `qemu-user-static` package is
  installed.  Since Fedora 37, the package got split into a set of packages
  arch-specific packages (like `qemu-user-static-x86`, `qemu-user-static-ppc`,
  etc.).  The Mock v3.4 does a better check, and raises more useful error if the
  package is missing.

  In Mock v3.5 we further enhanced the related error message(s).

  We also fixed a bug in the detection mechanism — mock no longer fails-hard for
  a missing architecture (not configured in
  `config_opts['qemu_user_static_mapping']`).  Mock in such situation newly just
  tries its best and continues the build, even though failure is likely.

[PR#1007]: https://github.com/rpm-software-management/mock/pull/1007
