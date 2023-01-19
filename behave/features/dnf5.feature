Feature: Mock 3.6+ should be able to work with DNF5

    @dnf5
    Scenario: Building in Rawhide with DNF5 but DNF4 on host
        Given mock is always executed with "--config-opts package_manager=dnf5"
        And the dnf5 package not installed on host
        And an unique mock namespace
        When an online source RPM is rebuilt
        Then the build succeeds

    @dnf5
    Scenario: Building in Rawhide with DNF5 with DNF5 on host
        Given mock is always executed with "--config-opts package_manager=dnf5"
        And the dnf5 package is installed on host
        And an unique mock namespace
        When an online source RPM is rebuilt
        Then the build succeeds
