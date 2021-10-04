---
layout: default
title: Release Notes 2.6
---

Released on - 2020-09-15.

## Mock 2.6 new features:

 * The default `--rebuild` mode now supports `-a|--addrepo` option, as
   well as the `--chain` did before,
   [rhbz#1857918](bugzilla.redhat.com/1857918).

 * The default `--rebuild` mode now also accepts URLs pointing at source
   RPMs.  In previous versions mock only worked with local source RPMs.
   The auto-downloading feature was previously available only in the
   `--chain` mode.

## Mock 2.6 bugfixes:

 * The configuration files inside buildroot are pre-configured
   (or re-configured) by mock even if they are pre-installed by packages
   as symbolic links, [rhbz#1878924](bugzilla.redhat.com/1878924).

 * Mock previously swallowed the 'rpm -i' error output when installing the
   source RPM into chroot and failed.  Newly the error output is printed to
   stderr.

 * Each particular build failure reason in `--chain` build is now properly
   dumped to stderr.

 * The `--chain` mode now fails right after the first build failure, as
   it was previously documented in the manual page.  To follow to the
   other package builds, one has to specify `--continue`.

 * Mock creates `/etc/localtime` as a symlink even with isolation=simple
   (per [fedora discussion](https://lists.fedoraproject.org/archives/list/devel@lists.fedoraproject.org/thread/BNTFZH6VS43Q7FLRIZYSBOTKDK6KMQZQ/)).

 * When systemd-nspawn supports the `--resolv-conf=`, mock newly always
   runs it with `--resolv-conf=off`.  This is done to revert back the previous
   expected name resolution behavior inside mock chroot (the new default
   --resolv-conf=auto has broken it).

The following contributors contributed to this release:

 * Miroslav Suchý

Thank you.
