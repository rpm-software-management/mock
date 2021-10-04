---
layout: default
title: Release Notes 2.2
---

Released on 2020-04-02.

## Mock 2.2 new features:

 * `/etc/mock/site-defaults.cfg` was moved from /etc to %doc, and the
   config file is now much smaller (and moved to `mock-core-configs`).
   Even before the file was meant to be documentation-only (everything
   commented-out), but since it was also configuration file - with
   frequent updates in RPM - it was very easy to stop following what's new
   there ([#555](../pulls/555)).

 * Mock no more strictly depends on `mock-core-configs` package, but depends on
   `mock-configs` instead.  Even though `mock-core-configs` package still
   provides `mock-configs`, but other packages can as well, so users now can
   provide alternatives to `mock-core-configs` ([#544](../pulls/544)).

 * New `config_opts['isolation']` option invented (alternative to
   `--isolation`) to replace boolean `config_opts['use_nspawn']`.  The
   possible values are `nspawn`, `simple` and `auto` (default).  When
   `auto` is specified mock tries to use `nspawn` and if it is not
   possible, it falls-back to `simple` chroot.  This is useful to make
   mock work by default in environments like Fedora Toolbox, Podman and
   Docker.  The old `use_nspawn` option still works, but `isolation` has
   preference ([#337](../pulls/337) and [#550](../pulls/550)).

 * The `LANG` is set to `C.UTF-8` by default (and always) for chrooted
   processes.  Previously mock inherited this value from host environment,
   and defaulted to `C.UTF-8` otherwise.  This was done to make mock more
   deterministic, users can change the default by
   `config_opts['environment']['LANG']` ([#451](../issues/451)).

## Mock 2.2 bugfixes:

 * Fix for doubled log entries in some situations ([#539](../pulls/539),
   [RHBZ#1805631](https://bugzilla.redhat.com/1805631)).

 * Fix to make mock work in *Fedora Toolbox* even with
   `--bootstrap-chroot` ([#550](../pulls/550)).

 * Fix for mock in `--privileged` docker container where `os.getlogin()`
   did not work ([#551](../pulls/551)).

 * When `--bootstrap-chroot` is enabled, things like `rpm -qa --root ...` are
   executed in bootstrap chroot, instead of on host.  This is to assure that the
   RPM used is compatible with target chroot RPMDB ([#525](../issues/525)).

 * The `mock --chroot -- CMD ARG1 ARG2` command was fixed so it works correctly
   for both `--isolation=simple|nspawn` and `use_bootstrap=True|False`, the
   caveats in `--shell` and `--chroot` are now better documented in manual
   page ([#550](../pulls/550)).

 * Mock `--chain` with `--isolation=simple` was fixed to work with
   external URLs ([#542](../pulls/542)).

 * Killing of forgotten chrooted processes was made more robust.  We now
   kill also "daemons" started on background during chroot initialization
   -- when packages are installed to mock chroot and some package
   scriptlet mistakenly spawns background process ([#183](../issues/183)).

 * The `--use-bootstrap-image` was fixed to work on EL7 properly
   ([#536](../pulls/536)).

 * Stuff below `<bootstrap_root>/tmp` is now passed down to mock chroot even
   with `--isolation=nspawn` (default).  Previously - everything mock prepared
   below that directory was automatically overmounted by `systemd-nspawn`.
   So newly, stuff like `--install /tmp/some.rpm` or repositories like
   `file:///tmp/test-repo` will be correctly used through `--bootstrap-chroot`.
   This fix requires new-enough `systemd-nspawn` which supports
   `$SYSTEMD_NSPAWN_TMPFS_TMP` environment variable ([#502](../issues/502)).

 * Mock configuration; the host-local
  `baseurl=file:///some/path/$basearch` repositories with dnf variables
  inside were fixed for `--bootstrap-chroot`
  ([RHBZ#1815703](https://bugzilla.redhat.com/1815703)).

 * Mock configuration; the host-local `metalink=file:///some/host/file`
   (and mirrorlist) repositories were are fixed for bootstrap
   ([RHBZ#1816696](https://bugzilla.redhat.com/1816696)).

 * With bootstrap, we use configured yum commands instead of hard-wired
   `/usr/bin/yum` ([#518](../pulls/518)).

 * The `package_state` plugin was fixed to cleanup RPMDB before executing
   `rpm -qa`.  This broke builds on targets with incompatible RPMDB
   backends before (e.g. OpenMandriva).

## Mock-core-configs 32.6

 * The `site-defaults.cfg` config file was moved from mock to
   `mock-core-configs`.

 * The `config_opts['isolation']` is now used instead of
   `config_opts['use_nspawn']`, when necessary.

 * We declare the minimal version of `mock` by `Requires:` now.  At this
   point it is version **2.2+**.

 * The default bootstrap image was specified for Amazon Linux conifgs.

Following contributors contributed to this release:

 * Neal Gompa
 * Owen W. Taylor
 * Paul Howarth

Thank you.
