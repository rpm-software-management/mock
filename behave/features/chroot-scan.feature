Feature: The chroot_scan plugin

@chroot_scan
Scenario: Check that chroot_scan works and file permissions are correct
    Given chroot_scan is enabled for dnf5.log
    And an unique mock namespace
    When an online source RPM is rebuilt
    Then the build succeeds
    And dnf5.log file is in chroot_scan result dir
    And ownership of all chroot_scan files is correct

@chroot_scan
Scenario: Check that chroot_scan tarball is created correctly
    Given an unique mock namespace
    And chroot_scan is enabled for dnf5.log
    And chroot_scan is configured to produce tarball
    When an online source RPM is rebuilt
    Then the build succeeds
    And chroot_scan tarball has correct perms and provides dnf5.log
