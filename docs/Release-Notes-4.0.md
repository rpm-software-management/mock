---
layout: default
title: Release Notes - Mock v4.0
---

Released on 2023-05-22.

## Mock v4.0 new features:

- The RPM Software Management team(s) work hard on the [DNF5][] project, which
  is planned to be the [default package manager in F39][].  Compared to [DNF4][],
  DNF5 is a from-scratch rewritten software, implying that features and
  command-line options might be implemented differently.  That's why Mock needed
  a special logic to support it.  While DNF5 is still not the default at this
  moment, Mock 4+ supports it and allows users to experiment:

  ```
  $ mock -r fedora-rawhide-x86_64 --config-opts=package_manager=dnf5 --shell
  ```

  When used like this, Mock installs DNF5 package manager into the bootstrap
  chroot first (using DNF5 itself, if found on host, or just using DNF4).
  Later, using DNF5 from bootstrap, installs the target Rawhide buildroot.

- The [--use-bootstrap-image](Feature-container-for-bootstrap) feature,
  implemented using the containerization [Podman][] command-line tooling, did
  not work correctly if Mock itself was run
  [in container](index#mock-inside-podman-fedora-toolbox-or-docker-container).
  At the time of releasing Mock 4.0, running nested Podman containers still
  requires quite a lot of
  [configuration done in the image](https://github.com/containers/podman/blob/36510f6/contrib/podmanimage/stable/Containerfile).
  So the requirements were relaxed to not run Podman containers, but only
  extract the container images using the [podman image mount][PR#1073] feature.
  So now, the `--use-bootstrap-image` feature works if Mock is run in Podman.

- Mock historically called the `useradd` utility with `-n` option to not create
  the default `mock` group in the chroot.  The `-n` option has been a Red Hat
  Enterprise Linux downstream patch, later implemented upstream as `-N`.  The
  `-N` option is now supported almost everywhere (since RHEL 6+).  If you build
  for older chroots than Enterprise Linux 6 (EOL nowadays), you might need to
  modify the `config_opts["useradd"]` option.

## Mock v4.0 bugfixes:

- The "essential" mount-points (`/proc`, `/sys`, ..) were not correctly mounted
  to the target buildroot at the time of its installation/initialization (when
  package manager from bootstrap chroot is used to install the buildroot
  packages).  This wasn't very obvious, because, during the later phases of Mock
  builds, Mock had those essential mount points mounted.  This caused issues
  with the installation of packages that relied on their existence, see
  [rhbz#2166028].

- Before killing the leftover in-chroot processes, older Mock versions first
  unmounted (well at least it tried) the mounted filesystems in the chroot.
  This has been fixed, and Mock does it vice-versa so both unmounting itself is
  less likely to have problems and killing the processes is easier.

- Mock ignored the `bootstrap_` prefixed `config_opts` options, especially
  useful on commandline for debugging (e.g.
  `--config-opts=bootstrap_chroot_additional_packages=package-foo`).  The
  configuration option logic
  [was adjusted](https://github.com/rpm-software-management/mock/commit/8bd4adcaa197af4a7b6a915a01484c51d1c1cc5b)
  to fix this problem.

- The manual page of Mock was fixed so users are now instructed to fill issues
  against the GitHub upstream [Mock project](https://github.com/rpm-software-management/mock/issues),
  not the Red Hat Bugzilla.

## mock-core-configs-38.4-1

- Fedora 35 and 36 are now EOL, so the configuration was moved
- The `includepkgs=devtoolset*` options were
  [dropped](https://github.com/rpm-software-management/mock/pull/1042) from the
  SCL-related CentOS 7 configuration.  This allows the installation of other SCL
  packages during package build (specified by `BuildRequires:`).
- The `useradd` override configuration was removed as it is not needed now,
  Mock v4.0 now uses `useradd -N` (not `useradd -n`) by default.
- The openSUSE i586 repos have been moved out of the main repos into a port.

**Following contributors contributed to this release:**

 * @cheese1
 * @lilinjie
 * Miroslav Suchý

Thank you.


[Podman]: https://podman.io/
[DNF5]: https://github.com/rpm-software-management/dnf5
[DNF4]: https://github.com/rpm-software-management/dnf
[PR#1073]: https://github.com/rpm-software-management/mock/pull/1073
[default package manager in F39]: https://fedoraproject.org/wiki/Changes/ReplaceDnfWithDnf5
[rhbz#2166028]: https://bugzilla.redhat.com/show_bug.cgi?id=2166028
