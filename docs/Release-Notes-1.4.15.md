---
layout: default
title: Release-Notes 1.4.15
---

Released on 2019-04-22.

## Mock new features:

- Mock supports [Dynamic Build Requires](https://fedoraproject.org/wiki/Changes/DynamicBuildRequires). There is still ongoing work in `rpmbuild`; therefore you cannot use it yet. Once the new rpmbuild lands in Fedora you can immediately use it with Mock. [[GH#245](https://github.com/rpm-software-management/mock/issues/245)]

- I have seen people who do not know about [setup](https://rpm-software-management.github.io/mock/#setup). Now, when you are not in the `mock` group, and Mock asks you via `consolehelper` for root password, it prints this banner: `You are not in the `mock` group. See https://github.com/rpm-software-management/mock/wiki#setup` [[GH#244](https://github.com/rpm-software-management/mock/issues/228)]

- Previously when Mock executed DNF, then Mock disabled DNF plugin `local`. Now the list of plugins which will be disabled can be configured via:

```
config_opts['dnf_disable_plugins'] = ['local', 'spacewalk']
```

The above is the new default, i.e., the plugin `spacewalk` is now disabled as well. [[GH#210](https://github.com/rpm-software-management/mock/issues/210)]

This change simplified `dnf_common_opts` default, which is now:

```
config_opts['dnf_common_opts'] = ['--setopt=deltarpm=False']
```

## Bugfixes:

- In Flatpak, the method `distro.version()` returns float, which produced fatal error in Mock. This is now fixed [[RHBZ#1690374](https://bugzilla.redhat.com/show_bug.cgi?id=1690374)]

- new rpm library now returns strings instead of bytes. Mock has been altered that it can accept both types [[RHBZ#1693759](https://bugzilla.redhat.com/show_bug.cgi?id=1693759)]

- Mock used FileNotFoundError class for a error handling. This class is not defined in Python 2 and caused a traceback during an error handling [[RHBZ#1696234](https://bugzilla.redhat.com/show_bug.cgi?id=1696234)]

## Known issues:

- On Fedora 30+, the createrepo_c prints its output to STDERR, which is fatal to mockchain. For the time being, I changed the mockchain behavior and creterepo_c errors are not fatal. However, mockchain print them as an error even there is no error at all. [GH#249](https://github.com/rpm-software-management/mock/issues/249)

Following contributors contributed to this release:

* Igor Gnatenko
* Jeroen van Meeuwen (Kolab Systems)
* Jo Shields
* Martin Kutlák
* Neal Gompa
* Pat Riehecky
* Toshio Kuratomi

Thank you.
