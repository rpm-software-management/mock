---
layout: default
title: Release Notes - Mock core configs 43.4
---

## [Release 43.4](https://rpm-software-management.github.io/mock/Release-Notes-43.4) - 2026-01-12


### Mock Core Configs changes

- The bootstrap chroot feature has been disabled for fedora-riscv64 chroots, as it is not currently
  functional on this architecture. 
- Fix aarch64 configuration for Azure Linux 3 (copy & paste error). 
- The EOL configuration for epel-6 has been updated with a bug fix for CA
  certificate trust, ensuring the chroot trusts the same set of CAs as the host. 
- Added RISC-V 64-bit architecture support with new configuration files for
  Fedora 42 and 43. The configs use the RISC-V Koji infrastructure at
  `riscv-koji.fedoraproject.org`.
