---
layout: default
title: Release Notes 1.4.18
---

Released on 2019-08-27.

## Mock-core-configs new features:

 * New configs for RHEL. See [separate page](Feature-rhelchroots) for more info.
 * Fedora 31 has been added
 * Add local-source repo definition to Fedora Rawhide.
 * revert sysusers setting [RHBZ#1740545](https://bugzilla.redhat.com/show_bug.cgi?id=1737469)

## Mock new features and bugfixes:

 * When a foreign architect is detected, Mock will automatically enable `--forcearch`.
 * Support for subscription-manager has been added. See [RHEL chroots](Feature-rhelchroots) page.
 * bootstrap-chroot always explicitly install shadow-utils
 * Add [procenv plugin](Plugin-ProcEnv.md) for more detailed build time information. This plugin is disabled by default.
 * Resolved issues with SELinux from the previous release. You may still experience some warnings, but none of them should be fatal.
 * SIGTERM, SIGPIPE, and SIGHUP signals are now propagated to chroot.

## Future

Note that in upcoming versions, I would like to:

 * drop python2 support as even EL7 version is running on python3 now.
 * drop EL7 support (likely spring 2020). I mean to stop building Mock for EL7. Building packages for EL7 using Mock will be still supported.
 * make DNF default package manager. E.g., you will have to state in the config that you want to use yum explicitly.

Following contributors contributed to this release:

* Dominik Turecek
* Jan Buchmaier
* Jiri Konecny
* Miro Hrončok
* Pat Riehecky
* Pavel Raiskup

Thank you.
