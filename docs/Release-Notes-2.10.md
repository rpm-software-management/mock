---
layout: default
title: Release Notes 2.10
---

Released on - 2021-04-27.

## Mock 2.10 bugfixes:

 * The `podman run` command which is used to pre-prepare the base mock bootstrap chroot
   is now called just with `-i`, not with `-i -t`.  That's because the new Podman
   variants dislike `-t` when no tty is on the input.

 * Fixed traceback for copying the Katello configs into the bootstrap chroot,
   [PR 678][PR#678].

 * Mount point handling was fixed;  newly we use the correct and expected
   mount-point options for recursive mounts (mostly needed for older util-linux
   variants), and we correctly umount sub-set of already ḿounted mountpoints
   upon some failure (traceback).  [PR 712][PR#712]


## Mock-core-configs v34.3:

 * Added Oracle Linux 7 and 8 configs.

 * Add openSUSE Leap 15.3 configs.

 * The openSUSE Leap 15.1 config was marked to EOL in configs.

 * Add openSUSE Tumbleweed s390x config

 * AlmaLinux 8 configs added

 * The 'make' package was removed from the minimal ELN buildroot.


The following contributors contributed to this release:

 * David Ward
 * Miro Hrončok
 * Miroslav Suchý
 * Neal Gompa

Thank you!

[PR#712]: https://github.com/rpm-software-management/mock/pull/712
[PR#678]: https://github.com/rpm-software-management/mock/pull/678

