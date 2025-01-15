Feature: Mock is able to work with dnf4 chroots

    @dnf4 @no-bootstrap
    Scenario: Building a DNF4 chroot without bootstrap chroot
        Given an unique mock namespace
        And mock is always executed with "--no-bootstrap-chroot --config-opts=dnf_warning=False"
        When an online source RPM is rebuilt against centos-stream+epel-9-x86_64
        Then the build succeeds

    @dnf4 @no-bootstrap-image
    Scenario: Building in DNF4 chroot with dnf4 on host, without bootstrap image
        Given an unique mock namespace
        And the python3-dnf package is installed on host
        And mock is always executed with "--no-bootstrap-image"
        When an online source RPM is rebuilt against centos-stream+epel-9-x86_64
        Then the build succeeds

    @dnf4 @no-bootstrap-image @with-dnf4
    Scenario: Building a DNF4 chroot without dnf4 on host, without bootstrap image
        Given an unique mock namespace
        And the python3-dnf package not installed on host
        And mock is always executed with "--no-bootstrap-image"
        When an online source RPM is rebuilt against centos-stream+epel-9-x86_64
        Then the build succeeds
