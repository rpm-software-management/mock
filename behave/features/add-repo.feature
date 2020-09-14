Feature: The --addrepo commandline option.

    Background:
        Given an unique mock namespace
        And pre-intitialized chroot

    Scenario: Test that --addrepo works
        Given a custom third-party repository is used for builds
        When a build is depending on third-party repo requested
        Then the build succeeds

    Scenario: Test that --addrepo LOCAL_DIR works
        Given a created local repository
        And the local repo contains a "always-installable" RPM
        And the local repo is used for builds
        When a build which requires the "always-installable" RPM is requested
        Then the build succeeds
