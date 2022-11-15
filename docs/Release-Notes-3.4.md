---
layout: default
title: Release Notes - Mock v3.4
---

Released on 2022-11-15.

## News in Mock v3.4:

- For cross-arch builds (see manual page for the `--forcearch` option), Mock
  tries to detect if the (potentially missing) `qemu-user-static` package is
  installed.  Since Fedora 37, the package got split into a set of packages
  arch-specific packages (like `qemu-user-static-x86`, `qemu-user-static-ppc`,
  etc.).  The Mock v3.4 does a better check, and raises more useful error if the
  package is missing.

- Mock newly provides the `/dew/mapper/control` file in chrot, so users may
  control the device mapper.  This has been requested by
  the [Koji team][kojipr#3585] while implementing Kiwi support [PR#1005][].


**Following contributors contributed to this release:**

 * Miroslav Suchý
 * Neal Gompa

Thank you.

[kojipr#3585]: https://pagure.io/koji/pull-request/3585
[PR#1005]: https://github.com/rpm-software-management/mock/pull/1005
