---
layout: default
title: Release Notes 2.13
---

Released on - 2021-11-02


## New Mock 2.13 features:

* A new option `--additional-package` is added.  During package
  development, this option can be used with `mock --rebuild` mode to specify
  an additional set of build requirements (still, properly setting
  `BuildRequires:` is a preferred way to achieve this) [[PR 776][PR#776]].

* A new option `--debug-config-expanded` is now available.  It provides a very
  similar mock configuration output to the `--debug-config` option, except that
  the `{{ Jinja }}` constructs the configuration are expanded
  [[PR 765][PR#765]].

## Mock 2.13 bugfixes:

* The [`external:` dependencies](Feature-external-deps) are now properly
  installed into a proper build chroot, not into a bootstrap chroot
  [[PR 771][PR#771]].

* The option parsing mechanism was migrated from the `optparse` library to
  `argparse`.  This in particular shouldn't be a user visible change, so please
  report changes in mock behavior if you observe any.

* The repositories generated locally by mock are not automatically signed.  But
  since Mock did not specify the default `gpgpcheck=` option before, and some of
  our config files didn't have `gpgcheck=0` in the `[main]` section,
  DNF applied its own `gpgcheck=1` default and it led to `mock --chain` build
  failures.  Newly we set `gpgcheck=0` by default by Mock and any GPG signed
  repository used in mock configuration needs to overwrite this explicitly
  [[PR 782][PR#782]].

* When re-mounting, we newly don't specify the source of the mountpoint as it is
  not needed in our case, and because the other (preferred) `mount --target ...`
  variant is more portable (behaves correctly with older `util-linux`
  implementations). [[issue 715][issue#715]]

* The `distro.linux_distribution()` call is now deprecated, we use
  `distro.id()` instead.  [[PR 767][PR#767]]

* Fixed LVM error message caused by copy/paste error [[PR 758][PR#758]].


The following contributors contributed to this release:

 * Gustavo Costa
 * Kamil Dudka
 * Miroslav Suchý
 * Sérgio M. Basto

Thank you!

[PR#758]: https://github.com/rpm-software-management/mock/pull/758
[PR#765]: https://github.com/rpm-software-management/mock/pull/765
[PR#767]: https://github.com/rpm-software-management/mock/pull/767
[PR#776]: https://github.com/rpm-software-management/mock/pull/776
[PR#782]: https://github.com/rpm-software-management/mock/pull/782
[PR#771]: https://github.com/rpm-software-management/mock/pull/771
[issue#715]: https://github.com/rpm-software-management/mock/issues/715
