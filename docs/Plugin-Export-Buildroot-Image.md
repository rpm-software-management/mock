---
layout: default
title: Plugin export_buildroot_image
---

This plugin allows you to (on demand) export the Mock chroot as an OCI image in
local archive format (tarball).  This tarball can provide additional convenience
for local build reproducibility.  See the example below for details.

By default, this plugin is **disabled**.  You can enable it using the
`--enable-plugin export_buildroot_image` option in `--rebuild` mode.

This plugin has been added in Mock v6.0.

## Example use-case

First, let's start a standard Mock build, but enable the OCI archive generator:

    $ mock -r fedora-rawhide-x86_64 --enable-plugin export_buildroot_image \
            /tmp/quick-package/dummy-pkg-20241212_1114-1.src.rpm
    ... mock installs all build-deps, and does other chroot tweaks ...
    Start: producing buildroot as OCI image
    ... mock performs the rpmbuild ...
    INFO: Results and/or logs in: /var/lib/mock/fedora-rawhide-x86_64/result
    Finish: run

The archive has been saved in the result directory:

    $ ls /var/lib/mock/fedora-rawhide-x86_64/result/*.tar
    /var/lib/mock/fedora-rawhide-x86_64/result/buildroot-oci.tar

Then, you can try re-running the build without Mock, like this:

    $ chmod a+r /tmp/quick-package/dummy-pkg-20241212_1114-1.src.rpm
    $ podman run --rm -ti \
        -v /tmp/quick-package/dummy-pkg-20241212_1114-1.src.rpm:/dummy-pkg.src.rpm:z \
        oci-archive:/var/lib/mock/fedora-rawhide-x86_64/result/buildroot-oci.tar \
        rpmbuild --rebuild /dummy-pkg.src.rpm

    Installing /dummy-pkg.src.rpm
    setting SOURCE_DATE_EPOCH=1401926400
    Executing(%mkbuilddir): /bin/sh -e /var/tmp/rpm-tmp.XIm441
    ...
    Executing(%prep): /bin/sh -e /var/tmp/rpm-tmp.pqJ9hu
    ...
    Executing(%build): /bin/sh -e /var/tmp/rpm-tmp.iaeMZG
    ...
    Executing(%install): /bin/sh -e /var/tmp/rpm-tmp.SHktaE
    ...
    Processing files: dummy-pkg-20241212_1114-1.fc42.x86_64
    ...
    Executing(%clean): /bin/sh -e /var/tmp/rpm-tmp.E71FWH
    ...
    + exit 0

**Warning:** This method of reproducing a Mock build is not recommended for
production use.  During a normal/full Mock rebuild, Mock ensures the buildroot
is fully up-to-date.  Using just plain `rpmbuild` within Podman may result in
outdated files, different structure in the kernel-driven filesystems like
`/proc`, `/dev`, and `/sys`, different SELinux assumptions, permissions, etc.
Proceed with caution, and be prepared to encounter some differences (and perhaps
different build failures).
