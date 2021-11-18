---
layout: default
title: Release Notes 2.15
---

Released on - 2021-11-18


## Mock 2.15 contains just two bugfixes:

* Mock v2.13 and v2.14 had a problem with old-style specified `chroot` and
  `shell` mode (e.g. `--chroot` specified without leading dashes like `chroot`),
  together with commands specified after the `--` separator.  If used, Mock
  misinterpreted the first part of the command to be executed; concretely, `--`
  was considered to be a part of the command to be executed
  [[rhbz#2024620][rhbz#2024620]].

* Fixed English grammar in `mock.1` [[PR#796][PR#796]].


The following contributors contributed to this release:

 * Adam Williamson
 * Cheese1

[rhbz#2024620]: https://bugzilla.redhat.com/2024620
[PR#796]: https://github.com/rpm-software-management/mock/pull/796
