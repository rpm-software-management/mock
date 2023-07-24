---
layout: default
title: Release Notes - Mock v?.?
---

Released on ????-??-??.

## Mock v?.? new features:

- The `use_bootstrap_image` feature has been turned on as it was stabilized in
  this release and it speeds up the bootstrap chroot preparation a lot
  (by not installing potentially hundreds of packages into the bootstrap chroot,
  but just extract the `boostrap_image` contents).  For the RHEL based chroots
  (where UBI `bootstrap_image` is in use, and where `python3-dnf-plugins-core`
  is installed by default) we also turned on the `bootstrap_image_ready=True`
  which drastically speeds the bootstrap preparation.  See the explanation for
  `bootstrap_image_ready` below.  See [PR#1101][] for more info.

- Start using `useradd` and `userdel` utilities from the host to modify
  in-chroot `etc/passwd` and `etc/group`.  This allowed us to remove
  the `shadow-utils` package from the list of "minimal buildroot" packages
  ([issue#1102][]).

- There's a new feature `config_opts['copy_host_users'] = ['pesign', ...]` that
  allows users to specify a list of users to pre-create in buildroot, copying
  the IDs from the host.  Users/groups used to be historically created by
  post-scriptlets from the buildroot packages, but the user/group IDs often did
  not match the IDs on the host - possibly causing weird and hard to fix issues
  similar to the [Pesign one][issue#1091].

- Make sure the `/dev/fuse` device is available in Mock buildroot with
  `--isolation=nspawn`.  Without this device, we could not use FUSE filesystems
  with image builds ([PR#1158][] and the [Fedora Infra issue][fuseInfra]).

- New option `config_opts['bootstrap_image_ready'] = True|False` was invented.
  When set to `True`, Mock doesn't try to do any package manager actions inside
  bootstrap (normally Mock installs `dnf` tooling there).  It simply assumes
  that the bootstrap image is ready to use (that the `dnf` tooling is already
  installed on the image).  This might fix hard-to-debug/hard-to-fix issues like
  [issue#1088][] when an unexpected bootstrap image is used.

- The Podman container environment is able to automatically pass down the Red
  Hat Subscription credentials anytime a RHEL-based (UBI) container is run.  But
  the credential files are then on different path than when run natively on
  the host, and that used to break Mock.  Newly, when Mock is run in a Podman
  container, the credentials passed down by Podman are automatically detected
  and used ([PR#1130][]).

- Even though the buildroot is supposed to be initialized with cross-arch
  packages (using the --forcearch RPM feature), the bootstrap chroot is newly
  always prepared with the native architecture.  This change has been done to
  optimize the final buildroot installation because using the "native" DNF is
  much faster than cross-arch emulation using `qemu-user-static`.  As a benefit,
  we can simply use the native pulled Podman `bootstrap_image` even for
  cross-arch builds without any problems.  See [issue#1110][].

- An easier way to skip Mock plugin execution in the Bootstrap chroot has been
  invented.  It is now enough to specify the `run_in_bootstrap = False` global
  variable in such plugin, see [PR#1116][] for more info.  The plugin `hw_info`
  has been newly disabled for the bootstrap chroot this way.

- The bootstrap chroot installation was made smaller;  newly only the
  `python3-dnf` and `python3-dnf-plugins-core` are installed, instead of `dnf`
  and `dnf-plugins-core` (which used to install also unnecessary documentation
  files).

- Automatic downloads (for example with `mock https://exmaple.com/src.rpm`
  use cases) have been changed to automatically retry the download several times
  to work around random network failures ([PR#1132][] and [PR#1134][]).

- The `dnf` and `dnf5` processes are newly always executed with the
  `--setopt=allow_vendor_change=yes` option.  This is done in belief that we
  don't have to protect the Mock builds against `Vendor` changes, and we do this
  because overriding the distro-default RPMs is quite common thing (`mock
  --chain` e.g.) while mimicking the distro-default `Vendor` tag would be
  a painful task.  The thing is that the `allow_vendor_change=no` is going to be
  set by default in DNF5 soon and we want to prevent unnecessary surprises.
  Also, openSUSE has been reported to use this even now with DNF4 ([PR#1160][]).

## Mock v?.? bugfixes:

- Make sure we properly unmount all the Mock mount internal points even though
  the Mock process was interrupted using `CTRL+C` (`KeyboardInterrupt`
  exception).  This has fixed a long-term bug which, when observed before, broke
  the subsequent `mock` processes including `mock --scrub`. Also, the directory
  removal method has been fixed to re-try under [certain
  circumstances][PR#1058]. Relates to [rhbz#2176689][], [rhbz#2176691][],
  [rhbz#2177680][], [rhbz#2181641][], etc.

- Python `imp` module was removed from Python 3.12, so the code was migrated to
  `importlib`, [issue#1140][].

- Automatic SRPM downloads from the web were handling the file names specified
  by HTTP headers using the long-time deprecated `cgi` module.  The module is
  being dropped from Python v3.13 so Mock 5.0 has been fixed to use
  `email.message` library which now provides the same functionality
  ([PR#1134][]).

- The default recursion limit of Python scripts is set to 1000 for non-root
  users; this isn't enough for Mock in some use-cases so the limit was increased
  to 5000.  For example, some utilities have directory-tree stress-tests in
  test suites, and for such cases a very large directory tree can cause too deep
  recursive calls of the `shutil.rmtree()` method.

- The bootstrap-related logging has been fixed so the corresponding log entries
  are now added to the default `root.log` file.  This change should lead to
  a better understanding what is going on in the bootstrap chroot ([issue#539][]
  and [PR#1106][]).

- Mock newly never uses the `--allowerasing` option with the `dnf5 remove`
  command (this option has not been implemented in DNF5 and DNF5 simply fails,
  contrary to the old DNF4 code where it was implemented a no-op,
  [issue#1149][]).

- The SSL certificate copying has been fixed [once more][PR#1113] to use our own
  `update_tree()` logic because the `distutils.copy_tree()` was removed from the
  Python stdlib, and the new stdlib alternative `shutil.copytree()` is not
  powerful enough for the Mock use-cases ([issue#1107][]).

- Mock no longer dumps the long output of the `rpmbuild --help` command into
  `build.log`, fixes [issue#999][].

## mock-core-configs v?.? changes:

- The new `mock-core-configs` package is not compatible with older Mock
  versions, therefore the requirement was bumped to `v5.0` or newer.

- Started using `bootstrap_image_ready = True` for RHEL-based configs as UBI
  images contain all the necessary DNF tooling by default ([PR#1101][]).

- Disable `use_bootstrap_image` for the Mageia chroots;  Mageia doesn't provide
  an officially supported (and working) container images that we could set in
  the `boostrap_image` config option ([issue#1111][]).

- Dropped the `config_opts['useradd']` option from all the configs; the
  `useradd` utility from now on always executed on the host (not in chroot) with
  the `--prefix <chrootRoot>` options ([issue#1102][]).

- Using `$releasever` in openEuler metalink URLs.


**Following contributors contributed to this release:**

 * Miro Hrončok
 * Miroslav Suchý
 * Neal Gompa
 * zengwei2000

Thank you.

[PR#1058]: https://github.com/rpm-software-management/mock/pull/1058
[PR#1101]: https://github.com/rpm-software-management/mock/pull/1101
[PR#1106]: https://github.com/rpm-software-management/mock/pull/1106
[PR#1113]: https://github.com/rpm-software-management/mock/pull/1113
[PR#1116]: https://github.com/rpm-software-management/mock/pull/1116
[PR#1130]: https://github.com/rpm-software-management/mock/pull/1130
[PR#1132]: https://github.com/rpm-software-management/mock/pull/1132
[PR#1134]: https://github.com/rpm-software-management/mock/pull/1134
[PR#1158]: https://github.com/rpm-software-management/mock/pull/1158
[PR#1158]: https://github.com/rpm-software-management/mock/pull/1160
[issue#539]: https://github.com/rpm-software-management/mock/issues/539
[issue#999]: https://github.com/rpm-software-management/mock/issues/999
[issue#1088]: https://github.com/rpm-software-management/mock/issues/1088
[issue#1091]: https://github.com/rpm-software-management/mock/issues/1091
[issue#1102]: https://github.com/rpm-software-management/mock/issues/1102
[issue#1107]: https://github.com/rpm-software-management/mock/issues/1107
[issue#1110]: https://github.com/rpm-software-management/mock/issues/1110
[issue#1111]: https://github.com/rpm-software-management/mock/issues/1111
[issue#1140]: https://github.com/rpm-software-management/mock/issues/1140
[issue#1149]: https://github.com/rpm-software-management/mock/issues/1149
[rhbz#2176689]: https://bugzilla.redhat.com/2176689
[rhbz#2176691]: https://bugzilla.redhat.com/2176691
[rhbz#2177680]: https://bugzilla.redhat.com/2177680
[rhbz#2181641]: https://bugzilla.redhat.com/2181641
[fuseInfra]: https://pagure.io/fedora-infrastructure/issue/11420
