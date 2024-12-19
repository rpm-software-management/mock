---
layout: default
title: Release Notes - Mock 6.0 (+ mock-core-configs v41.5)
---

## [Release 6.0](https://rpm-software-management.github.io/mock/Release-Notes-6.0) - 2024-12-19


### New features

- [A new plugin, `export_buildroot_image`](Plugin-Export-Buildroot-Image), has
  been added.  This plugin can export the generated Mock chroot as an OCI image
  archive once all the build dependencies have been installed (when the chroot
  is fully prepared to run `/bin/rpmbuild -bb`).

  A [new complementary feature](Feature-buildroot-image) has also been
  implemented in Mock and can be enabled using the following option:

      --buildroot-image /tmp/buildroot-oci.tar

  This feature allows the use of generated OCI archives as the source for the
  build chroot, similar to how `bootstrap_image` is used as the base for the
  bootstrap chroot.

  Additionally, this feature can be utilized with an online image:

      --buildroot-image registry.access.redhat.com/ubi8/ubi

  In both cases, it is essential to use chroot-compatible images!

- Hermetic build process is enhanced by adding used imaged digests into the
  metadata and confirming that exactly same image is used in the next step.

- The mock-hermetic-repo command now implements a retry mechanism for
  downloading files.

- The `podman load` mechanism for loading OCI archive bootstrap images has been
  replaced with `podman pull oci-archive:/path/to-the.tar`.

### Bugfixes

- The [chroot_scan plugin](Plugin-ChrootScan) [issue#1490][] has been fixed so it
  no longer (re)creates resultdir below the global `basedir`, but under the
  per-package resultdir (by default in a `/var/tmp/` sub-directory).  In turn, the
  resultdir is no longer created with improper ownership.

- Make `--dnf-cmd` compatible with DNF5, fixes [issue#1400][].

- The `libexec/create_default_route_in_container.sh` file shipped with Mock has
  been removed, it was never used in practice (relates to [issue#113][]).

- The [hermetic mode](feature-hermetic-builds) no longer fallbacks to a manual
  bootstrap installation using the hosts DNF stack; it doesn't make sense
  because we don't have the bootstrap packages pre-downloaded in the local
  "offline" repository.  Fixes [issue#1522][].

- The error message in the `podman_check_native_image_architecture()` method has
  been fixed to correctly indicate the expected (system) architecture and the
  image architecture.

- Regression introduced in Mock v5.7 that ignored the `dnf_builddep_opts`
  configuration option has been fixed, [issue#1496][].

- The `%pre` scriptlet installing the `mock` group is newly not used for modern
  distributions like Fedora 39+ or Mageia (group/user additions are handled by
  an RPM built-in feature).

### Mock Core Configs v41.5 changes

- The Fedora ELN template has been updated for the new pullspec of the bootstrap
  image.

- The Fedora ELN ResilientStorage repositories are obsolete and have been
  removed from the ELN template.

- The EPEL 10 configuration has been updated to include the epel and epel-testing
  repos with the appropriate metalinks.  Previously it only included the koji
  local repo.

- Fedora 39 is now [end-of-live](https://fedorapeople.org/groups/schedule/f-39/f-39-all-tasks.html);
  the corresponding Mock configuration files have been moved under the
  `/etc/mock/eol` directory.

- Fix [openSUSE-tumbleweed update failure][issue#1506] during the second build.

- The CentOS Stream 10 configuration has been updated to use
  `quay.io/centos/centos:stream10` as its bootstrap image, instead of the
  previously used development image.


#### The following contributors have contributed to this release:

- Addisu Z. Taddese
- Carl George
- cheese1
- duli
- Jakub Kadlcik
- Maksym Kondratenko
- Miroslav Suchý
- Ralph Bean
- Romain Geissler
- Tomas Kopecek
- Yaakov Selkowitz

Thank You!

[issue#113]: https://github.com/rpm-software-management/mock/issues/113
[issue#1506]: https://github.com/rpm-software-management/mock/issues/1506
[issue#1490]: https://github.com/rpm-software-management/mock/issues/1490
[issue#1522]: https://github.com/rpm-software-management/mock/issues/1522
[issue#1400]: https://github.com/rpm-software-management/mock/issues/1400
