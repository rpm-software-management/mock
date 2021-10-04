---
layout: default
title: Feature nosync
---
# Nosync

One of the reasons why mock has always been quite slow is because installing a lot of packages generates a heavy IO load. But the main bottleneck regarding IO is not unpacking files from packages to disk but writing Yum DB entries. Yum DB access (used by both yum and dnf) generates a lot of `fsync`(2) calls. Those don't really make sense in mock because people generally don't try to recover mock buildroots after hardware failure. We discovered that getting rid of `fsync` improves the package installation speed by almost a factor of 4. Mikolaj Izdebski developed a small C library, `nosync`, that is `LD_PRELOAD`ed and replaces the `fsync` family of calls with (almost) empty implementations. I added support for it in mock.
How to activate it?
You need to install the `nosync` package and for multilib systems (`x86_64`), you need versions for both architectures. Then it can be enabled in mock by setting
```
# dnf install nosync
config_opts['nosync'] = True
```
If you cannot install both architectures of nosync (for example on RHEL) and still want mock to use it, you can force its usage. Then expect there can be harmless error messages from ld.so when a 32bit program is executed, but it should otherwise work fine for 64bit binaries. Forcing is done using
```
config_opts['nosync_force'] = True
```

It does require those extra steps to set up but it really pays off quickly.

