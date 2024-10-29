A new plugin, `export_buildroot_image`, has been added.  This plugin can export
the Mock chroot as an OCI archive once all the build dependencies have been
installed (when the chroot is ready-made for runnign `/bin/rpmbuild -bb`).

A new complementary feature has been implemented in Mock, and can be enabled
using the following option:

    --buildroot-image /tmp/buildroot-oci.tar

It allows the use of generated OCI archives as the source for the build chroot,
similar to how `bootstrap_image` is used "as the base" for the bootstrap chroot.

Additionally, this feature may be used as:

    --buildroot-image registry.access.redhat.com/ubi8/ubi

Of course, in both cases it is important to use chroot-compatible iamges.
