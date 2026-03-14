---
layout: default
title: Release Notes - Mock Core Configs 43.5
---

## [Release 43.5](https://rpm-software-management.github.io/mock/Release-Notes-Configs-43.5) - 2026-01-27

### Mock Core Configs changes

- Fedora 41 has reached its [End of Life
  (EOL)](https://fedorapeople.org/groups/schedule/f-41/f-41-key-tasks.html), and
  its mock configurations have been updated accordingly.

- Mageia 10+ and Cauldron now use DNF5 as their default package manager.

- RHEL 10.1 and RHEL 9.7 now utilize Post-Quantum (PQ) GPG keys.  This release
  adds these keys to the RHEL 9 configurations.  However, since other systems
  (even Fedora)cannot yet handle PQ keys, RHEL package installation would fail.
  To make Mock builds work, you must either use a bootstrap-image (the default)
  or run Mock on RHEL 10.1+ / RHEL 9.7+.
