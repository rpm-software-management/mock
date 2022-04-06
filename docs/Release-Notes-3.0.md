---
layout: default
title: Release Notes - Mock v3.0
---

Released on 2022-04-07.

## Mock v3.0 changes:

- Mock `v2.*` releases of Mock were supported on Enterprise Linux 7+.  Since
  this version `v3.0`, the prerequisite is Enterprise Linux 8 or newer.  Mock for
  the Enterprise Linux 7 is still supported in the [mock-2 branch][mock-2]
  upstream, but it will only receive bug fixes.

  This only affects the Mock RPM installation, i.e. the **host** EL7 operating
  system where Mock is run.  **Building** packages for the **target** Enterprise
  Linux 7 chroots continues to be supported in Mock v3.X.  More info in the
  [original issue][issue #755].

- The minimal runtime requirement now is **Python 3.6**.

- Mock has a new command `--list-chroots` which prints the list of available
  chroots with short descriptions ([PR#869][pull #869]).  It will go through both
  system-wide configuration files in `/etc/mock` and users' configuration in
  `~/.config/mock/`.  The output looks like:

  ```
  $ mock --list-chroots
  INFO: mock.py version 2.16 starting (python version = 3.10.2, NVR = mock-2.16-1.git.3339.8f0b45e.fc35)...
  Start(bootstrap): init plugins
  INFO: selinux enabled
  Finish(bootstrap): init plugins
  Start: init plugins
  INFO: selinux enabled
  Finish: init plugins
  INFO: Signal handler active
  Start: run
  config name                        description
  Global configs:
  alma+epel-8-aarch64                AlmaLinux 8 + EPEL
  alma+epel-8-ppc64le                AlmaLinux 8 + EPEL
  alma+epel-8-x86_64                 AlmaLinux 8 + EPEL
  [..snip..]
  rhel-8-x86_64                      RHEL 8
  rocky+epel-8-aarch64               Rocky Linux 8 + EPEL
  rocky+epel-8-x86_64                Rocky Linux 8 + EPEL
  rocky-8-aarch64                    Rocky Linux 8
  rocky-8-x86_64                     Rocky Linux 8
  Custom configs:

  mockbuild.exception.ConfigError: Could not find included config file: /etc/mock/foohkhk

  fedora-50-x86_64                   error during parsing the config file
  fedora-rawhide-python39            Fedora Rawhide
  Finish: run
  ```
  In this example, the `fedora-50-x86_64` is a user's configuration file which
  has some syntax issue(s).

- There is a new function `mockbuild.config.simple_load_config(name)` available.
  You should use it if you want to parse Mock's configuration files.  The use is
  as simple as:

  ```
  >>> from mockbuild.config import simple_load_config
  >>> config_opts = simple_load_config("fedora-rawhide-x86_64")
  >>> config_opts["resultdir"]
  '/var/lib/mock/fedora-rawhide-x86_64/result'
  ```

- the [hw_info plugin](Plugin-HwInfo) now reports utilization of volume with `cachedir` directory.

- Source CA certificates found in `/usr/share/pki/ca-trust-source` are now
  automatically copied from host to the target chroot, together with the
  `/etc/pki/ca-trust` ([PR 864][pull #864]).

- bash completion for `--scrub` and `--short-circuit` has been improved.

- SECCOMP was disabled for `systemd-nspawn` before, and newly we disable it for
  Podman commands by default, too ([PR 885][pull #885]).

  The SECCOMP rules (syscall allow-lists) maintained in those tools are often
  different across distributions or even distro versions.  Because Mock does
  cross-distribution builds, the "host" distro rules are not always applicable
  on the "target" distribution.  To not complicate things, and because by design
  Mock doesn't have to fully isolate, we disable SECCOMP for those
  containerization tools by default.  But if you want to enable it, you can now
  do it using:

  ```
  config_opts["seccomp"] = True
  ```

- Since the last release of Mock we have done a few mock-core-configs releases,
  see below.

## mock-core-configs-37-1

- EOL CentOS/EPEL 8 configs
- Add Fedora 36
- drop failovermethod=priority from EL8 configs
- Add Extras repo for CentOS Stream 9

## mock-core-configs-37.1-1

- drop EL7 related hack
- link default.cfg file to the right EL N config
- Add CentOS Stream 8 + EPEL 8 configs

## mock-core-configs-37.2-1

- Update CentOS Stream 9 Extras repo to use correct key
- Add AlmaLinux+EPEL 8 for POWER (ppc64le)
- Add AlmaLinux 8 for POWER (ppc64le)
- Deleted Fedora 37/Rawhide armhfp configs

## mock-core-configs-37.3-1

* Provided 'epel-9' symlinks for 'fedpkg mockbuild'
* allow n-2 gpg key for Fedora ELN
* added new key `description` for `--list-chroots` command


**Following contributors contributed to this release:**

 * Derek Schrock
 * Didik Supriadi
 * Miro Hrončok
 * Miroslav Suchý
 * Neal Gompa
 * Pavel Raiskup
 * Tomas Tomecek

Thank you.


[mock-2]: https://github.com/rpm-software-management/mock/tree/mock-2
[issue #755]: https://github.com/rpm-software-management/mock/issues/755
[pull #864]: https://github.com/rpm-software-management/mock/pull/864
[pull #885]: https://github.com/rpm-software-management/mock/pull/885
[pull #869]: https://github.com/rpm-software-management/mock/pull/869
