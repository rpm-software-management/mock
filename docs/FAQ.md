---
layout: default
title: FAQ
---

## FAQ

### How to preserve environment variable in chroot

Q: I put

    config_opts['environment']['VAR'] = os.environ['VAR']

into config, but the variable is not preserved.

A: Environment is sanitized by consolehelper when elevating UID. You need to alter `/etc/security/console.apps/mock` too.

### I cannot build Fedora or RHEL8 beta package on RHEL/CentOS 7

Q: I am on RHEL 7 and when I run `mock -r fedora-28-x86_64 --init` (similarly for rhelbeta-8-x86_64) I get:

    ....
    ---> Package patch.x86_64 0:2.7.6-4.fc28 will be installed
    ---> Package redhat-rpm-config.noarch 0:108-1.fc28 will be installed
    Error: Invalid version flag: if

A: This is not Mock error. This is because redhat-rpm-config in Fedora 28 (& RHEL 8 Beta) contains rich dependency: `Requires: (annobin if gcc)`. This is a new rpm's feature and is not recognized by RHEL7's rpm. When you are installing the fedora-28 chroot, mock is using host's rpm. And RHEL7 rpm cannot install this package, because of the new feature, which does not recognize.

The solution is to use mock's [bootstrap feature](https://rpm-software-management.github.io/mock/Release-Notes-1.4.1#bootstrap-chroot). It is not enabled by default, because there are still some [unresolved issues](https://github.com/rpm-software-management/mock/labels/bootstrap), but generally it works. Try:

    mock -r fedora-28-x86_64 --init --bootstrap-chroot

### When I can expect next release

Q: A developer merged my pull-request. When I can expect the next release with my fix?

A: I try to stick to two month cadence. Check the last release date and add two months and you can set your expectation. Of course things like Christmas or summer holidays can add a few weeks. On the other hand the branching event in Fedora can make it shorter as I usually do a mock release a day before Fedora branches, because I had to add new configs there anyway.
