Feature: Test error reporting from argument parser

    @errors
    Scenario: The --resultdir option is incompatible with --chain
        When mock is run with "--resultdir /tmp/dir --chain" options
        Then the exit code is 5
        And the one-liner error contains "ERROR: The --chain mode doesn't support --resultdir"
