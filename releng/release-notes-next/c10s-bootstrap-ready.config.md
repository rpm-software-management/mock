The CentOS Stream 10 configuration has been updated to use
`quay.io/centos/centos:stream10-development` as its bootstrap image.  Since
this image [already has the `python3-dnf-plugins-core` package
installed](https://issues.redhat.com/browse/CS-2506), the configuration is also
updated to set `bootstrap_image_ready = True`.  This means the image can be
used "as is" to bootstrap the DNF stack without installing any additional
packages into the prepared bootstrap chroot, significantly speeding up
bootstrap preparation.
