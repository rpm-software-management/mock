---
layout: default
title: Release Notes 1.2.13
---

mock-1.2.13 is bugfix release, but some bugfix may be interesting for you:

* Fedora 23 configs are reverted back to use yum again. To be on pair
with Koji
* Lot of fixes for --new-chroot option
* Mockchain can download SRPM from Dropbox
* DNF does not install weak dependencies by default
* When cleaning up chroots, mock now exclude mountpoints
* When you build using DNF (rawhide) on systems, which does not have DNF (EL6, 7), mock will print warning, wait for confirmation, tell you how to suppress this warning next time. Nevertheless this warning is not fatal and Mock can continue using YUM.
* Previously package_state plugin always used YUM, now it use DNF when chroot is configured to use DNF.
* When file `/usr/bin/yum-deprecated` is present on your machine, then variable `config_opts['yum_command']` is set to this value by default.
* Several others bugfixes﻿
