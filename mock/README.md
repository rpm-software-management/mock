# Mock

A 'simple' chroot build environment manager for building RPMs.

Mock is used by the Fedora Build system to populate a chroot environment, which is then used in building a source-RPM (SRPM). It can be used for long-term management of a chroot environment, but generally a chroot is populated (using DNF), an SRPM is built in the chroot to generate binary RPMs, and the chroot is then discarded.

## User documentation

This is an area for developers. You may be looking for [user documentation](https://rpm-software-management.github.io/mock/).

## Sources

Mock source tarballs: https://github.com/rpm-software-management/mock/releases

## Mock Branches

Mock currently has one active branch plus `main`.

 * `mock-1.0` - This branch was used for EL-5 and there will be no changes.
 * `mock-1.3` - This branch is in security-fixes-only mode and is used for EL-6.
 * `mock-1.4` - This branch is in bug-fixes-only mode.
 * `main` - This is currently mock 2.x and is used for releasing and
   development.  If you want to send patches, you probably want this branch.

## Communication

Do you have a patch, an idea, or just a question? You can write to [buildsys mailing list](https://lists.fedoraproject.org/admin/lists/buildsys%40lists.fedoraproject.org/) or try [#fedora-buildsys](http://web.libera.chat/) on [Libera.chat](https://libera.chat/). We prefer email though.

If you hate mailing lists for some reason (we still prefer it) - you can use [Discussions](https://github.com/rpm-software-management/mock/discussions).

## Getting and compiling mock

    git clone https://github.com/rpm-software-management/mock.git
    cd mock
    cd mock-core-configs
    tito build --rpm
    cd ../mock
    tito build --rpm


The latest release for all supported platforms can be found in this [Copr repository](https://copr.fedorainfracloud.org/coprs/g/mock/mock-stable/).

## Packaging status

<table border="0"><tr><td valign="top">
<img src="https://repology.org/badge/vertical-allrepos/mock.svg?exclude_unsupported=1&header=mock" alt="mock versions" />
</td><td  valign="top">
<img src="https://repology.org/badge/vertical-allrepos/mock-core-configs.svg?exclude_unsupported=1&header=mock-core-configs" alt="mock-core-configs versions" />
</td></tr></table>

## Nightly

Package from the latest commit in the `main` branch can be obtained from https://copr.fedorainfracloud.org/coprs/g/mock/mock/

Latest status: [![build status](https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/g/mock/mock/package/mock/)


## Sponsor

This project is sponsored by [Red Hat](https://www.redhat.com/). [Buy](https://www.redhat.com/en/store) Red Hat subscription to sponsor this project.


## License

GPLv2+
