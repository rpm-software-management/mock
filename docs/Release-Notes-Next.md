---
layout: default
title: Release Notes - Mock v?.?
---

Released on ????-??-??.

## Mock v?.? new features:

- Automatic downloads (for example with `mock https://exmaple.com/src.rpm`
  use-cases) has been changed to automatically retry the download several times
  to work-around random network failures ([PR#1132][] and [PR#1134][]).

- The `dnf` and `dnf5` processes are newly always executed with the
  `--setopt=allow_vendor_change=yes` option.  This is done in belief that we
  don't have to protect the Mock builds against `Vendor` changes, and we do this
  because overriding the distro-default RPMs is quite common thing (`mock
  --chain` e.g.) while mimicking the distro-default `Vendor` tag would be
  a painful task.  The thing is that the `allow_vendor_change=no` is going to be
  set by default in DNF5 soon and we want to prevent unnecessary surprises.
  Also, openSUSE has been reported to use this even now with DNF4 ([PR#1160][]).

## Mock v?.? bugfixes:

-

## mock-core-configs v?.? changes:

- ...

**Following contributors contributed to this release:**

 * zengwei2000

Thank you.

[PR#1132]: https://github.com/rpm-software-management/mock/pull/1132
[PR#1134]: https://github.com/rpm-software-management/mock/pull/1134
[PR#1160]: https://github.com/rpm-software-management/mock/pull/1160
