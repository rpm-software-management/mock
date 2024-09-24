# Mock

A 'simple' chroot build environment manager for building RPMs.

Mock is used by the Fedora Build system to populate a chroot environment, which is then used in building a source-RPM (SRPM). It can be used for long-term management of a chroot environment, but generally a chroot is populated (using DNF), an SRPM is built in the chroot to generate binary RPMs, and the chroot is then discarded.

## User documentation

This is an area for developers. You may be looking for [user documentation](https://rpm-software-management.github.io/mock/).

## Sources

Mock source tarballs: https://github.com/rpm-software-management/mock/releases

## Mock Branches

Mock currently has one active branch plus `main`.

 * `main` - This is used for releasing and developing the latest Mock version.
   If you want to send patches, you probably want this branch.
 * `mock-2` - This branch is used for Mock v2.x, for EL-7, bug-fixes-only mode.
 * `mock-1.4` - End of life, there will be no changes.
 * `mock-1.3` - This branch was used for EL-6, EOL.
 * `mock-1.0` - This branch was used for EL-5, EOL.

## Communication

Do you have a patch, an idea, or just a question?
You can write to [buildsys mailing list](https://lists.fedoraproject.org/admin/lists/buildsys%40lists.fedoraproject.org/)
or try [Fedora Build System Matrix channel](https://matrix.to/#/#buildsys:fedoraproject.org).
We prefer email though.

If you hate mailing lists for some reason (we still prefer it) - you can use [Discussions](https://github.com/rpm-software-management/mock/discussions).

## Getting and compiling mock

    git clone https://github.com/rpm-software-management/mock.git
    cd mock
    cd mock-core-configs
    tito build --rpm
    cd ../mock
    tito build --rpm


The latest release for all supported platforms can be found in this [Fedora Copr project](https://copr.fedorainfracloud.org/coprs/g/mock/mock-stable/).

## Packaging status

<table border="0"><tr><td valign="top">
<img src="https://repology.org/badge/vertical-allrepos/mock.svg?exclude_unsupported=1&header=mock" alt="mock versions" />
</td><td  valign="top">
<img src="https://repology.org/badge/vertical-allrepos/mock-core-configs.svg?exclude_unsupported=1&header=mock-core-configs" alt="mock-core-configs versions" />
</td></tr></table>

## Nightly

Pre-release packages built from the latest git commit in the `main` branch are in [Fedora Copr project](https://copr.fedorainfracloud.org/coprs/g/mock/mock/):

    dnf copr enable @mock/mock
    dnf install mock

### Copr build status

package | released | development
------- | -------- | -----------
mock | [![badge](https://copr.fedorainfracloud.org/coprs/g/mock/mock-stable/package/mock/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/mock/mock-stable/package/mock/) | [![badge](https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock/)
mock-core-configs | [![badge](https://copr.fedorainfracloud.org/coprs/g/mock/mock-stable/package/mock-core-configs/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/mock/mock-stable/package/mock-core-configs/) | [![badge](https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock-core-configs/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock-core-configs/)


## Sponsor

This project is sponsored by [Red Hat](https://www.redhat.com/). [Buy](https://www.redhat.com/en/store) Red Hat subscription to sponsor this project.


## License

[GPL-2.0-or-later](https://spdx.org/licenses/GPL-2.0-or-later.html)
