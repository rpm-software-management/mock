---
layout: default
title: Feature buildroot image
---

Starting from version v6.0, Mock allows users to use an OCI container image for
pre-creating the buildroot (build chroot).  It can be either an online container
image hosted in a registry (or cached locally), or a local image in the form of
a tarball.

Be cautious when using chroot-compatible images (e.g., it is not advisable to
combine EPEL `ppc64le` images with `fedora-rawhide-x86_64` chroot).

## Example Use-Case

1. Mock aggressively caches the build root, so clean up your chroot first:

    ```bash
    $ mock -r fedora-rawhide-x86_64 --scrub=all
    ```

2. Perform any normal Mock operation, but select the OCI image on top of that:

    ```bash
    $ mock -r fedora-rawhide-x86_64 \
        --buildroot-image registry.fedoraproject.org/fedora:41 \
        --rebuild /your/src.rpm
    ```

## Using Exported Buildroot Image

The [export_buildroot_image](Plugin-Export-Buildroot-Image) plugin allows you to
wrap a prepared buildroot as an OCI archive (tarball).  If you have this
tarball, you may select it as well:

```bash
$ mock -r fedora-rawhide-x86_64 \
    --buildroot-image /tmp/buildroot-oci.tar \
    --rebuild /your/src.rpm
```

Again, ensure that you do not combine incompatible chroot and image pairs.
