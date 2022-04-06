Feature: Test the "library" methods

    @library @simple_load_config
    Scenario: The --resultdir option is incompatible with --chain
        When simple_load_config method from mockbuild.config is called with fedora-rawhide-x86_64 args
        Then the return value contains a field "description=Fedora Rawhide"
