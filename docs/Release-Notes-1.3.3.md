---
layout: default
title: Release Notes 1.3.3
---

There are new features:

* All chroot (but rawhide) configs now contains `best=1`. This way DNF will always try to install latest package.
  If its dependence cannot be satisfied DNF will report an error. Without this DNF may silently install some older
  version which does not have broken deps.
  This is fine for regular user, but not for buildsystems, where maintainers usually want to
  use latest version.
  Note that this change may result in sudden build failure, which previously silently succedded.
  In this case, please check your BuildRequires and ask maintainers of those build deps to resolve broken dependency.
  This option was not added to rawhide chroots as there are broken dependencied very often.
  Additionaly option `best=1` is used for repos passed to mockchain using `-a` option.
* new config for epel-7-aarch64 chroot
* You can use new variable `hostname`: `config_opts['hostname'] = 'my.own.hostname'`
  This unconditionally calls `sethostname()`, however
  variable `use_container_host_hostname` or `%_buildhost` macro can override this (on F25+).
* Use DNF on RHEL, when it is installed and configured [RHBZ#1405783](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1405783)
* Temporary directories now use `tmp.mock.` prefix.
* Temporary directories are now removed even when buildroot is not cleaned.
* Add bash completion for .cfg files outside /etc/mock [#20](https://github.com/rpm-software-management/mock/pull/20)

There are some bugfixes:

* Handle working directories which contains spaces [RHBZ#1389663](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1389663)
* Error: is not iterable [RHBZ#1387895](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1387895)
* Delay mounting of user-defined mountpoints [RHBZ#1386544](http://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1386544)
* Added example how to use `more_buildreqs` when you need more packages
* Added example how to use `--plugin-option`
