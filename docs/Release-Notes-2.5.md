---
layout: default
title: Release Notes 2.5
---

Released on - 2020-09-03.

## Mock 2.5 features:

 * Since the introduction of `mock-configs` virtual provides, it can
   happen that `mock-core-configs` is not actually installed.  Previously,
   the `mock` group would be missing though on such installation because
   it was installed by the `mock-core-configs` package.  Newly, both
   `mock` and `mock-core-configs` depend on the new `mock-filesystem`
   package that is responsible for installing both the `mock` system group
   and some basic directory layout.

 * Mock newly configures the DNF so it sets a custom HTTP User Agent
   header when downloading packages.  This information can be later used
   for better download statistics (e.g.normal end-user package downloads
   vs. build-system downloads).

 * A new [showrc plugin](https://rpm-software-management.github.io/mock//Plugin-Showrc) was added.  It puts the output of the command
   `rpm --showrc` into a separate log file in result directory so users may
   e.g. use this info during debugging the macro definition peculiarities.


## Mock 2.5 bugfixes:

 * Previously, when macro wasn't specified with leading `%` (see the
   difference between `config_opts['macros']['foo'] = 'baz'` vs.
   `config_opts['macros']['%foo'] = 'baz'`), mock on newer systems
   (with new-enough Python 3.8+) failed hard with not really helpful
   error.  This has been fixed (issue#605).

## Mock-core-configs v33 changes:

 * New Fedora ELN config files are provided.

 * Some adjustments were done for the new mock-filesystem package.


Following contributors contributed to this release:

 * Miroslav Suchý
 * Pat Riehecky

Thank you.
