Feature: Mock correctly works with DNF5

    @dnf5 @no-bootstrap
    Scenario: Building in Rawhide with DNF5, without bootstrap chroot
        Given mock is always executed with "--no-bootstrap-chroot"
        And an unique mock namespace
        When an online source RPM is rebuilt
        Then the build succeeds

    @dnf5 @no-bootstrap-image
    Scenario: Building in Rawhide with DNF5 with DNF5 on host
        Given mock is always executed with "--no-bootstrap-image"
        And an unique mock namespace
        When an online source RPM is rebuilt
        Then the build succeeds
