Feature: The --list-chroots commandline option

    @list_chroots
    Scenario: Test --list-chroots
        When mock is run with "--list-chroots" options
        Then the exit code is 0
        And stdout contains "fedora-rawhide-x86_64              Fedora Rawhide"
        And stdout contains "rhel+epel-8-x86_64                 RHEL 8 + EPEL"
