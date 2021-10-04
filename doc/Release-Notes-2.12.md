---
layout: default
title: Release Notes 2.12
---

Released on - 2021-07-19


## Mock 2.12 bugfixes:

This is rather a small bugfix release, the most interesting stuff has been done
in mock-core-configs package (see below).

 * We don't set --cwd for --shell mode when a systemd-nspawn without the
   `--chdir` option is installed on the sytem (typically el7)

 * An RPM `addMacro()` traceback fixed.  The SCM plugin was fixed to explicitly
   convert the configured macro macro values (in e.g.
   `config_opts['macros']['%_platform_multiplier'] = 10`) to strings.
   [[PR 753][PR#753]]

 * Explicitly disabled versionlock DNF plugin by default, as we don't want to
   affect the builds. [[PR 747][PR#747]]

 * Mock package requirement on `shadow-utils` was removed from
   `mock-core-configs` to proper `mock-filesystem`. [[PR 743][PR#743]]


## Mock-core-configs v34.6:

 * CentOS Stream 9 "preview" files added

 * Rocky Linux configs added

 * AlmaLinux 8 AArch64 configs added.

 * Add AlmaLinux Devel repo as an optional repo for AlmaLinux 8.

 * Fixed GPG key path for SLE updates in openSUSE Leap 15.3.

 * Switch CentOS templates to use quay.io images for bootstrap.

 * EPEL Next 8 configs added.

The following contributors contributed to this release:

 * Carl George
 * Igor Raits
 * Louis Abel
 * Miroslav Suchý
 * Neal Gompa
 * Scott K Loga

Thank you!

[PR#747]: https://github.com/rpm-software-management/mock/pull/743
[PR#747]: https://github.com/rpm-software-management/mock/pull/747
[PR#753]: https://github.com/rpm-software-management/mock/pull/753
