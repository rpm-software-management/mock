---
layout: default
title: Release Notes 1.4.17
---

Released on 2019-08-08.

## Mock-core-configs new features:

 * Added updates-modular to Fedora 29 and Fedora 30, but with `enabled=0` for now due
   [bug in DNF](https://bugzilla.redhat.com/show_bug.cgi?id=1737469).
 * Removed info about metadata expire.
 * Replace groupadd using sysusers.d.
 * epel-7 profiles to use mirrorlists.
 * EOLed Fedora 28.
 * Do not protect packages in chroot [[GH#286]](https://github.com/rpm-software-management/mock/pull/286).
 * Fix value for dist for OpenMandriva 4.0 configs.
 * Add initial OpenMandriva distribution targets.

## Mock new features and bugfixes:

 * Mockchain has been replaced by `mock --chain`. This new command inherited most
   mockchain command-line options. The [return codes](https://github.com/rpm-software-management/mock/blob/master/mock/py/mockbuild/exception.py#L26) are little different.
   This has been done to remove duality - mockchain parsed configs differently than mock.
   Now, the behavior should be unified. Mockchain has been marked obsolete - it even prints warning
   when you execute, and you are encouraged to migrate to `mock --chain`. I will try to preserve `mockchain` for next
   12 months, but mockchain will not be receiving any new functionality.
 * Mock is now able to run in [Fedora Toolbox](https://docs.fedoraproject.org/en-US/fedora-silverblue/toolbox/).
 * Added support for [Cheat](https://github.com/cheat/cheat) - try running `cheat mock`.
 * There is a new tool `mock-parse-buildlog --path FILE` which tries to parse build.log file and give you nice
   human friendly description, why the build failed. Right now, it support just two use cases. Feel free to
   send pull request to enhance it.
 * Secondary groups are now loaded [[RHBZ#1264005]](https://bugzilla.redhat.com/show_bug.cgi?id=1264005).
 * When installing dependencies, Mock pass --allowerasing to DNF now. [[GH#251]](https://github.com/rpm-software-management/mock/pull/251).
 * make include() functional for --chain [[GH#263]](https://github.com/rpm-software-management/mock/pull/263).
 * Removing BUILDSTDERR from log - it is now configurable via `config_opts['_mock_stderr_line_prefix`]', which is by default empty string.
 * Use rpm -qa --root instead of running rpm -qa in chroot.
 * Run more that one loop for DynamicBuildrequires if it is neeed.
 * Number of loop devices is now configurable using `config_opts['dev_loop_count'] = 12` and the new default has been raised from 4 to 12. This change only affects `--old-chroot`. We are working on making it functional in nspawn chroot as well.
 * Return back to call binaries using /bin for split-usr setups.
 * Repeat [dynamic requires](https://fedoraproject.org/wiki/Changes/DynamicBuildRequires) loop if needed [[GH#276]](https://github.com/rpm-software-management/mock/pull/276)
 * Fix compatibility with pre-4.15 RPM versions with DynamicBuildRequires.
 * Enable [Dynamic BuildRequires](https://fedoraproject.org/wiki/Changes/DynamicBuildRequires) by default.
 * Independent network configuration [[GH269]](https://github.com/rpm-software-management/mock/pull/269)
 * Now, when you execute `mock -r FOO`, mock will check if `~/.config/mock/FOO.cfg` exists and use this config. If it does not exists, it will use the `/etc/mock/FOO.cfg`. This is useful if you want to localy override default configs.
 * respect use_host_resolv config even with use_nspawn.
 * Fix crash on non-ascii dnf log messages.
 * switch to python3 on el7 (msuchy@redhat.com)

## Future

Note that in upcoming versions, I would like to:

 * drop python2 support as even EL7 version is running on python3 now.
 * drop EL7 support (likely spring 2020). I mean to stop building Mock for EL7. Building packages for EL7 using Mock will be still supported.
 * make DNF default package manager. E.g., you will have to state in config that you want to use yum explicitly.
 * Pavel Raiskup is preparing support for building for RHEL 8 targets. So besides traditional CentOS targets, you will be able to build for RHEL, if you have Red Hat subscription. This will allows you to not wait for CentOS release when RHEL has already been released.

Following contributors contributed to this release:

 * Barak Korren
 * Bernhard Rosenkränzer
 * Igor Gnatenko
 * khoitd1997
 * Martin Necas
 * Miro Hrončok
 * Neal Gompa
 * Owen W. Taylor
 * Pavel Raiskup
 * Silvie Chlupova

Thank you.
