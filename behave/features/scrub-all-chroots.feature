Feature: Clean all chroots

    @clan_all_chroots
    Scenario: The --scrub-all-chroots works as expected
        When mock is run with "--shell true" options
        And mock is run with "--scrub-all-chroots" options
        Then the directory /var/lib/mock is empty
        And the directory /var/cache/mock is empty
