---
layout: default
title: Release Notes - Mock v5.1 and mock-core-configs v39.1
---

Released on 2023-09-15.


## New 5.1 features

- We [implemented a convenience fallback][PR#1200] from **bootstrap-from-image**
  to the slower **bootstrap-installed-DNF-from-host** for the cases when Podman
  can not be used properly (when container image can not be pulled, image can
  not be mounted, image architecture mismatch, Podman is not available or not
  working - e.g. if run in non-privileged Docker, etc).

  There's also a new ["podman pull" backoff logic][commit#395fc07f796] that
  makes Mock to retry Podman pulling for 120s (default).  Feel free to adjust this
  timeout by `config_opts["bootstrap_image_keep_getting"]` option.
- Mock [newly logs out][PR#1210] the package management toolset versions (e.g.
  version of DNF, RPM, etc.) that is used for the buildroot installation.  This
  is a feature helping users to diagnose problems with buildroot installation
  (minimal buildroot, `BuildRequires`, dynamic build requires, etc.).  It might
  seem like a trivial addition, but sometimes it isn't quite obvious where the
  tooling comes from (is that from host? from bootstrap? was it downloaded
  "pre-installed" with bootstrap image?).
- There's a [new "INFO" message][commit#8c7aad5680e8f86] raised when running
  Podman in Docker, potentially without `docker run --privileged`.  This should
  decrease the confusion if Mock subsequently falls-back to non-default
  `use_bootstrap_image=False`.  See [issue#1184][] for more info.
- New exception `BootstrapError` was invented with (if not caught) returns with
  exit status 90.  This exception covers problems with the bootstrap chroot
  preparation.
- The `package_state.py` plugin has been updated to sort the displayed list of
  installed and available packages alphabetically (previously the list of packages
  was printed in random order).
- Per [PR#1220][] discussion, Mock package newly `Recommends` having DNF5, DNF and
  YUM package managers installed on host.  These packages are potentially useful,
  at least when the (default) bootstrap preparation mechanism (bootstrap image)
  fails and the bootstrap needs to be installed with host's package management.
  Previously Mock just "suggested" having them installed, which though used to
  have almost zero practical effect (as Suggests are not installed by default).
- Mock now, at least on the best effort basis (if used with
  `package_manager=dnf`), ["fails" with exit status 30][issue#42] if it isn't able
  to process the `--postinstall` request (i.e. installing the built packages into
  the target chroot).  Previous Mock versions used to ignore (with warning) the
  failed package installation attempts.
- The SCM logic [got a new option][PR#1197]
  `config_opts['scm_opts']['int_src_dir']` that instructs Mock to search for
  sources in a specified sub-directory.


### Bugfixes

- Some container images Mock is using for initializing bootstrap chroot (e.g.
  `centos:7`), do not provide all the needed architectures.  Podman [though
  silently pulls arch-incompatible
  image](https://github.com/containers/podman/issues/19717), which caused
  [hard-to-debug build failures](https://github.com/fedora-copr/copr/issues/2875).
  Mock 5.1 therefore [implements a new assertion][PR#1199] failing the build
  early, before mistakenly trying to run emulated "--forcearch" chroot leading to
  failure.  The assertion is exposed as a Python library call
  `mockbuild.podman:podman_check_native_image_architecture()`.
- When bootstrap chroot is initialized from downloaded container image, it
  typically contains `/etc/rpm/macros.image-language-conf` file with locale
  filtering of some kind (per defaults from the fedora-kickstarts project).
  This bootstrap configuration though affects the buildroot installation
  (filtering l11n files from buildroot) and this is sometimes unexpected.
  Mock now [automatically removes the macro file][PR#1189], see
  [issue#1181][] for more info.
- Manual page has been fixed to better describe the `--config-opts=option=value`
  semantics.
- Mock uses `tmpfs` mountpoints in some cases just to hide (on host) some rather
  complicated mount structures (done in chroot/separate mount namespace).  These
  "barrier" mount points though used to have the default `mode=0777` potentially
  allowing anyone to accidentally write there and cause e.g. unmount failures.
  New Mock [uses `mode=0755`][PR#1213] instead.
- The `systemd-nspawn` utility [v253.9 started
  failing](https://github.com/systemd/systemd/issues/29174) with pre-mounted
  `<buildroot>/proc` directory (used like `systemd-nspawn -D <buildroot>`).
  The resulting Mock error, per several reports like [this
  one](https://github.com/fedora-copr/copr/issues/2906), was rather cryptic:

      # /usr/bin/systemd-nspawn -q -M 50743cd0fe0a4142b9b2dbb2c5f8eea6 -D /var/lib/mock/fedora-39-x86_64-bootstrap-1694347273.676351/root
      Failed to mount /proc/sys (type n/a) on /proc/sys (MS_BIND ""): Invalid argument
      Failed to create /user.slice/user-1000.slice/session-12.scope/payload subcgroup: Structure needs cleaning

  Previous versions of `systemd-nspawn` silently over-mounted the `/proc`
  filesystem so Mock simply could _always_ pre-mount `/proc` (with
  `--isolation=simple` it is still needed).

  To work-around this problem, new Mock now [stopped "pre-mounting"][PR#1214]
  `<buildroot>/proc` directory when `--isolation=nspawn` (default) and the package
  management downloaded with bootstrap image is used for **installing packages
  into the bootstrap chroot**.
- Mock automatically kills "orphan" processes started in buildroot (unwanted
  "daemons").  These are typically started by DNF installation that trigger some
  buggy scriptlet.  The corresponding code has been [moved][PR#1214] to a better
  place which assures that such processes are **always** killed before "buildroot
  in bootstrap" recursive bind-mount is unmounted.
- Mock properly dumps Podman's standard error output to logs to allow the user
  better diagnose related errors.  Per [issue#1191][] report.
- Mock 5.0 release contained a bug causing that `postyum` hooks (in Mock plugins)
  were not called.  In turn, e.g. `root_cache` locking mechanism [was
  broken][issue#1186] causing Mock to wait for the lock unnecessary long.
- Previous version of Mock used to bind-mount `/proc` and `/proc/filesystems` in
  wrong order, eventually causing that `/proc/filesystems` was not visible (this
  could affect some scriptlests from packages installed into such a chroot).  This
  [has been fixed now][PR#1214].
- The `--installdeps foo.spec` feature is implemented using the RPM Python API.
  Previously we used the method `hdr.dsFromHeader()` to get the list of
  `BuildRequires`.  This method has been removed from the Python RPM API (rpm
  v4.19) in favor of the long-enough existing `rpm.ds(hdr, ...)` method.  Mock
  [has started using `rpm.ds()` API call][PR#1223] to fix the [`AttributeError:
  'rpm.hdr' object has no attribute 'dsFromHeader'`][issue#1203] traceback on
  newer systems (e.g. Fedora 40+).
- The `--shell` standard output is no longer affected by `podman image unmount`
  output executed in the background (prints out the image ID).


### mock-core-configs v39.1 changes

- Mageia 9 to branched (released recently) and Cauldron retargeted to Mageia 10.
- openSUSE Leap 15.3 became end-of-life at the end of 2022 and the corresponding
  Mock configuration is now [end-of-life][PR#1175], too.
- openSUSE Leap 15.5 configuration [added][PR#1175].


**Following contributors contributed to this release:**

 * Evan Goode
 * Miroslav Suchý
 * Neal Gompa
 * Pavel Raiskup
 * Takuya Wakazono

Thank you.

[PR#1200]: https://github.com/rpm-software-management/mock/pull/1200
[issue#1186]: https://github.com/rpm-software-management/mock/issues/1186
[PR#1220]: https://github.com/rpm-software-management/mock/pull/1220
[issue#1203]: https://github.com/rpm-software-management/mock/issues/1203
[issue#42]: https://github.com/rpm-software-management/mock/issues/42
[PR#1189]: https://github.com/rpm-software-management/mock/pull/1189
[issue#1184]: https://github.com/rpm-software-management/mock/issues/1184
[commit#395fc07f796]: https://github.com/rpm-software-management/mock/commit/395fc07f796
[PR#1210]: https://github.com/rpm-software-management/mock/pull/1210
[PR#1197]: https://github.com/rpm-software-management/mock/pull/1197
[issue#1191]: https://github.com/rpm-software-management/mock/issues/1191
[PR#1199]: https://github.com/rpm-software-management/mock/pull/1199
[commit#8c7aad5680e8f86]: https://github.com/rpm-software-management/mock/commit/8c7aad5680e8f86
[PR#1223]: https://github.com/rpm-software-management/mock/pull/1223
[issue#1181]: https://github.com/rpm-software-management/mock/issues/1181
[PR#1213]: https://github.com/rpm-software-management/mock/pull/1213
[PR#1175]: https://github.com/rpm-software-management/mock/pull/1175
[PR#1214]: https://github.com/rpm-software-management/mock/pull/1214
