---
layout: default
title: Release Notes - Mock Configs 41.1 (and typofix 41.2)
---

## [Release Configs 41.1](https://rpm-software-management.github.io/mock/Release-Notes-Configs-41.1) - 2024-08-14


### Mock Core Configs changes

- Configuration files for Fedora 41 have been branched from Rawhide, according
  to the [Fedora 41 Schedule](https://fedorapeople.org/groups/schedule/f-41/f-41-all-tasks.html).
- The "early" CentOS Stream 10 + EPEL 10 configuration files have been added,
  [issue#1421][].  These chroots only work with Fedora EPEL Koji buildroot(s).
- Add configuration for openEuler 24.03 LTS.
- Mock chroots for CentOS Stream 10 now use the mirrored repositories also for
  baseos-source, baseos-debuginfo, appstream-source, appstream-debuginfo,
  crb-source, and crb-debuginfo.
- The CentOS 7 [is now EOL](https://www.redhat.com/en/topics/linux/centos-linux-eol)
  and the mirroring is disabled.  Corresponding configuration files have been
  moved to `/etc/mock/eol` and are pointing now to vault.centos.org.

  Similarly, EPEL 7 [goes EOL](https://pagure.io/epel/issue/238), too.  Moving
  EPEL 7 configuration to `/etc/mock/eol`, too.
- The Fedora ELN ix86 config has been removed, as 32-bit multilibs are no longer
  built for ELN.
- Fedora Rawhide configurations, such as releasever=41 now, accept GPG keys from
  Fedora releasever+1 (for example, 42, not yet used for RPM signatures).  This
  change is implemented to address the typically short and unnecessary
  inconvenience during [the Fedora branching process][issue#1338] in the future.
- The Fedora Rawhide configuration (F41+) has been updated to use the
  `bootstrap_image_ready = True` configuration.  The default container images are
  [already shipped with the `dnf5-plugins` package](https://pagure.io/fedora-kiwi-descriptions/pull-request/63).

  This means we use the container image "as is" to bootstrap the DNF5 stack
  without installing any additional packages into the prepared bootstrap chroot.
  Consequently, the bootstrap preparation is much faster (bootstrap preparation
  basically equals the image download, if not pre-downloaded, and its subsequent
  "extraction").

#### Following contributors contributed to this release:

- Daan De Meyer
- Jakub Kadlcik
- Jiri Kyjovsky
- Miro Hrončok
- nucleo
- Robert Scheck
- Yaakov Selkowitz

Thank you!

[issue#1338]: https://github.com/rpm-software-management/mock/issues/1338
