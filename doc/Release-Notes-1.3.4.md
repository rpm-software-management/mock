---
layout: default
title: Release Notes 1.3.4
---

There are new features:

* [scm plugin](Plugin-Scm) now supports [DistGit](https://github.com/release-engineering/dist-git/) (or DistSVN etc.) .
* log files of [package_state plugin](Plugin-PackageState) got `.log` extension. I.e. `available_pkgs.log` and `installed_pkgs.log`.
* Configuration files for Fedora 26 has been added.
* Configuration files for Fedora 23 has been removed.
* Even rawhide configs now use best=1.
* when Mock is run directly without consolehelper it now return exit code 2.
* You can pass additional arguments to systemd-nspawn using this config option: `config_opts['nspawn_args'] = []`.
* kojipkgs urls now use https instead of http.
* new plugin [hw_info](Plugin-HwInfo) which prints HW information of builder. This plugin is enabled by default.

There are some bugfixes:

* reflect change of "Rawhide" to "rawhide" in /etc/os-release [RHBZ#1409735](https://bugzilla.redhat.com/show_bug.cgi?id=1409735)
* in site-defaults.cfg is more examples of how to set up PS1 [RHBZ#1183733](https://bugzilla.redhat.com/show_bug.cgi?id=1183733)
* preserve mode of files when doing chroot_scan [RHBZ#1297430](https://bugzilla.redhat.com/show_bug.cgi?id=1297430)
* shell in systemd-nspawn is run as PID 2 [RHBZ#1372234](https://bugzilla.redhat.com/show_bug.cgi?id=1372234) - this is not done in EL7 version of systemd-nspawn does not support it
* debuginfo repos has been renamed so `mock --dnf-cmd debuginfo-install PACKAGE` works now [RHBZ#1409734](https://bugzilla.redhat.com/show_bug.cgi?id=1409734)

Notes:

* next version will have systemd-nspawn as default. This can break your scripts built on top of Mock. You can try the new behaviour using `--new-chroot` option.
* next version will not be released for EL6. You are advised to upgrade to EL7.
