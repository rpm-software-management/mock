---
layout: default
title: Release Notes - Mock 6.3
---

## [Release 6.3](https://rpm-software-management.github.io/mock/Release-Notes-6.3) - 2025-06-18


### New features

- The `hw_info` plugin now reports memory info units in [human readable scale][PR#1587].


### Bugfixes

- The `/bin/dnf` command is no longer hardcoded
  [in the --calculate-build-dependencies code][issue#1592], and we
  use the standard `config_opts['dnf5_command']` (or
  `config_opts['dnf_command']`, respectively).

- The mechanism for creating the `mock` group has been fixed again on
  Fedora/RHEL, because the built-in RPM user creation mechanism only works on
  F42 and newer.  Mock on older distributions returned back to using `%pre`
  scriptlet.

- The `mock-core-configs` package files were previously owned by the `mock`
  group, same as a few files in `mock` package — which was unnecessary.  These
  files are intended to be read-only and accessible by anyone.  This issue was
  actually [causing install-order problems][issue#1588] when `mock-core-configs`
  or `mock` was installed before `mock-filesystem`.  So newly those files have
  the default `0644, root, root` ownership.

- This release includes a fix for a Python 3.14 [incompatibility][issue#1594].

  Mock refused to start as non-root user with Python 3.14.  This was because of
  the change in behaviour of ProcessPoolExecutor in Python.  The code has been
  altered to work with both old and new Python.

### Mock Core Configs changes

- Added AlmaLinux 10 configs
- Add AlmaLinux kitten 10 x86_64_v2 config
- Added Rocky Linux 10 configs

#### The following contributors have contributed to this release:

- FeRD (Frank Dana)
- Javier Hernández
- Jonathan Wright
- Konstantin Shalygin
- Louis Abel
- Miroslav Suchý

Thank You!


[issue#1592]: https://github.com/rpm-software-management/mock/issues/1592
[issue#1588]: https://github.com/rpm-software-management/mock/issues/1588
[PR#1587]: https://github.com/rpm-software-management/mock/pull/1587
[issue#1594]: https://github.com/rpm-software-management/mock/issues/1594
