Feature: Mock 5.7+ supports hermetic builds

    @hermetic_build
    Scenario: Hermetic build against a DNF5 distribution
        Given an unique mock namespace
        When deps for python-copr-999-1.src.rpm are calculated against fedora-rawhide-x86_64
        And a local repository is created from lockfile
        And a hermetic build is retriggered with the lockfile and repository
        Then the build succeeds
        And the produced lockfile is validated properly

    @hermetic_build
    Scenario: Hermetic build against a DNF4 distribution
        Given an unique mock namespace
        When deps for mock-test-bump-version-1-0.src.rpm are calculated against centos-stream+epel-9-x86_64
        And a local repository is created from lockfile
        And a hermetic build is retriggered with the lockfile and repository
        Then the build succeeds
        And the produced lockfile is validated properly
