---
layout: default
title: Release Notes - Mock 6.4 and Core Configs 43.2
---

## [Release 6.4](https://rpm-software-management.github.io/mock/Release-Notes-6.4) - 2025-10-09


### New features

- A new plugin named `unbreq` has been added.  This plugin can detect unused
  `BuildRequires` based on file access during the RPM build.  This plugin is
  currently experimental and disabled by default.

  It can be enabled in the configuration as follows:

      config_opts['plugin_conf']['unbreq_enable'] = True

  See the [documentation page](Plugin-Unbreq).

- Added support for client certificates when using `mock-hermetic-repo`. This can be
  specified as:

      --client-cert-for example.com /path/crt.pem /path/key.pem


### Changes

- Mock now passes `--suppress-sync=yes` to every `systemd-nspawn` call (when
  available, i.e., on RHEL 9 and later).  This turns off any form of on-disk
  file system synchronization for the container payload.

  This feature sets a new default for:

      config_opts['nspawn_args'] = ['--capability=cap_ipc_lock', '--suppress-sync=yes']

  This dramatically improves container runtime performance by up to 16% for
  large packages.  It has little effect on building small packages.

  The only drawback is that in the case of a hard shutdown (e.g., a power
  outage) during the build (or any other operation you do with Mock), some
  changes in the buildroot could be lost.  As the Mock buildroot is meant to be
  ephemeral and reconstructed for every action, we have enabled this by default.
  If you want to disable this feature, you can add the following to your
  configuration:

      config_opts['nspawn_args'] = ['--capability=cap_ipc_lock']

- The [buildroot\_lock](Plugin-BuildrootLock) plugin's error reporting has been
  improved.  It now displays all package NVRAs that are not found in the
  configured DNF repositories; previously, it only displayed the first missing
  package from the list.

- We now set `module_hotfixes=true` on repositories generated using
  `--localrepo`.  This allows fetching packages from the local repository that
  are filtered out by modularity when building with `--chain --localrepo <dir>`.

### Bugfixes

- We now execute `repoquery` in `buildroot_lock.py` as a privileged user.
  Otherwise, [DNF5 fails with](https://github.com/rpm-software-management/dnf5/issues/2392):

      filesystem error: cannot create directories: Permission denied [/var/lib/mock/f44-build-repo_6596509/root/home/mockbuilder/.local/state]


### Mock Core Config Changes

- RHEL+EPEL configuration files now provide a `[local]` repository pointing to
  EPEL buildroots in Koji, so users can use `--enablerepo=local`.  The `[local]`
  repos are explicitly `gpgcheck=0`, as RHEL config `[main]` parts set
  `gpgcheck=1` by default.

- Azure Linux 2.0 configuration marked End of Life (CBL Mariner 2.0) to follow
  the distribution's [End of Life](https://techcommunity.microsoft.com/blog/azurearcblog/eol-of-azure-linux-2-0-on-azure-kubernetes-service-enabled-by-azure-arc/4434242).

- Added support for Kylin OS 11, released at the end of 2024.


#### The following contributors have contributed to this release:

- Andreas Rogge
- Marián Konček
- Miroslav Suchý
- Scott Hebert
- Takuya Wakazono

Thank You!
