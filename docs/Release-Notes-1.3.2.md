---
layout: default
title: Release Notes 1.3.2
---

This is a release with big changes. Prior to this release there have been version 1.3.1, but it was never actually released. It was just tagged commit and was intended just for developers for testing. This is first public release after big internal changes.

There are those changes:

* move `/usr/sbin/mock` to `/usr/libexec/mock/mock` [RHBZ#1246810](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1246810)
  Previously there were /usr/bin/mock and /usr/sbin/mock. It caused some confusion. Script `/usr/sbin/mock` should not be run directly, but some people (and containers) had /usr/sbin first in their path. So this script is now in `/usr/libexec/`, which are not in `$PATH`. In other word: you can still type "mock" and mock will start. If you ever seen this error
`ERROR: The most common cause for this error is trying to run `/usr/sbin/mock` as an unprivileged user.` then you should not see it anymore.
* F22 configs has been removed
* Just for developers: I removed the automake and it will use Tito now. If you are new to tito, then just:
```bash
    sudo dnf install tito
    tito build --rpm --test -i  # install code from last commit
    tito build --rpm # build latest tagged version
```
  The benefits are that release process is now *much* easier. And there are no more build artefacts directly in git repo.
* `--nocheck` is working again [GH#2](https://github.com/rpm-software-management/mock/issues/2)
* You can now run mock inside of Docker [RHBZ#1336750](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1336750) - however you need to run docker with `-cap-add=SYS_ADMIN`.
* When building for Fedora 25+ target in container, then buildhost is set to name of host and not to name of container. [RHBZ#1302040](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1302040)
  These are the new defaults:
```
## When RPM is build in container then build hostname is set to name of
## container. This sets the build hostname to name of container's host.
## Works only in F25+ chroots
# config_opts['use_container_host_hostname'] = True
## This works in F25+ chroots. This overrides 'use_container_host_hostname' option
# config_opts['macros']['%_buildhost'] = 'my.own.hostname'
```
* There was a lot of flake8/pep8/pycodestyle clean up of code.
