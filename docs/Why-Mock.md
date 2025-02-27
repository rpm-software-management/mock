# Why Mock?

This document tries to answer two questions:

1. Why you should use Mock instead of lower-level tooling like `rpmbuild`
2. Why you should not try to reimplement Mock and rather join the project


## Mock builds packages inside an isolated environment

Building RPM packages is inherently dangerous because specfiles are written in a
Turing-complete language. Building an untrusted package can easily lead to a
compromised system. This is also true for self-written packages. One small bug
like `rpm -rf %{?nonexisting}/` can wipe your entire system if you are unwise
enough to run `rpmbuild` as `root`. Or at least your user home directory.

Mock builds packages inside of `systemd-nspawn` containers to prevent such
disasters from happening.


## Mock can build packages for different distributions

Mock comes with the `mock-core-configs` package which provides a list
[configuration files for many RPM-based distributions][mock-core-configs].
Mock allows building a package for any of them, regardless of what distribution
is installed on your host system.

Users can easily create and distribute their own configuration files.


## Mock installs build-time dependencies

Unlike `rpmbuild`, Mock automatically installs all `BuildRequires` dependencies
needed by the package. It also supports [dynamic dependencies][DynamicBuildRequires]
through `%generate_buildrequires`, which is the standard way of dealing with
dependencies for Python, Go, Rust, and other languages.

Additionally, not enabled by default, Mock can install
[dependencies from non-RPM sources][external-dependencies] like PyPI, RubyGems,
etc.


## Mock is not bounded by the host system

You can easily prepare minimal buildroot with something like this:

```
dnf --installroot /tmp/buildroot --use-host-config install @buildsys-build
```

But what if, instead of using your system configuration, you want to use
repositories for a different distribution. In some cases, it works just fine.

But if the distribution is older (e.g. RHEL) than your host system, it may use a
different package manager (e.g. Yum) which can install a different set of
packages, the metadata can use different hashing algorithms, etc.

Conversely, if the distribution is newer (e.g. Fedora rawhide) it may require
some RPM features or macros, that are not yet available on the host system.

Mock solves this by using a [bootstrap chroot][bootstrap-chroot].

This feature unlocked a lot of innovation in RPM because the development is not
limited by the OS used in the builder infrastructure anymore.


## Mock prepares a directory structure for rpmbuild

Before `rpmbuild` can be used, it requires a specific directory structure to be
created. Users typically do it by running `rpmdev-setuptree` on their systems,
but inside of a chroot, the structure needs to be created manually with correct
location and permissions.


## Mock sets build-specific macros

Some distributions or architectures require specific macros to be set, so that
RPM packages are built correctly. For example, some chroots set `%_host_cpu` to
`ppc64le`, some chroots adjust the `%dist` macro, etc. The `mock-core-configs`
package provides reasonable defaults, but on top of that, users define or change
any macro they want.


## Mock prepares special devices

Some packages require special devices like `/dev/fuse` `/dev/loop-control`,
`/dev/hwrng`, `/dev/prandom`, etc to build successfully. Mock makes them
available inside of the buildroot.


## Mock caches downloaded RPM packages

Not all dependencies have to be downloaded every time. This brings significant
performance improvements especially when consecutively rebuilding the same RPM
package or a package from the same ecosystem (e.g. multiple Python packages).


## Also worth mentioning:

- Mock uses the same timezone as the host system



[bootstrap-chroot]: https://rpm-software-management.github.io/mock/Feature-bootstrap
[DynamicBuildRequires]: https://fedoraproject.org/wiki/Changes/DynamicBuildRequires
[external-dependencies]: https://rpm-software-management.github.io/mock/Feature-external-deps
[mock-core-configs]: https://rpm-software-management.github.io/mock/Mock-Core-Configs
