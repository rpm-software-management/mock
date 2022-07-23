---
layout: default
title: Release Notes - Mock v3.1
---

Released on 2022-07-22.

## Mock v3.1 changes:

- There's a fix for a new RPM behavior on F37+ where `rpmbuild` automatically
  cleans the `%buildroot` directory upon a successful build.  This behavior is
  not desired when Mock user wants to keep the buildroot contents for further
  debugging (`config_opts["cleanup_on_success"] = False` is
  configured, or `--no-cleanup-after` option is used).  [Original bug
  report.][rhbz#2105393]

- Mock v3.1+ started using `/bin/tar` instead of `/bin/gtar` for normal work
  with archives.  This default can be changed by a new option
  `config_opts["tar_binary"]`.  This should help with distributing Mock to
  GNU/Linux distributions where `/bin/gtar` symbolic link doesn't exist.

- Mock v3.1+ *still* expects that that the default system Tar represents
  a GNU tar implementation (unless `config_opts["tar"] = 'bsdtar'`).  Mock v3.1
  version though got several fixes that make the work with the BSD tar
  implementation more convenient.


## mock-core-configs-37-4-1

* Add AlmaLinux 9 and AlmaLinux 9 + EPEL configs (neal@gompa.dev)
* Update the AlmaLinux 8 GPG key path (neal@gompa.dev)
* Fix description typo on AlmaLinux 8 for x86_64 (neal@gompa.dev)
* Add RHEL9 templates and configs (carl@george.computer)


## mock-core-configs-37.5-1

* configs: add ELN local Koji repo
* config: sync epel-8 and epel-9 templates
* Add Rocky Linux 9 Configuration and Mod RL8 (label@rockylinux.org)
* Update Fedora ELN repo template (sgallagh@redhat.com)
* EuroLinux 9 chroot configs added (git@istiak.com)
* Fedora 34 is EOL
* circlelinux+epel-8 as epel-8 alternative
* Fix dist value for openSUSE Leap 15.4 (ngompa@opensuse.org)
* Add CircleLinux 8 configs (bella@cclinux.org)
* Add openSUSE Leap 15.4 configs (ngompa@opensuse.org)
* Move openSUSE Leap 15.2 to EOL directory (ngompa@opensuse.org)
* Use MirrorCache for openSUSE repositories instead of MirrorBrain (ngompa@opensuse.org)
* Add Anolis OS 7 and Anolis OS 8 templates and configs (wb-zh951434@alibaba-inc.com)


**Following contributors contributed to this release:**

 * babakovalucie
 * Bella Zhang
 * Carl George
 * DominikaMarchovska
 * Istiak Ferdous
 * JeremiasVavak
 * katerin71
 * Louis Abel
 * Miroslav Suchý
 * naveen
 * Neal Gompa
 * Nico Kadel-Garcia
 * Papapja
 * PastelBrush
 * SpiderKate
 * Stephen Gallagher
 * terezakoktava
 * Zhao Hang

Thank you.


[rhbz#2105393]: https://bugzilla.redhat.com/show_bug.cgi?id=2105393
