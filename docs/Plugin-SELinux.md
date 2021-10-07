---
layout: default
title: Plugin SELinux
---

On SELinux enabled box, this plugin will pretend, that SELinux is disabled in build environment.

* fake /proc/filesystems is mounted into build environment, excluding selinuxfs
* option `--setopt=tsflags=nocontext` is appended to each 'yum' command

This plugin is enabled by default and there is actually no way to disable it.

This plugin is not used with NSPAWN chroot (`--new-chroot` option) and will be removed when NSPAWN chroot will be only one option.
