---
layout: default
title: Feature SUSE Linux Enterprise chroots
---
## Build packages for SUSE Linux Enterprise Server

Mock provides `sles-<RELEASEVER>-<TARGET_ARCH>` configs (for example `sles-15.7-x86_64` for SLES 15 SP7, or `sles-16.1-aarch64`) which build against the real SUSE Linux Enterprise Server repositories. You need a [SUSE subscription](https://www.suse.com/products/server/); a free 60-day evaluation is available at <https://www.suse.com/download/sles/>.

### How it works

SUSE does not publish static repository URLs for SUSE Linux Enterprise. At the start of every run, mock asks the registration server for the repositories of the product. That server is the SUSE Customer Center (SCC), or the RMT/SMT server set in `/etc/SUSEConnect`. SUSE's own [container-suseconnect](https://github.com/SUSE/container-suseconnect) does the same for containers.

* With SCC, every repository URL carries a short-lived CDN access token, so the URLs are fetched again on each run and are never stored in the config.
* With RMT/SMT, the repositories are protected by HTTP basic authentication. Mock writes the system credentials as `username`/`password` into the generated repositories in the chroot's `dnf.conf`.

Mock also saves the generated repositories in the chroot's cache directory (`/var/cache/mock/<CHROOT>/suse_subscription_repos.json`, readable only by root). With `--offline`, mock doesn't contact the registration server and uses the repositories saved by the last online run, together with the cached package metadata.

The repositories of the base product are always added. Mock also adds the repositories of the extensions the server marks as recommended (for example the Basesystem, Server Applications and Python 3 modules on SLES 15; SLES 16 has no modules), plus the ones in `config_opts['suse_subscription_extensions']`. Debuginfo and source repositories are added but disabled, and you can turn them on with `--enablerepo`.

SUSE Linux Enterprise only ships `dnf` (SLES 15) and `dnf5` (SLES 16) in the SUSE Package Hub extension, and the SUSE container images only contain zypper. The host's package manager therefore installs the bootstrap chroot from the SLES repositories, with the Package Hub repositories already enabled (`config_opts['suse_subscription_bootstrap_extensions']`).

This way the buildroot is installed **only** from the SLES repositories, without Package Hub. When the target architecture is emulated (for example `sles-15.7-aarch64` on an x86_64 host), the bootstrap chroot is native, so mock also requests the SLES repositories for the host architecture. As far as we know, there are no architecture specific subscriptions, so the same subscription covers both.

Package Hub packages are signed with the openSUSE Backports keys, which are only trusted for the Package Hub repositories (`config_opts['suse_subscription_bootstrap_gpgkey']`).

### Granting access

Mock can get access in one of three ways:

#### Run mock on a registered SLES host

Mock reads `/etc/zypp/credentials.d/SCCcredentials`, written by `SUSEConnect --regcode <REGISTRATION_CODE>`, and `/etc/SUSEConnect` if present.

#### Copy the credentials of a registered system

On a non-SUSE host, copy `/etc/zypp/credentials.d/SCCcredentials` (mode `0600`, owned by root) and optionally `/etc/SUSEConnect` from a registered system to the same paths. You can point at another credentials file with `config_opts['suse_subscription_credentials_file']`.

#### Use a registration code

Set it in a configuration file that only you, or only the `mock` group, can read, for example `~/.config/mock.cfg` with mode `0600`, or `/etc/mock/site-defaults.cfg` with mode `0640` and owned by `root:mock`:

```python
config_opts['suse_subscription_regcode'] = '<REGISTRATION_CODE>'
```

Don't pass the registration code with `--config-opts` on the command line, where it is visible to other users in the process list, stays in the shell history and is written to the mock logs.

Mock writes the chroot's `dnf.conf`, which contains the repository access tokens or credentials, with mode `0600`, so it is not readable by the build user.

### Extensions and modules

Add extension identifiers to build with more of them:

```python
config_opts['suse_subscription_extensions'] += ['sle-module-desktop-applications', 'sle-module-web-scripting']
```

If you request an extension that doesn't exist for the product, mock fails and lists the extensions that are available. To use only the extensions you listed and none of the recommended ones, set `config_opts['suse_subscription_include_recommended'] = False`.

### Options

See `site-defaults.cfg` for all the `suse_subscription_*` options.
