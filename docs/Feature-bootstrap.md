---
layout: default
title: Feature bootstrap
---

## Bootstrap chroot

Mock is calling `dnf --installroot` to install packages for target architecture into the target directory. This works. Mostly. The only problem that use host DNF and rpm to install packages. But this can cause a problem when a new RPM feature is introduced. Like Soft dependencies or Rich dependencies. When you have EL6 host and try to install Fedora rawhide package with Rich dependency then rpm will fail and you cannot do anything about it. You can upgrade your build machine to Fedora rawhide, but that is often not possible when it is part of critical infrastructure.

So we introduced Boostrap chroot. And 'we' actually means Michael Cullen who implements it. And Igor Gnatenko who proposed this idea. Big kudos for both of them.

Bootstrap chroot means that we first create very minimal chroot for the target platform and we call DNF/YUM from that platform. For example: when you are on RHEL7 and you want to build a package for `fedora-26-x86_64`, mock will first create chroot called `fedora-26-x86_64-bootstrap`, it will install DNF and rpm there (fc26 versions). Then it will call DNF from `fedora-26-x86_64-bootstrap` to install all needed packages to `fedora-26-x86_64` chroot.

The disadvantage is that you will need more storage in `/var/lib/mock`, the build is a little bit slower. But you will hardly notice that unless you disabled `yum_cache` and `root_cache` plugins for some reasons.

The advantage is that you can use a stable version of OS to build packages for even most recent OS. And vice versa.

This feature is enabled by default. If you want to disable it you should set:

```
    config_opts['use_bootstrap'] = False
```

in your configuration.

This has been added in Mock 1.4.1.

### Using bootstrap with local repositories

It is possible to use `file://` local repositories with boostrap chroot. However, you should not bind mount repositories located in `/tmp`, `/dev`, etc., as they might be over-mounted by systemd-nspawn.
