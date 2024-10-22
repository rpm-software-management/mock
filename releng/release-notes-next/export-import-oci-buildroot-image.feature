A new plugin, `export_buildroot_image`, has been added.  This plugin can export
the Mock chroot as an OCI archive once all the build dependencies have been
installed (when the chroot is ready-made for runnign `/bin/rpmbuild -bb`).
