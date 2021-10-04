---
layout: default
title: Release Notes 2.8
---

Released on - 2020-12-15.

## Mock 2.8 bugfixes:

  * The systemd-nspawn wasn't used for --isolation=nspawn.  This is regression
    in the release v2.7.  See [issue 678][issue#678].

  * Better error message for certain `rmtree` failures, [PR 677][PR#677].

The following contributors contributed to this release:

  * Adam Williamson
  * Miroslav Suchý
  * Timm Bäde

Thank you!

[issue#678]: https://github.com/rpm-software-management/mock/issues/678
[PR#677]: https://github.com/rpm-software-management/mock/pull/677
