---
layout: default
title: Release Notes 2.1
---

Released on 2020-03-11.

## Mock 2.1 bugfixes:

 * Fixed `mock --install <sth>` request when `<sth>` is a file or directory
   in CWD, or an absolute path on host (#474).

 * We do not emit the warning `WARNING: Not using '/usr/bin/yum', it is symlink
   to '/usr/bin/dnf-3'` anymore for installing bootstrap chroot (#477,
   rhbz#1802930).

 * The `config_opts['dnf.conf']` option is made equivalent to
   `config_opts['yum.conf']` (#486).

 * Allow specifying host-local repositories with `baseurl=/absolute/path`, not
   only with `baseurl=file:///absolute/path`.  This did not work with bootstrap
   mode before (#480).

 * Fixed broken sign plugin (#476, rhbz#1806577).

 * Fixed too deep jinja recursion caused by trailing newlines in `dnf.conf`
   config option (rhbz#1806482).

 * The `mock --scrub` with lvm_root plugin enabled did not work (rhbz#1805179).

 * Do not fail when host doesn't provide CA certificates on expected locations
   (#492).

 * Traceback fix for `mock --chain` with tmpfs `keep_mounted` enabled (#479).

 * Dnf caches aren't cleaned for consecutive builds with `mock --chain` (#483).

## Mock 2.1 new features:

 * Mock expects that `rpmbuild -br` (for %generate_buildrequires spec statement,
   aka "dynamic BuildRequires") can return both exit status 0 and 11.  Currently
   released RPM always returns 11, but the plan is to fix that to return 0.

 * New option `ssl_ca_bundle_path`.  When specified, the CA certificate bundle
   is copied from host to the specified path in chroot (usually it is enough to
   keep the default behavior when whole `/etc/pki/ca-trust/extracted` is
   copied, but e.g. OpenSUSE has different path to bundle) (#500).


## Mock-core-configs 32.4

 * Specify CA bundle path for OpenSUSE chroots (#500).

 * EOL Mageia 6 configs.

 * Temporarily disable package_state plugin for openmandriva 4.0 and Cooker (#525).

Following contributors contributed to this release:

 * Jakub Kadlcik
 * Miroslav Suchý
 * Remi Collet
 * Tomas Hrnciar

Thank you.
