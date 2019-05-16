# Mock

A 'simple' chroot build environment manager for building RPMs.

Mock is used by the Fedora Build system to populate a chroot environment, which is then used in building a source-RPM (SRPM). It can be used for long-term management of a chroot environment, but generally a chroot is populated (using DNF), an SRPM is built in the chroot to generate binary RPMs, and the chroot is then discarded.

## User documentation

This is an area for developers. You may be looking for [user documentation](https://github.com/rpm-software-management/mock/wiki).

## Sources

Mock source tarballs: https://github.com/rpm-software-management/mock/releases

## Mock Branches

Mock currently has one active branch plus master.

 * `mock-1.0` - This branch was used for EL-5 and there will be no changes.
 * `mock-1.3` - This branch is in security-fixes-only mode and is used for EL-6.
 * `master` - This is currently mock 1.4.x and is still getting features. It is used for everything else. This branch is used purely for releasing.
 * `devel` - All development happens here, if you want to send patches, use this branch.

## Communication

Do you have a patch, an idea, or just a question? You can write to [buildsys mailing list](https://lists.fedoraproject.org/admin/lists/buildsys%40lists.fedoraproject.org/) or try [#fedora-buildsys](http://webchat.freenode.net/?channels=fedora-builsys) on [Freenode](https://freenode.net/). We prefer email though.

## Getting and compiling mock

    git clone https://github.com/rpm-software-management/mock.git
    cd mock
    cd mock-core-configs
    tito build --rpm
    cd ../mock
    tito build --rpm


The latest release for all supported platforms can be found in this [Copr repository](https://copr.fedorainfracloud.org/coprs/g/mock/mock-stable/).

## Nightly

Package from the latest commit in the devel branch can be obtained from https://copr.fedorainfracloud.org/coprs/g/mock/mock/

Latest status: [![build status](https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock/)

## License

GPLv2+
