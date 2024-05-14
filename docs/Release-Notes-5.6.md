---
layout: default
title: Release Notes - Mock 5.6
---

## [Release 5.6](https://rpm-software-management.github.io/mock/Release-Notes-5.6) - 2024-05-14


### New features

- The Bash completion script for Mock has been improved to pre-compile the list of
  available Mock options at package build-time.  This enhancement significantly
  reduces the time required for option completion from approximately 0.5 seconds
  (on a reasonably fast laptop) to just 0.05 seconds. [rhbz#2259430][].


### Bugfixes

- When a `mock --chain --recurse` fails to built at least one package, it is
  unable to print a list of failed packages and displays `AttributeError: type
  object 'FileDownloader' has no attribute 'backmap'` instead. The `original_name`
  method of `FileDownloader` class has been fixed, and the chain build results
  displayed as expected ([issue#1345][]).
- Don't use the `--allowerasing` parameter for DNF subcommands such as
  `repoquery`, `makecache`, `search`, and `info`.
- A missing bash completion script for `mock-parse-buildlog` command [has
  been added][PR#1353].
- In the [issue#1257][] it was suggested that we do not change recursively
  ownership every run. This was implemented and landed in Mock 5.5.
  But in the [issue#1364][] we found that for fresh chroots the homedir
  is not writable for unpriv user.
  We changed the behaviour that ownership of homedir is changed always (that was
  a behaviour prior 5.5 release) and the ownership is changed recursively only for
  rebuilds.
- The `nosync` logic was preparing temporary directories even when
  `config_opts["nosync"] = False` (meaning nosync was disabled).  This logic has
  been optimized out.  Works around [issue#1351][].
- No more ugly tracebacks for "no space left on device" (and similar
  `OSError`s) related to copying built artifacts to `--resultdir`,
  [rhbz#2261758][].
- The SCM plugin's option `git_timestamps` has been updated to work with Python 3
  and to handle Git repositories with non-Unicode data. ([PR#1355][])


### Mock Core Configs changes

- Add configuration for Circle Linux 9 configurations ([PR#1366][]).
- Add i686 configuration for Mageia Cauldron and Mageia 10, and remove
  corresponding i586 configurations ([PR#1360][]).
- The Fedora ELN configuration [has been updated to use DNF5 for Mock chroot
  package management][issue#1292].


#### Following contributors contributed to this release:

- Bella Zhang
- David Michael
- Evan Goode
- Felix Krull
- Jakub Kadlcik
- Jani Välimaa
- Martin Jackson
- Michael Rochefort
- Miro Hrončok
- Miroslav Suchý
- Neal Gompa
- Nikita Gerasimov
- Orion Poplawski
- Pavel Raiskup
- Sandro Bonazzola
- Stephen Gallagher
- Stewart Smith
- Takuya Wakazono
- Tomas Kopecek
- Vít Ondruch
- Yu Ming Zhu
- zengchen1024
- zengwei2000

[rhbz#2259430]: https://bugzilla.redhat.com/2259430
[issue#1292]: https://github.com/rpm-software-management/mock/issues/1292
[issue#1345]: https://github.com/rpm-software-management/mock/issues/1345
[issue#1351]: https://github.com/rpm-software-management/mock/issues/1351
[issue#1364]: https://github.com/rpm-software-management/mock/issues/1364
[PR#1366]: https://github.com/rpm-software-management/mock/pull/1366
[PR#1353]: https://github.com/rpm-software-management/mock/pull/1353
[issue#1257]: https://github.com/rpm-software-management/mock/issues/1257
[PR#1355]: https://github.com/rpm-software-management/mock/pull/1355
[PR#1360]: https://github.com/rpm-software-management/mock/pull/1360
[rhbz#2261758]: https://bugzilla.redhat.com/2261758
