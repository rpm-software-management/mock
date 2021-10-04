---
layout: default
title: Release Notes 1.4.9
---

Released on 2018-02-12.

Note:

In this release, there are several fixes to bootstrap feature. This is especially important for users who run Mock on EL7. Rich dependencies are now allowed in Fedora and maintainers are starting to use them. So sooner or later, you will be unable to build packages for Fedoras on EL7 host. Unless you start using bootstrap feature (`--bootstrap-chroot`), which is still by default off.


Features:
* Stdout and stderr in build.log has been split. All stderr output lines are prefixed by `BUILDSTDERR:`
* There is a new config option `opstimeout`:

```
# Set timeout in seconds for common mock operations
# if 0 is set, then no time limit is used
# config_opts['opstimeout'] = 0
```

The default is 0, which means that Mock is waiting until command exit.

Bugfixes:
* Builds for EL5 are working again - EL5 is sensitive to order of params of adduser [RHBZ#1535328](https://bugzilla.redhat.com/show_bug.cgi?id=1535328)
* Use correct builddep when bootstrap is used. Additionally, ccache is not installed into bootstrap chroot. [RHBZ#1540813](https://bugzilla.redhat.com/show_bug.cgi?id=1540813).
* User defined mounts are not mounted in bootstrap chroot.
* Detect if essential mounts are already mounted - previously, mock assumed that essential mounts (procfs, sysfs) are never mounted when mock starts up. That's not true, as multiple non-destructive mock processes are allowed (`--shell`, `--install`, etc.) to run concurrently. So when you use `mock --shell` and do a `mock --install` in parallel, it breaks your shell, because it unmounts its proc. This improves the situation by first asking whether the mounts aren't there already.
* fix quoting in sign_opts example in site-defaults.cfg [RHBZ#1537797](https://bugzilla.redhat.com/show_bug.cgi?id=1537797).
* Honor the "cwd" flag when nspawn is being used and "chrootPath" is not set.
* Do not produce a warning when we are using different PM for a bootstrap container.
* Default for config_opts['dnf_warning'] in site-defaults.cfg according to docs.

Additionally, there are several major changes in mock-core-config. This package is independent now, and a new version has been released two weeks ago and will be pushed to Fedora stable next week. I will repeat here changes in that package:
* Fedora 28 configs has been added.
* `failovermethod=priority` has been removed for repos which use DNF. This is the only method which DNF recognize and it cannot be changed.
* Set `skip_if_unavailable=False` for all repos. If a repository is unreachable, then build fails.


Following contributors contributed to this release:

* Barak Korren
* Michael Simacek
* Mikhail Campos Guadamuz
* mprahl
* Pavel Raiskup
* Todd Zullinger

Thank you.
