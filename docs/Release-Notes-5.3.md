---
layout: default
title: Release Notes - Mock v5.3
---

Released on 2023-12-13.

### Mock 5.3 new features

- A new plugin to pre-process spec files with rpmautospec [has been
  implemented][PR#1253].

  If this plugin is enabled, mock pre-processes spec files that use rpmautospec
  features (for automatic release numbering and changelog generation) before
  building a source RPM.

- Only run the `%prep` section once when running `%generate_buildrequires`
  multiple times.
  Previously Mock run `%prep` repeatedly before each `%generate_buildrequires`
  round except for the last one.  This was inconsistent and unnecessary
  slow/wasteful.

  When the original support for `%generate_buildrequires` landed into Mock,
  the intention was to only call `%prep` once.
  However when Mock added support for multiple rounds of
  `%generate_buildrequires`, `%prep` ended up only being skipped in the final
  `rpmbuild` call. This was an oversight.  `%prep` is now only called once, as
  originally intended.

  Some RPM packages might be affected by the change, especially if a dirty
  working directory after running `%generate_buildrequires` affects the results
  of subsequent rounds of `%generate_buildrequires`.  However, such behavior was
  undefined and quite buggy even previously, due to the lack of the `%prep`
  section in the final `rpmbuild` call.

  Packages that need to run commands before every round of
  `%generate_buildrequires` should place those commands in the
  `%generate_buildrequires` section itself rather than `%prep`.

- The automatic killing feature for orphan processes within the chroot environment
  [was][PR#1255] [improved][PR#1268] to also provide the user with information
  about the command-line arguments of the terminated process:

  `WARNING: Leftover process 1331205 is being killed with signal 15: daemon --with-arg`

- The info about package management tooling used to install the target buildroot
  has been updated to provide the info earlier, before the buildroot
  installation happens.  Mock newly informs also about dnf5 presence.


### Bugfixes

- The Bash completion bug in Mock for options accepting multiple arguments,
  tracked in the [long-standing issue][issue#746], has been resolved through [PR#1262].

- If DNF 5 sees an "interactive" TTY on stdout, it will try to draw progress bars
  and cause the Mock logs to [be garbled](https://github.com/fedora-copr/copr/issues/3040).
  This release brings a fix that simply sets the output of DNF5 to a pipe instead
  of a PTY.

- When Mock completes the installation of all the requirements generated
  by `%generate_buildrequries`, it calls `rpmbuild -ba` to perform a final build
  of the package.

  During the final build, `%generate_buildrequries` runs again in order to
  generate a list of `BuildRequires` to be added to the built SRPM metadata.
  An arbitrary `%generate_buildrequries` section may generate different
  requirements that may not have been installed.

  Previously, the `rpmbuild -ba` call used the `--nodeps` option,
  hence it was [possible to successfully build a package with
  unsatisfiable BuildRequires in the built SRPM metadata][issue#1246].

  When a bootstrap chroot is used, the `--nodeps` option is
  [no longer used][PR#1249] in the final `rpmbuild -ba` call.
  If `%generate_buildrequries` attempts to generate new unsatisfied requirements
  during the final build, the build will fail.
  When a bootstrap chroot is not used, the `--nodeps` option remains because
  Mock cannot know if the RPM in chroot can read the RPM database.

**Following contributors contributed to this release:**

 * Evan Goode
 * Jakub Kadlcik
 * Miro Hrončok
 * Orion Poplawski
 * Stephen Gallagh

Thank you!

[issue#746]: https://github.com/rpm-software-management/mock/issues/746
[PR#1268]: https://github.com/rpm-software-management/mock/pull/1268
[issue#1246]: https://github.com/rpm-software-management/mock/issues/1246
[PR#1255]: https://github.com/rpm-software-management/mock/pull/1255
[PR#1262]: https://github.com/rpm-software-management/mock/pull/1262
[PR#1249]: https://github.com/rpm-software-management/mock/pull/1249
[PR#1253]: https://github.com/rpm-software-management/mock/pull/1253
