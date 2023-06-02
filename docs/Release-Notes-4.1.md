---
layout: default
title: Release Notes - Mock v4.1
---

Released on 2023-06-05.

## Mock v4.1 new features:

- The `/bin/dnf` path can be either provided by [DNF5][] on newer systems
  ([Fedora 39+][default package manager in F39]), or by [DNF4][] on older
  systems.  The detection of `/bin/dnf` though wasn't ideal.  Newly, if [DNF4][]
  is requested, Mock searches for the `/bin/dnf-3` script instead.  Also, when
  installing [DNF4][] into a bootstrap chroot, `python3-dnf` is installed
  instead of just `dnf` which might install [DNF5][].

- We newly allow installing the bootstrap chroot using `/bin/dnf5` as fallback,
  if the requested package manager is not found on host (e.g. if
  `package_manager=dnf` is set for particular chroot, but only [DNF5][] is
  available on host, i.e. the future systems).  Previous version of Mock would
  just fail verbosely.

- The `mock.rpm` runtime dependencies were changed and relaxed.  We newly don't
  strictly require any of the package managers.  Having `dnf5` or `python3-dnf`
  installed on host is just a `Suggested` thing, and it is newly up to the user
  to install one of them (on Fedora 39+, [DNF5][] will be more commonly the
  choice).  Strictly speaking, with the `--use-bootstrap-image` feature, no
  package manager on host is needed at all.

- We use the same package manager search logic for bootstrap, non-bootstrap or
  bootstrap image use-cases.

## Mock v4.1 bugfixes:

- The Mock v4.0 broken chroot configurations with custom SSL certificates and
  bootstrap (the certificates were not copied into the bootstrap chroot
  correctly).  This problem [has been fixed][issue#1094].

- The `bind_mount` plug-in newly pre-creates the destination directory in-chroot
  for bind-mounted files.  See [PR#1093][] for more info.

- The --dnf-cmd option was fixed for the revamped `package_manager` detection
  logic.  See [PR#1087][] for more info.

[default package manager in F39]: https://fedoraproject.org/wiki/Changes/ReplaceDnfWithDnf5
[PR#1087]: https://github.com/rpm-software-management/mock/pull/1087
[PR#1093]: https://github.com/rpm-software-management/mock/pull/1093
[issue#1094]: https://github.com/rpm-software-management/mock/issues/1094
[DNF4]: https://github.com/rpm-software-management/dnf
[DNF5]: https://github.com/rpm-software-management/dnf5
