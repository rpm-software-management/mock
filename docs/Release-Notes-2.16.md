---
layout: default
title: Release Notes 2.16
---

Released on 2021-12-16.

## Mock-core-configs 36.4

The biggest change is the removal of `epel-8-*` configs. It has been replaced by several configs: `alma+epel-8-*`, `centos+epel-8-*`, `oraclelinux+epel-8-*`, `rhel+epel-8-*`, `rocky+epel-8-*`. Every config has its pros and cons:

* `alma+epel-8-*` - This uses Alma Linux 8 + Fedora EPEL. It works right off the bat and it is recommended replacement. The only disadvantage is that Koji actually uses RHEL + EPEL for EPEL builds.
* `centos+epel-8-*` - This uses CentOS 8 + Fedora EPEL. We do **not** recommend using this config, because [CentOS 8 will reach EOL on December 31, 2021](https://www.centos.org/centos-linux-eol/), and will be removed from mirrors on January 31, 2022.
* `oraclelinux+epel-8-*` - This uses Oracle Linux 8 + Fedora EPEL.
* `rhel+epel-8-*` - This uses RHEL 8 + Fedora EPEL. This is the configuration that Koji uses. But it [requires some settings](Feature-rhelchroots) and RHEL subscriptions. As a developer, you can have [16 subscriptions for free](https://developers.redhat.com/blog/2021/02/10/how-to-activate-your-no-cost-red-hat-enterprise-linux-subscription).
* `rocky+epel-8-*` - This uses Rocky Linux 8 + Fedora EPEL. It works right off the bat and it is recommended replacement. The only disadvantage is that Koji actually uses RHEL + EPEL for EPEL builds.

There were [several options on how to handle EOL of epel-* configs](https://docs.google.com/document/d/1wF7-7_y6Ac_oB-kCFdE6VBWPW8o8zjXd2Z0SGy4VxUA/edit?usp=sharing) and we asked EPEL Steering Committee to decide and they [decided to remove epel-* config](https://pagure.io/epel/issue/133#comment-765381). So it is up to you to decide what to use.

Mock will ease it and if you try to build for `epel-8-*` config and this config does not exist, you will get this message:

```
$ mock -r epel-8-x86_64 --shell
ERROR: Could not find required config file: /etc/mock/epel-8-x86_64.cfg
ERROR: There are those alternatives:
ERROR:
ERROR: [1] alma+epel-8-x86_64
ERROR:     Use instead: mock -r alma+epel-8-x86_64 --shell
ERROR:     Builds against AlmaLinux 8 repositories, together with the official EPEL repositories.
ERROR:     Project page: https://almalinux.org/
ERROR:     Enable permanently by:
ERROR:     $ ln -s /etc/mock/alma+epel-8-x86_64.cfg /home/praiskup/.config/mock/epel-8-x86_64.cfg
ERROR:
ERROR: [2] centos+epel-8-x86_64
ERROR:     Use instead: mock -r centos+epel-8-x86_64 --shell
ERROR:     Builds against CentOS Linux 8 repositories, together with the official EPEL repositories.
ERROR:     This will reach end-of-life in January 2021.
ERROR:     Enable permanently by:
ERROR:     $ ln -s /etc/mock/centos+epel-8-x86_64.cfg /home/praiskup/.config/mock/epel-8-x86_64.cfg
ERROR:
ERROR: [3] rhel+epel-8-x86_64
ERROR:     Use instead: mock -r rhel+epel-8-x86_64 --shell
ERROR:     Builds against Red Hat Enterprise Linux 8 repositories, together with the official EPEL repositories.
ERROR:     This mimics what is done in the official EPEL build system, but you need a Red Hat subscription:
ERROR:     https://rpm-software-management.github.io/mock/Feature-rhelchroots
ERROR:     Enable permanently by:
ERROR:     $ ln -s /etc/mock/rhel+epel-8-x86_64.cfg /home/praiskup/.config/mock/epel-8-x86_64.cfg
ERROR:
ERROR: [4] rocky+epel-8-x86_64
ERROR:     Use instead: mock -r rocky+epel-8-x86_64 --shell
ERROR:     Builds against Rocky Linux 8 repositories, together with the official EPEL repositories.
ERROR:     Project page: https://rockylinux.org/
ERROR:     Enable permanently by:
ERROR:     $ ln -s /etc/mock/rocky+epel-8-x86_64.cfg /home/praiskup/.config/mock/epel-8-x86_64.cfg
```

Additional changes are:

 * Fedora 33 configs were moved to eol/ directory
 * EOLed EPEL Playground configs, per [EPEL Steering Committee decision](https://pagure.io/epel/issue/136)
 * Added configs for CentOS Stream 9 + EPEL Next 9
 * We expanded `dnf_vars` which cause an issue on EL7 hosts [RHBZ#2026571](https://bugzilla.redhat.com/show_bug.cgi?id=2026571)
 * Added compatibility symlinks for EPEL 7 to centos+epel-7-*
 * Resolved the multiple "local" repo problems
 * Dropped rhel+epel-8-ppc64 config
 * Added rhel+epel-8-s390x config
 * Added navy-8-x86_64 config
 * Reduced packages installed in EPEL chroots

## Mock 2.16 changes:

- Mock got a new configuration option:

  ```
  config_opts["no-config"]["epel-8"] = {}
  config_opts["no-config"]["epel-8"]["alternatives"] = {
      "alma+epel-8": {
          "description": [
              "Builds against AlmaLinux 8 repositories, "
              "together with the official EPEL repositories.",
              "Project page: https://almalinux.org/"
          ],
      }
      }
  ```

  When the configuration file for `epel-8-*` does not exist, it will print the text from the `description` field.
  There is new file `/etc/mock/chroot-aliases.cfg` which contains defaults, but you can add your own option in your user config.

- There was one issue with BSD Tar, which has been resolved [[GH#820](https://github.com/rpm-software-management/mock/pull/820)]

- There is new option `ssl_extra_certs` [[GH#801](https://github.com/rpm-software-management/mock/pull/801)]

  ```
  config_opts['ssl_extra_certs'] = ['/etc/pki/tls/certs/client.crt', '/etc/pki/tls/certs/',
                                    '/etc/pki/tls/private/client_nopass.key.crt', '/etc/pki/tls/private/']
  #config_opts['ssl_extra_certs'] = ['/path/on/host', '/path/in/mock/chroot',
  #                                  '/path/on/host2', '/path/in/mock/chroot2', ... ]
  ```

  It copies the host's SSL certificates into a specified location inside the chroot if
  mock needs access to repositories requiring client certificate
  authentication. Specify the full path to the public certificate on the host
  and the destination directory in the chroot. Do the same for the private key.
  The private key should not be password-protected if you want Mock to run
  unattended.

- For the "bootstrap_image" feature, we use `podman run` command to install
  `dnf` stack into the bootstrap container.  Prevously we cleaned-up the
  environment for the Podman process which in turn caused DNF installation
  problems on EL8 ([issue 831](https://github.com/rpm-software-management/mock/issues/831))

- We disabled `seccomp` filtering in `--isolation=nspawn` (the default).  This
  has been done to avoid build failures on hosts with stricter filters than on
  the target chroot ([issue 811](https://github.com/rpm-software-management/mock/issues/831))

- Note **this is the last 2.x release** made from the `main` branch.  After this
  release, we will create a new branch, and future 2.x versions will get only
  important bug fixes and important changes to the config.

  A version in `main` will be 3.x and will stop supporting EL7 as build *host*.
  This will allow us to get rid of some compatibility code. However, we will
  still support building **for** EL7.

  We plan to build 3.x for all supported Fedora versions and EPEL 8+.  EPEL 7
  will stay on 2.x version.


## Currently known issues:

- On Fedora 35+, there are [problems with the nosync.so plugin](https://bugzilla.redhat.com/show_bug.cgi?id=2019329).
  Please, to avoid the problems, temporarily disable the nosync.so plugin.

- The `subscription-manager` plugins breaks the DNF stack on Fedora, so when
  installed even the normal DNF operations don't work.  Updated packages (not
  yet in Bodhi updates) help, [see the workaround](https://bugzilla.redhat.com/show_bug.cgi?id=1995465#c6).


**Following contributors contributed to this release:**

 * Adil Hussain
 * Carl George
 * Daniel Berteaud
 * Istiak Ferdous
 * Justin Vreeland
 * Louis Abel
 * Miroslav Suchý
 * Neal Gompa
 * Patrick Laimbock
 * Pavel Raiskup

Thank you.


