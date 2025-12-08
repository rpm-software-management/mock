---
layout: default
title: Release Notes - Mock 6.6
---

## [Release 6.6](https://rpm-software-management.github.io/mock/Release-Notes-6.6) - 2025-12-08


### Changes

- Make sure to install `BuildRequires` that are defined by macros originating
  from macro files installed through other BuildRequires.  For example:

  ```
  BuildRequires: selinux-policy
  %{?selinux_requires}
  ```

  This now properly tells Mock to install the `selinux-policy-devel` package, as
  defined by `%selinux_requires`.  See also [issue#1652][].

- The `unbreq` plugin is now active only when an actual build is taking place.
  It no longer searches for SRPM files during unrelated Mock operations, such as
  `--init` or `--clean`.

- Mock now automatically maps the target build architecture directly to the
  appropriate QEMU user-static binary variant for `forcearch` builds.  For
  example, a build for `riscv64` (for `fedora-43-riscv64` target) is mapped to
  `/usr/bin/qemu-riscv64-static` (see the architecture string matches).  Mock
  config contributors no longer need to modify Mock code to add support for new
  architectures (if these architecture specifiers match).


#### The following contributors have contributed to this release:

- Jakub Kadlcik
- Marián Konček
- Simone Caronni

Thank You!

[issue#1652]: https://github.com/rpm-software-management/mock/issues/1652
