---
layout: default
title: Release Notes - Mock 5.5
---

Released on 2024-02-14.


### Mock 5.5 New Features

- New `write_tar` option for `chroot_scan` plugin [added][PR#1324].  Without it,
  directory structure is created in `resultdir`.  If `write_tar` is set to
  `True`, `chroot_scan.tar.gz` tarball will be created instead.

- A new `{{ repo_arch }}` Jinja2 template (templated-dictionary) is provided
  by Mock.  This variable is usable for DNF config options denoting URLs like
  `baseurl=`, `metalink=`, etc.  Namely, it can be used instead of the DNF-native
  `$basearch` variable which [doesn't work properly for all the
  distributions][issue#1304].  The new `config_opts['repo_arch_map']` option has
  been added too, if additional tweaks with `repo_arch` template need to be done.

- Previously, only the file sizes were reported by the hw_info plugin:

  ~~~
  Filesystem                                             Size  Used Avail Use% Mounted on
  /dev/mapper/luks-3aa4fbe3-5a19-4025-b70c-1d3038b76bd4  399G  9.1G  373G   3% /
  /dev/mapper/luks-3aa4fbe3-5a19-4025-b70c-1d3038b76bd4  399G  9.1G  373G   3% /
  ~~~

  Newly, [also file system type is reported][issue#1263]:

  ~~~
  Filesystem                                             Type   Size  Used Avail Use% Mounted on
  /dev/mapper/luks-3aa4fbe3-5a19-4025-b70c-1d3038b76bd4  btrfs  399G  9.1G  373G   3% /
  /dev/mapper/luks-3aa4fbe3-5a19-4025-b70c-1d3038b76bd4  btrfs  399G  9.1G  373G   3% /
  ~~~


### Mock 5.5 Bugfixes

- The Bash completion script has been fixed to properly complete arguments
  of [multi-arg options][issue#1279] like `--install` or `--chain`.  This
  bug-fix is a follow-up for fix related to [issue#746][].

- Mock [has been][PR#1322] [fixed][commit#27dde5da] so that it no longer
  inadvertently changes the group ownership of the in-chroot $HOME directory
  to the wrong group ID.  In previous versions of Mock, the group ownership
  was changed to the effective group ID of the user on the host that
  executed Mock.  This could confuse some tools during the build process, as
  they might want to create similarly owned files at the `rpmbuild` time
  (but that assumption would be incorrect, such GID doesn't exist
  in-chroot).  Now, Mock changes the files to the `mockbuild:mock`
  ownership, where the `mock` group ID is always 135 (the same GID on host
  and in-chroot).  This matches the effective GID for the `rpmbuild`
  process, ensuring that the tools executed during the build process have
  full control over such files.

  While on this, Mock was also [optimized][commit#db64d468202] to do this
  ownership change before, and only if, the `rpmbuild` process is started
  (so e.g. plain `mock --chroot` commands do not touch the file ownership at
  all).

- The `mock` package has been fixed to depend on precisely the same version
  of `mock-filesystem` sub-package (product of the same rpm build).  This is
  to protect against incompatible Mock sub-package installations.

- Mock parses the DNF configuration specified in `config_opts["dnf.conf"]` itself
  to perform some post-processing tasks, such as bind-mounting the on-host repo
  directories into the bootstrap chroot based on this DNF config.  In previous
  versions of Mock, there was an issue where it failed to parse the DNF config if
  some of the DNF options contained the '%' symbol.  This was due to Python's
  ConfigParser raising an %-interpolation exception that was ignored but Mock, but
  resulting in Mock ignoring the rest of the config file and finishing without
  performing the mentioned bind-mounts.  This bug has been fixed, and the '%' sign
  is no longer considered to be a special Python ConfigParser character.

- The `root_cache` plugin is designed to invalidate the cache tarball whenever the
  corresponding Mock configuration changes (any file in the list
  `config_opts['config_paths']` changes).  This cache invalidation mechanism had
  been broken since Mock v3.2 when we rewrote the configuration file loader and
  inadvertently broke the `config_opts['config_paths']`.  The config loader [has
  now been fixed][PR#1322], and the cache invalidation works again as expected.

### Mock Core Configs 40.1 changes

- Configuration files for Fedora 40 have been branched from Rawhide,
  according to the [Fedora 40 Schedule](https://fedorapeople.org/groups/schedule/f-40/f-40-all-tasks.html).

- Mageia 7 configs [marked as end-of-life][PR#1316].

- Mageia config files started using the `{{ repo_arch }}` option to fix the
  [cross-arch builds][issue#1317].

- The OpenMandriva i686 chroots [have been marked as end-of-life][PR#1315], fixing
  [issue#987][] and [issue#1012][].

- [Added][PR#1283] a config option called "use_host_shadow_utils", to account for situations where
  users have host shadow-utils configurations that cannot provision or destroy users and
  groups in the buildroot; one example of this kind of configuration is using
  FreeIPA-provided subids on the buildhost. The option defaults to True since mock has made a conscious
  design decision to prefer using the host's shadow-utils, and we hope that this is a
  temporary workaround. Upstream issue is being tracked [here](https://github.com/shadow-maint/shadow/issues/897).

**Following contributors contributed to this release:**

 * Jakub Kadlcik
 * Jani Välimaa
 * Martin Jackson
 * Tomas Kopecek
 * Vít Ondruch


Thank you!

[commit#db64d468202]: https://github.com/rpm-software-management/mock/commit/db64d468202
[issue#1012]: https://github.com/rpm-software-management/mock/issues/1012
[commit#27dde5da]: https://github.com/rpm-software-management/mock/commit/27dde5da
[PR#1324]: https://github.com/rpm-software-management/mock/pull/1324
[PR#1322]: https://github.com/rpm-software-management/mock/pull/1322
[issue#987]: https://github.com/rpm-software-management/mock/issues/987
[PR#1315]: https://github.com/rpm-software-management/mock/pull/1315
[PR#1283]: https://github.com/rpm-software-management/mock/pull/1283
[issue#1263]: https://github.com/rpm-software-management/mock/issues/1263
[issue#746]: https://github.com/rpm-software-management/mock/issues/746
[issue#1317]: https://github.com/rpm-software-management/mock/issues/1317
[issue#1304]: https://github.com/rpm-software-management/mock/issues/1304
[issue#1279]: https://github.com/rpm-software-management/mock/issues/1279
[PR#1316]: https://github.com/rpm-software-management/mock/pull/1316
