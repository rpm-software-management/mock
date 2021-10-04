---
layout: default
title: Release Notes 2.9
---

Released on - 2021-01-18.

## Mock 2.9 new features:

 * The `rpkg_preprocessor` plugin got new `force_enable` option.  This option
   tells rpkg_preprocessor to ignore rpkg.conf and always preprocess the spec
   file.  This is useful for testing mass package changes where it's not
   practical to add an rpkg.conf to every package.

 * The configuration mechanism was cut-out from mock, and is now newly provided
   as new package `python3-templated-dictionary` that mock package depends on.

## Mock-core-configs v33.5 fixes:

 * EPEL 6 configuration was marked EOL (moved to eol/ subdirectory).

 * Fedora 31 configuration is EOL, too.

 * Fixed bootstrap of Fedora on Enterprise Linux 7 boxes.

 * Bootstrap images defined for OpenSUSE Tumbleweed.

 * RepoIDs renamed for EL8 chroots, according to real repoIDs in normal repo
   files.

The following contributors contributed to this release:

 * Miroslav Suchý
 * Neal Gompa
 * Tom Stellard

Thank you!
