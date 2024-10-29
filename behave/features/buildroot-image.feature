Feature: Mock 6.0+ supports --bootstrap-image feature and OCI buildroot exports

    @buildroot_image
    Scenario: Use image from registry for buildroot preparation
        Given an unique mock namespace
        Given mock is always executed with "--buildroot-image registry.fedoraproject.org/fedora:rawhide"
        When an online source RPM is rebuilt against fedora-rawhide-x86_64
        Then the build succeeds

    @buildroot_image
    Scenario: Image from 'export_buildroot_image' works with --buildroot-image
        Given an unique mock namespace
        Given next mock call uses --enable-plugin=export_buildroot_image option
        # No need to do a full build here!
        When deps for python-copr-999-1.src.rpm are calculated against fedora-rawhide-x86_64
        And OCI tarball from fedora-rawhide-x86_64 backed up and will be used
        And the fedora-rawhide-x86_64 chroot is scrubbed
        And an online SRPM python-copr-999-1.src.rpm is rebuilt against fedora-rawhide-x86_64
        Then the build succeeds
