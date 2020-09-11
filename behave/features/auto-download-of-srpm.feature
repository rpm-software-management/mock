Feature: Check that we download source RPMs URLs

    @autodownload
    Scenario: Mock downloads SRPMs in --rebuild mode
        Given an unique mock namespace
        And pre-intitialized chroot
        When an online source RPM is rebuilt
        Then the build succeeds
