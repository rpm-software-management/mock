---
layout: default
title: Release Notes - Mock 6.9
---

## [Release 6.9](https://rpm-software-management.github.io/mock/Release-Notes-6.9) - 2026-10-01


### Breaking changes

- Mock now always runs `rpmbuild` with `--noclean` (when supported by
  `rpmbuild`), so the `%clean` section of spec files is never executed, and
  neither is `rpmbuild`'s built-in `rmbuild` step that removes the build tree.
  Mock does its own cleanup of the build directory (and keeping the directory
  around is needed, e.g., for the separate `%check` phase).

  Note this is not really a new behavior.  Mock has been passing `--noclean`
  [since 2022][commit#638e0abf], and it did so for the default configuration
  already — a `resultdir` inside the `basedir` [disables
  `cleanup_on_success`][config-noclean], which is what made Mock pass
  `--noclean`.  That is also the case in Fedora Koji, so Fedora package builds
  have not been running `%clean` for years.  What changes in 6.9 is that a
  `resultdir` placed outside of the `basedir` behaves the same way.

  Spec files that rely on their `%clean` section being performed _in a Mock
  build_ would need to be adjusted — but we believe no such spec files exist in
  practice.  See also [the related devel@ discussion][devel-clean-thread].


### New features

- Add a `%check` test to mock-core-configs that asserts openEuler source
  repositories use the literal `openEuler-<version>` directory in
  `metalink ... path=` URLs rather than the untranslated `$releasever`,
  which the metalink `path=` form does not expand.


### Bugfixes

- Probe if systemd-nspawn has the --restrict-address-families option
  and use it if available. Otherwise, systemd-nspawn will print a warning
  about planned changes to its default behaviour in a future version
  and urge to use said option ([issue#1799][]). This pollutes mock's
  output, breaking other tools, like fedora-review ([rhbz#2511998][]).

- Fix `separate_check` builds with a separate `--resultdir`.  A resultdir
  outside of the chroot directory enables `cleanup_on_success`, and that in turn
  made Mock run `rpmbuild` without `--noclean`.  The `%clean` stage then removed
  the build directory before the separate `%check` phase could run, so
  `rpmbuild -bk --short-circuit` failed with `rpmbuild.env: No such file or
  directory` ([issue#1808][]).  Mock now always runs `rpmbuild` with `--noclean`
  and does its own cleanup, so the build directory survives for the separate
  `%check` phase.

- The `unbreq` plugin reports fewer false positives.  When checking whether all
  the providers of a `BuildRequires` can be removed together, the result of the
  check was ignored and every provider from the previous step was reported as
  unused.  The providers deduplication also checked the length of the
  `BuildRequires` name instead of the length of the list of providers

### Mock Core Configs changes

- The openSUSE Tumbleweed `%dist` macro expands to `.suse.tw<snapshot>` again
  (it had been expanding to just `.suse.tw`), and loading the Tumbleweed config
  no longer prints a Python `SyntaxWarning` ([issue#1785][]).

- The AlmaLinux Kitten + EPEL 10 configs have been updated to use a new 10s
  pattern.  This is related to a minor reconfiguration of EPEL 10 minor version
  repo redirects.  See [this discussion
  thread](https://discussion.fedoraproject.org/t/looking-back-at-epel-10-and-forward-to-epel-11/197373)
  for more details.

- Add Amazon Linux 2027 configuration and mark AL2 eol

- Amazon Linux 2023 has a buildsys-build group that is used to set up the chroot now instead of the enumerated package set.

- The CentOS Stream + EPEL 10 configs have been updated to use a new 10s pattern.
  This is related to a minor reconfiguration of EPEL 10 minor version repo
  redirects.  See [this discussion
  thread](https://discussion.fedoraproject.org/t/looking-back-at-epel-10-and-forward-to-epel-11/197373)
  for more details.

- Add openSUSE Leap 16.1 configurations ([issue#1786][]). openSUSE Leap 16.1 is
  currently in beta; the configurations use the same GPG keys as Leap 16.0.

[issue#1785]: https://github.com/rpm-software-management/mock/issues/1785
[issue#1786]: https://github.com/rpm-software-management/mock/issues/1786
[issue#1808]: https://github.com/rpm-software-management/mock/issues/1808
[rhbz#2511998]: https://bugzilla.redhat.com/2511998
[issue#1799]: https://github.com/rpm-software-management/mock/issues/1799
[commit#638e0abf]: https://github.com/rpm-software-management/mock/commit/638e0abfa05d21171940da734a08b2d4ec497669
[config-noclean]: https://github.com/rpm-software-management/mock/blob/3b308660a12fb59886f438a59561f023d01586d8/mock/py/mockbuild/config.py#L670-L672
[devel-clean-thread]: https://lists.fedoraproject.org/archives/list/devel@lists.fedoraproject.org/thread/257ZJM2NQ6E45ZUIFK2QO5QXZ6W5WZG7/
