Feature: Mock is able to work with dnf4 chroots

    @dnf4
    Scenario: Building a DNF4 chroot without bootstrap chroot
        Given an unique mock namespace
        And mock is always executed with "--no-bootstrap-chroot"
        When an online source RPM is rebuilt against centos-stream+epel-9-x86_64
        Then the build succeeds
