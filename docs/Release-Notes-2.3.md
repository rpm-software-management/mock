---
layout: default
title: Release Notes 2.3
---

Released on 2020-05-22.

## Mock 2.3 bugfixes:

 * The `--resultdir RESULTDIR` directory is bind-mounted to bootstrap chroot, so
   we can use `--postinstalll` even with `--bootstrap-chroot`,
   [#564](../issues/564),

 * easier configuration for `mount` plugin, [#578](../issues/578),

 * mock raises better error message when `%prep` script fails during
   dynamic_biuldrequires resolution, [#570](../issues/570),

 * local mirrorlists are correctly bind-mounted to bootstrap chroot,
   [RHBZ#1816696](https://bugzilla.redhat.com/1816696),

 * traceback for invalid `getresuid()` call, [#571](../issues/571),

 * use-cases with `--rootdir` and `--bootstrap-chroot` were fixed, [#560](../issues/560),

 * use bootstrap (not host's) `/bin/rpm` when producing list of installed packages,
   [PR#568](../pulls/568), (pmatilai@redhat.com),

 * braced dnf variables are now expanded in repo URLs,
   [PR#577](../pulls/577), (dmarshall@gmail.com).

Following contributors contributed to this release:

 * David Marshall
 * Neal Gompa
 * Panu Matilainen

Thank you.
