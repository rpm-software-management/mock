---
layout: default
title: Release Notes - Mock 6.1
---

## [Release 6.1](https://rpm-software-management.github.io/mock/Release-Notes-6.1) - 2025-02-27


### New features

- The buildroot lockfile generator [has been modified][PR#1548] to include
  additional bootstrap image metadata that can be later used for a precise image
  pulling.

  The mock-hermetic-repo script has also been modified, to respect the additional
  metadata.  This allows us to, e.g., download bootstrap image of a different
  (cross) architecture then the platform/host architecture is.  In turn, the
  script is now fully arch-agnostic (any host arch may be used for downloading
  files from any arch specific lockfile). 


### Bugfixes

- Previous versions of Mock did not install local RPMs (specified as filenames)
  via --additional-package when bootstrap was enabled (default).  This bug has
  been fixed.  [issue#1532][]. 


### Mock Core Configs 43.1 changes

- Add AlmaLinux Kitten 10 configs to enable building packages for AlmaLinux Kitten 10. 
- Add AlmaLinux Kitten 10 + EPEL 10 configs to enable building packages for EPEL 10 using AlmaLinux Kitten 10 as a base. 
- Add Azure Linux 2.0 configuration (x68_64, aarch64). The distribution changed name mid lifecycle, it was originally called "CBL Mariner 2.0", replacing "Common Base Linux 1.0". That's why the distribution tag is still "cm2" and has "mariner" references in the repository. 
- Add Azure Linux 3.0 configuration (x86_64, aarch64). 
- EuroLinux is end-of-life now, so we [EOLed][issue#1537] also the corresponding Mock configuration. 
- Add Kylin 10 mock configuration files (x86_64, aarch64, loongarch64). 
- Navy Linux 8 configuration [fixed][issue#1538] 
- Bugfix: upgrade openeuler chroots to latest release and fix gpg check failed in 20.03 for issue#1539 
- Add openSUSE Leap 15.6 configurations [issue#1516][]
  Move openSUSE Leap 15.5 configurations to eol (since 31st December 2024) [issue#1516][] 
- Expand Oracle Linux distro_id from `ol` to `oraclelinux` when looking for configuration files [issue#1545]

#### The following contributors have contributed to this release:
                                                                                                                                                                                             
- Evan Goode
- cheese1
- Pavel Raiskup

and to release of configs:

- Adil Hussain
- Avi Miller
- Li Chaoran
- Miroslav Suchý
- Neal Gompa
- Pavel Raiskup
- Simone Caronni

Thank You!



[issue#1516]: https://github.com/rpm-software-management/mock/issues/1516
[issue#1545]: https://github.com/rpm-software-management/mock/issues/1545
[issue#1537]: https://github.com/rpm-software-management/mock/issues/1537
[issue#1532]: https://github.com/rpm-software-management/mock/issues/1532
[issue#1538]: https://github.com/rpm-software-management/mock/issues/1538
[PR#1548]: https://github.com/rpm-software-management/mock/pull/1548
