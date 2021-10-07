---
layout: default
title: Release Notes 2.7
---

Released on - 2020-12-01.

## Mock 2.7 new features:

 * [External (non-RPM) build requires](Feature-external-deps) proof of concept introduced. Initially,
   there's only a support for PyPI and Crates packages.  Any feedback and
   patches (e.g. for other software providers) are welcome! It is disabled by default. It can be enabled using:

```
config_opts['external_buildrequires'] = True
```

   and then you can use in SPEC files:

```
BuildRequires: external:pypi:foo
```

   For more details see [feature page](Feature-external-deps).



 * There's a new plugin for pre-processing the input spec files; so the input
   spec file "templates" are instantiated right before the source RPM build is
   started.  See the [plugin documentation](Plugin-rpkg-preprocessor) for more
   info.

 * The full mock's NAME-VERSION-RELEASE string is now dumped to the log files,
   it is now easier to understand what precise Mock version was used during
   particular package build.

 * Added a new `postupdate` plugin hook; newly the Mock plugins can implement
   the automatic "snapshoting" of the buildroot after any package update inside
   chroot.  This was now used by `root_cache` and `lvm_root` plugins and they
   now newly udpate the buildroot cache after `dnf update` ([rhbz#1175346]).

 * Mock automatically copies the Katello CA pem file for the local Satellite
   server into bootstrap chroot, if such CA is configured on host ([issue#638]).

## Mock 2.7 bugfixes:

 * The `config_opts['resultdir']` path can contain `%`-sign, previous versions
   of Mock failed on processing such configuration ([issue#639]).

 * The `--addrepo <baseurl>` option newly doesn't fail the mock build when the
   `<baseurl>` directory doesn't exist.  This unifies the behavior of that
   option because other errors/typos in the `--addrepo` option are ignored as
   well.

 * Mock doesn't always traceback if the `rpmbuild` process exists with exit code
   11.  That exit code only means that there are still some missing "dynamic
    Buildrequires" (`%generate_buildrequires`) to be installed by Mock
    ([issue#560]).  We also enhanced the build.log output a bit so it is more
    obvious what Mock installs on demand.

  * The bare `mock --shell` (login shell execution) was fixed so it doesn't call
    `setsid()` prior executing the shell itself.  This fixes the shell warning
    message `Inappropriate ioctl for device`.

  * The `sign` plugin now treats the non-zero exit code from the configured
    auto-sign command (usually some `rpmsign` wrapper).  Previous versions of
    Mock just ignored the failure ([koji#2570]).

  * Strange failure on RHEL 8 s390x issue fixed by removing one (probably
    invalid) logging call from `preexec_fn`, but the [PR#653] still needs
    proper fix (help is welcome).

The following contributors contributed to this release:

  * Dominik Turecek
  * Jiri Konecny
  * Markus Linnala
  * Merlin Mathesius
  * Michal Novotný
  * Miroslav Suchý

Thank you!

[rhbz#1175346]: https://bugzilla.redhat.com/1175346
[issue#560]: https://github.com/rpm-software-management/mock/issues/650
[issue#639]: https://github.com/rpm-software-management/mock/issues/639
[PR#653]: https://github.com/rpm-software-management/mock/pull/653
[issue#638]: https://github.com/rpm-software-management/mock/issues/638
[koji#2570]: https://pagure.io/koji/issue/2570
