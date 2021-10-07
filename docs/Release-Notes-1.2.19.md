---
layout: default
title: Release Notes 1.2.19
---

Mock version 1.2.19 has those changes:

* plugin [PackageState](Plugin/PackageState) is now enabled by default and it has new options. By default this plugin now generate list of installed packages. List of available packages is disabled by default.
* Fedora 25 configs has been added
* GPG keys in configs are now used from package `distribution-gpg-keys`. Keys in `/etc/pki/mock` will be still shipped for some time, so we do not break old user config. But new one will not be added and users are encouraged to migrate their paths to GPG keys.
* you can include some other config using:
   ``include('/path/to/config/to/be/included/include.cfg')``
* there is new option available which will install additional package to minimal chroot. This is extension of already existing option `chroot_setup_cmd`. It was added to easy automated changed of minimal buildroot in Copr.:
   ``config_opts['chroot_additional_packages'] = 'some_package other_package'``
* And it resolves those bugs: RHBZ#1272381, RHBZ#1358397, RHBZ#1362478, RHBZ#1277187, RHBZ#1298220, RHBZ#1264508.

And few notes about future release:
* in next release will be very likely resolved [RHBZ#1246810](https://bugzilla.redhat.com/show_bug.cgi?id=1246810). I.e. /usr/sbin/mock will be moved to /usr/libexec/mock/mock. Since this is very big change, next release will likely be 1.3.0
* Development and documentation will likely move to Github or Pagure. Please follow buildsys mailing list.
