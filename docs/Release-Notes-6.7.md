---
layout: default
title: Release Notes - Mock 6.7 and Core Configs 44.2
---

## [Release 6.7](https://rpm-software-management.github.io/mock/Release-Notes-6.7) - 2026-03-02

### New features and important changes

* The default mock `umask` has been changed from `0002` to `0022` to prevent
  permission issues.  The previous setting caused unexpected default permissions
  during image builds inside Mock.

- New `expand_spec` plugin: This plugin expands the specfile into
  expanded-spec.txt within the results directory.  This ensures access to a
  fully parsed and accurate specfile from within the chroot.  ([Issue
  #1705][issue#1705])

- `/bin/yum` support for `--calculate-dependencies`: The
  `--calculate-dependencies` command now supports the yum package manager for
  building older distributions.  This allows the use of appropriate bootstrap
  images with `/bin/yum` without issues.  Additionally, `mock-hermetic-repo` has
  been updated with a `--compatibility` flag to create repositories compatible
  with both `dnf` and `yum`.

* The `traceLog()` decorator, used for tracking when internal methods are
  entered and exited, has been disabled.  **Warning:** We plan to remove this
  decorator entirely; please follow [issue#1681][] for updates.  In the
  meantime, you can export the `MOCK_TRACE_LOG=true` environment variable to
  revert this change and re-enable the logging.

* The suggested location for the host certificates bundle has been updated from
  `/etc/pki/tls/certs/ca-bundle.crt` to
  `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, following the
  [droppingOfCertPemFile Fedora Change](https://fedoraproject.org/wiki/Changes/droppingOfCertPemFile).

  These bundles are automatically synced into Mock chroots for specific targets
  (e.g., openSUSE).  This new location is also compatible with EPEL 8 hosts.
  Fixes [issue #1667][],


### Bugfixes

- RISC-V Personality Recognition: Mock now recognizes `riscv32` and `riscv64`
  architectures when selecting the execution personality for the RPM/DNF stack
  (see personality(2)).

- `mock --scrub=all` now correctly backs up successful builds from the
  buildroot.  This resolves [issue #1639][].  The backup process now uses `mv`
  semantics instead of `cp`, which avoids file duplication, preserves
  timestamps, and improves performance.  Following a security review, the use of
  `util.run` was replaced with `os.replace` to ensure files are overwritten
  safely.  Internal logs and comments in `backup_build_results` have also been
  clarified.

* Mock no longer fails if `resolv.conf` is missing on the host.  While builds
  requiring network access (`--enable-networking`) will still fail later, Mock
  will no longer crash with a `FileNotFoundError` during the initialization
  phase.

* Hermetic builds now provide access to the "offline repository" from within the
  (directory with RPM files) via the `/hermetic_repo` bind-mount ([PR#1712][]).

  While some packages expect `/var/cache/{dnf|yum}` to be populated with these
  downloaded RPMs, `dnf4` does not do so for the "offline" repositories
  (`baseurl=file://...`) used in hermetic builds (unlike `dnf5` with
  `keepcache=1`).  Providing `/hermetic_repo` ensures that buildroot packages
  are always easily accessible.

* Bootstrap image caching for hermetic builds now utilizes
  [skopeo](https://github.com/containers/skopeo) sync instead of
  `podman pull|save` commands.  Skopeo handles digests more reliably, ensuring
  the correct image is always used.

* The `file_util.rmtree` cleanup process has been significantly accelerated,
  particularly for large buildroots.  For example, the cleanup time for a tree
  containing ~2M files has been reduced from over 13 minutes to approximately
  one minute.

* Fixed the `mock --help` output to inform user about `--scrub=bootstrap`.

* The `unbreq` plugin now supports both `--isolation=simple` and
  `--no-bootstrap-chroot` options.  Additionally, the plugin no longer crashes
  when encountering `(foo if bar)` expressions in `BuildRequires`.

* The performance of `unbreq` has been significantly improved through caching
  and parallelization, and the plugin now logs standard output for failed
  commands.

* The Mock package now pulls in `dnf5` by default on Enterprise Linux 11+
  distributions.


### Mock Core Configs 44.2 changes

- openSUSE Tumbleweed configs now use DNF5 for the package manager.

#### The following contributors have contributed to this release:

- Marián Konček
- Miroslav Suchý
- mkoncek
- Neal Gompa
- nikitych
- Pavel Raiskup
- Sérgio M. Basto
- Simone Caronni
- Tomas Kopecek
- Yuming Zhu

Thank You!

[issue#1639]: https://github.com/rpm-software-management/mock/issues/1639
[issue#1681]: https://github.com/rpm-software-management/mock/issues/1681
[issue#1667]: https://github.com/rpm-software-management/mock/issues/1667
[issue#1705]: https://github.com/rpm-software-management/mock/issues/1705
[PR#1712]: https://github.com/rpm-software-management/mock/pull/1712
