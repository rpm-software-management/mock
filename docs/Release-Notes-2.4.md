---
layout: default
title: Release Notes 2.4
---

Released on - 2020-07-21.

## Mock 2.4 features:

 * The file `/dev/btrfs-control` is now available in chroot if host supports it.
   This allows to create btrfs-based image builds. [[fedora-infra#9138](https://pagure.io/fedora-infrastructure/issue/9138)].

 * Copy source CA certificates -
   Prior to this change, we would only copy the "extracted" SSL CA
   certificates into the chroot. If anything ran "update-ca-trust" inside
   the chroot, this would delete our custom SSL certificates from the
   "extracted" directory. For example, Fedora and RHEL's main
   "ca-certificates" package always does this in %post, and any custom
   third-party package could do this as well.
   Copy the entire parent directory so that "sources" and "extracted" are
   both present in the chroot. With this change, "update-ca-trust"
   does not wipe out the CA certificates from the chroot. [[#588](../issues/588)]

 * Add `module_setup_commands` configuration option, The new config option
   obsoletes `module_enable` and `module_install` configuration options (but
   those are still supported), and allows users to also configure "disable",
   "remove" and other commands.

   Each command can be specified multiple times, and mock respects the
   order of the commands when executing them.

   Artificial example: (1) Disable any potentially enabled postgresql module
   stream, (2) enable _specific_ postgresql and ruby module streams,
   (3) install the development nodejs profile and (4) disable it immediately.

```
    config_opts['module_setup_commands'] = [
        ('disable', 'postgresql'),
        ('enable',  'postgresql:12, ruby:2.6'),
        ('install', 'nodejs:13/development'),
        ('disable', 'nodejs'),
        ]
```

## Mock 2.4 bugfixes:

 * `.rpmmacros` is now created in "rootdir" instead of "basedir"
   [[rhbz#1848201](https://bugzilla.redhat.com/1848201)]

Following contributors contributed to this release:

 * Ken Dreyer
 * Neal Gompa
 * Pavel Raiskup

Thank you.
