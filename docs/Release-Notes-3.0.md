---
layout: default
title: Release Notes 3.0
---

Released on XXXXX.

## Mock 3.0 changes:

Previus releases supported RHEL7+. This version has minimal requirement RHEL 8+. RHEL 7 will receive only critical fixes as backports.
This only affects underlaying operating system where Mock is run. **Building packages for RHEL 7 is still possible.**

The minimal runtime requirement now is Python 3.

- Mock has new command `--list-chroots` which will print list of available
  chroots. It will go through both system-wide configs in `/etc/mock` and
  users config in `~/.config/mock/`. The output is:

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
alma+epel-8-ppc64le                
alma+epel-8-x86_64                 AlmaLinux 8 + EPEL
almalinux-8-aarch64                AlmaLinux 8 + EPEL
almalinux-8-ppc64le                
almalinux-8-x86_64                 AlmaLinux 8 + EPEL
amazonlinux-2-aarch64              Amazon Linux 2
amazonlinux-2-x86_64               Amazon Linux 2
centos+epel-7-ppc64le              CentOS 7 + EPEL
centos+epel-7-x86_64               CentOS 7 + EPEL
centos-7-aarch64                   CentOS 7
centos-7-ppc64                     CentOS 7
centos-7-ppc64le                   CentOS 7
...
SNIP
...
hel-8-s390x                       RHEL 8
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
  In this example `fedora-50-x86_64` is user's config which has syntax issues.

- There is a new function available: `mockbuild.config.simple_load_config(name, config_path=None)`.
  You should use it if you want to parse mock's configs. The use is as simple as:

```
>>> from mockbuild.config import simple_load_config
>>> config_opts = simple_load_config("fedora-rawhide-x86_64")
>>> config_opts["resultdir"]
'/var/lib/mock/fedora-rawhide-x86_64/result'
```

- [hw_info plugin)(Plugin-HwInfo) now reports utilization of volume with `cachedir` directory.
- Source CA certificates found in `/usr/share/pki/ca-trust-source` are copied to chroot too.
- bash completation for `--scrub` and `--short-circuit` has been improved.
- The SECCOMP in Podman is now disabled too. In Systemd-nspawn it was already disabled some time ago.
  The list of seccomp rules (syscall allow-lists) maintained
  in those tools is often different across distributions or even versions.
  Because Mock does cross-distribution builds, "host" distro rules are not
  often applicable on the "target" distribution.  To not complicate things, and
  because by design Mock doesn't have to fully isolate, we disable seccomp for
  those containerization tools by default.
  If you want to enable it, you can now do it using:
```
config_opts["seccomp"] = True
```


From the last release of Mock we have released few mock-core-configs:

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


