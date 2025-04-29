# Why Mock?

This document tries to answer two questions:

1. Why you should use Mock instead of lower-level tooling like `rpmbuild`
2. Why you should not try to reimplement Mock and rather join the project


## Mock builds packages in a dedicated environment

Builds are done in a dedicated buildroot that contains only a minimal set of
packages. As a consequence, build failures are deterministic and reproducible
because they cannot be affected by something that user installed/configured on
their host system.

Additionally, building RPM packages is inherently dangerous because specfiles
are written in a Turing-complete language. Building an untrusted package can
easily lead to a compromised system. This is also true for self-written
packages. One small bug like `rpm -rf %{?nonexisting}/` can wipe your entire
system if you are unwise enough to run `rpmbuild` as `root`. Or at least your
user home directory.

Mock does many parts of the build process inside a `systemd-nspawn`
container (or at least [chroot][chroot]) to avoid such disasters as much as
possible.

For fully offline builds, Mock supports [hermetic builds][hermetic-builds].

## Mock can build packages for different distributions

Mock comes with the `mock-core-configs` package which provides a list
[configuration files for many RPM-based distributions][mock-core-configs].
Mock allows building a package for any of them, regardless of what distribution
is installed on your host system.

Users can easily create and distribute
[their own configuration files][mock-configuration].

Let's say you use Fedora 41 as your operating system and want to build a package
for RHEL 8 (or any other distribution). Mock then reads the configuration file
to know what repositories should use, what macros to define, what packages
to install into the minimal buildroot, etc. It does all that, and then builds
the package inside this chroot.


## Mock installs build-time dependencies

Unlike `rpmbuild`, Mock automatically installs all `BuildRequires` dependencies
needed by the package. It also supports [dynamic dependencies][DynamicBuildRequires]
through `%generate_buildrequires`, which is the standard way of dealing with
dependencies for Python, Go, Rust, and other languages.

Additionally, as an opt-in, Mock can install
[dependencies from non-RPM sources][external-dependencies] like PyPI, RubyGems,
etc.


## Mock is not constrained by the host system

You can easily prepare minimal buildroot with something like this:

```
dnf --installroot /tmp/buildroot --use-host-config install @buildsys-build
```

But what if, instead of using your system configuration, you want to use
repositories for a different distribution. In some cases, it works just fine.

But if the distribution is older (e.g. RHEL) than your host system, it may use a
different package manager (e.g. Yum) which can install a different set of
packages, the metadata can use different hashing algorithms, etc.

Conversely, if the distribution is newer (e.g. Fedora Rawhide) it may require
some RPM features or macros, that are not yet available on the host system.

Mock solves this by using a [bootstrap chroot][bootstrap-chroot].

This feature unlocked a lot of innovation in RPM because the development is not
limited by the OS used in the builder infrastructure anymore.


## Mock prepares a directory structure for rpmbuild

Before `rpmbuild` can be used, it requires a specific directory structure to be
created. Users typically do it by running `rpmdev-setuptree` on their systems,
but inside of a chroot, the structure needs to be created manually with correct
location and permissions.


## Mock elevates permissions responsibly

Mock does a lot of things to prepare a buildroot. For some of them
(e.g. installing build dependencies) Mock needs to elevate permissions to
root. But it does so only for a limited time-frame, and drops back to normal
user as soon as possible.


## Mock sets build-specific macros

Some distributions or architectures require specific macros to be set, so that
RPM packages are built correctly. For example, some chroots set `%_host_cpu` to
`ppc64le`, some chroots adjust the `%dist` macro, etc. The `mock-core-configs`
package provides reasonable defaults, but on top of that, users define or change
any macro they want.

The same goes for DNF/Yum placeholders like `$releasever`, `$arch`, etc.


## Mock prepares special devices

Some packages require special devices like `/dev/fuse` `/dev/loop-control`,
`/dev/hwrng`, `/dev/prandom`, etc to build successfully. Mock makes them
available inside of the buildroot.


## Mock caches downloaded RPM packages

Not all dependencies have to be downloaded every time. This brings significant
performance improvements especially when consecutively rebuilding the same RPM
package or a package from the same ecosystem (e.g. multiple Python packages).

Mock also caches DNF metadata (often tens of megabytes), which is significant
because downloading metadata was a well-known bottleneck before DNF5.


## Also worth mentioning:

- Mock uses the same timezone as the host system



[bootstrap-chroot]: https://rpm-software-management.github.io/mock/Feature-bootstrap
[DynamicBuildRequires]: https://fedoraproject.org/wiki/Changes/DynamicBuildRequires
[external-dependencies]: https://rpm-software-management.github.io/mock/Feature-external-deps
[mock-core-configs]: https://rpm-software-management.github.io/mock/Mock-Core-Configs
[hermetic-builds]: https://rpm-software-management.github.io/mock/feature-hermetic-builds
[mock-configuration]: https://rpm-software-management.github.io/mock/configuration
[chroot]: https://en.wikipedia.org/wiki/Chroot
