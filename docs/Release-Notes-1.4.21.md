---
layout: default
title: Release Notes 1.4.21
---

Released on 2019-11-01.

## Mock-core-configs 31.7

 * Added configs for epel8-playground
 * Added 3 base packages to epel-playground and epel buildroot [RHBZ#1764445](https://bugzilla.redhat.com/show_bug.cgi?id=1764445)

## Mock 1.4.21 bugfixes:

This is a bugfix-only release. There is already ongoing work on 1.5.0 version. I cherry-picked some commits, which resolves some painfull bugs:

There were some issue with initialization of "Container image for bootstrap" feature. [GH#380](https://github.com/rpm-software-management/mock/issues/380). This is now fixed. As side effect there are two changes. Download of container image has been moved from `root_cache` plugin to main Mock code. As result you do not need to have root cache enabled to use this feature. Second, distribution-gpg-keys are always copied to bootstrap chroot if you use bootstrap container feature.

Commands `--install` and `--installdeps` now works with boostrap [RHBZ#1447627](https://bugzilla.redhat.com/show_bug.cgi?id=1447627)

There was an ugly bug, which involved systemd, CGroups v2 and SELinux and can lead to complete freeze of a system. This has been now resolved. [RHBZ#1756972](https://bugzilla.redhat.com/show_bug.cgi?id=1756972)

Rarely you may hit bug with incorrect rpmbuildstate. This is now fixed. [GH#349](https://github.com/rpm-software-management/mock/issues/349).

Following contributors contributed to this release:

 * Jakub Kadlcik
 * Merlin Mathesius
 * Pavel Raiskup

Thank you.
