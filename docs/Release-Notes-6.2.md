---
layout: default
title: Release Notes - Mock 6.2
---

## [Release 6.2](https://rpm-software-management.github.io/mock/Release-Notes-6.2) - 2025-05-22


### New features

- Disables copying /etc/pki/ca-trust and /usr/share/pki/ca-trust-source on
  Azure Linux 3.0 via a new config options ('ssl_copied_ca_trust_dirs').
  This avoids file ownership conflicts with a symlink installed by the
  ca-certificates-shared packages on that distro.  Behavior should be unchanged
  for other configurations.

### Bugfixes

- Mock will now fall back smoothly to chroot installation by DNF if Podman
  image pull fails entirely.


### Mock Core Configs changes

- Mock chroots for RHEL 10 and RHEL+EPEL 10 have been added.

- Fedora 40 is now
  [EOL](https://fedorapeople.org/groups/schedule/f-40/f-40-key-tasks.html), and
  we marked Fedora 40 configuration EOL, too.

- The EPEL 10 configuration has been updated to have separate templates
  available for use on CentOS Stream 10 (epel-10.tpl) and RHEL 10
  (epel-z-10.tpl).  Relates to [issue#1427][].

- Update the list of packages installed by default in the Azure Linux 2 & 3
  chroot to include shadow-utils.  Due to recent changes, the useradd/groupadd
  commands are required by other packages in the list, but the requirements are
  not specified correctly.  Add %dist macro to the Azure Linux 3 template.

- The openSuse Leap 15.6 is now correctly using a bootstrap image of Leap 15.6.
  The Leap configurations now refer to bootstrap images using the $releasever
  value, instead of hardcoding, to avoid potential misalignment in the future.


#### The following contributors have contributed to this release:

- Adam Williamson
- Carl George
- Reuben Olinsky
- Simone Caronni

Thank You!

[issue#1427]: https://github.com/rpm-software-management/mock/issues/1427
