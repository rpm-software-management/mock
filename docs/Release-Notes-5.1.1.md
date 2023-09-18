---
layout: default
title: Release Notes - Mock 5.1.1
---

Released on 2023-09-18.

## Mock 5.1.1 bugfixes

- [commit#1e13b56ce3c0efdf81][] caused "basedir" to be created only once per Mock
  run, but likewise directory "rootdir" was created only once.

  Since Mock automatically unmounts rootdir **after each build** and then
  also **removes the rootdir** directory to finish the cleanup tasks (at
  least if tmpfs or other "root" plugin is in use, --resultdir is in
  use, ...), subsequent builds failed to re-mount the rootdir with, e.g.:

      ERROR: Command failed:
      $ mount -n -t tmpfs -o mode=0755 -o nr_inodes=0 -o size=140g mock_chroot_tmpfs /var/lib/mock/fedora-37-x86_64-1694797505.326095/root

  This caused problems e.g. [in Fedora Copr][copr_issue#2916] where each
  Mock build is actually a two-step build done like:

      mock --spec foo.spec --sources . --resultdir ...

  So Mock first builds SRPM, and then builds RPMs (two builds in one run).

[commit#1e13b56ce3c0efdf81]: https://github.com/rpm-software-management/mock/commit/1e13b56ce3c0efdf81
[copr_issue#2916]: https://github.com/fedora-copr/copr/issues/2916
