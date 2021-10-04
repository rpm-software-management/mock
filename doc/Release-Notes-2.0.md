---
layout: default
title: Release Notes 2.0
---

Released on 2020-02-07.

## Mock 2.0 highlights:

 * The mock versioning policy (or rather style) has changed from three to
   two-number pattern.  Don't panic, this isn't really special major
   release - the change was only done to move from the
   `<UNUSED>.<MAJOR>.<MINOR>` pattern to `<MAJOR>.<MINOR>`, so practically
   we went with *v2.0* instead of previously planned *v1.5.0*.

 * The `--bootstrap-chroot` option is newly enabled by default, this can be
   disabled by `--no-bootstrap-chroot`, or by
   `config_opts['use_bootstrap'] = False`.  The content of bootstrap chroot
   is cached by default and never automatically updated, but one
   can use the new `--scrub=bootstrap` to remove related caches.  The
   `--scrub=all` was updated to clean bootstrap as well (but `--clean`
   doesn't touch bootstrap chroot at all).

 * The `use_bootstrap_container` configuration option was renamed to
   `use_bootstrap` to better describe it's purpose (it never implied usage
   of container technology) and to align with `use_bootstrap_image`
   option.  Please migrate your custom configuration.

 * The output from `--debug-config` option now only shows the differences
   from mock's defaults, and the output doesn't have the Jinja templates
   expanded.

 * The `config_opts['dnf.conf']` replaced `config_opts['yum.conf']`.  Both
   still work, but only one of them can exist one config file.

 * The `--old-chroot` and `--new-chroot` options were obsoleted by
   `--isolation=chroot|nspawn`, and still default to `--isolation=nspawn`.
   Please migrate your tooling.

 * Mock now can now pre-configure DNF variables ([#346](../issues/346)), e.g.
   `config_opts['dnf_vars'] = { 'stream': '8-stream' }`

 * The regression in `--use-bootstrap-image` implementation was fixed (did
   not work at all in `v1.4.21`), and should work reliably now (`podman`
   still needs to be installed manually to make it work).

 * In mock config files we now prefer Jinja templates, instead of
   previously used python expansion `"%(variable)" % ..`.  It is not
   likely, but if you use this in your custom config files, please
   migrate.

## Mock 2.0 other fixes and enhancements:

 * Loop device files are pre-populated even in `--isolation=nspawn`
   chroots, similarly to what is done with `--isolation=chroot`
   ([#298](../issues/298)).

 * The `include()` statement in mock config now also accepts relative path
   names (relative against `config_opts['config_path']` for now).

 * The host local repositories from mock config files
   (like `baseurl=file://`) are now correctly bind-mounted to boostrap
   chroot.  So installing RPM from such repositories with
   `--bootstrap-chroot` now works (related [#381](../issues/381)).

 * Non-interactive commands in chroot are executed through
   `systemd-nspawn --console=pipe` (when `--isolation=nspawn`, default)
   ([#432](../issues/432)).

 * Better detection of host's package manager (DNF vs. YUM), for both
   bootstrap and normal chroot.  This should demotivate people from using
   `--dnf` and `--yum` options ([#233](../issues/233)).  More, on Fedora 31+ there's no
   real YUM package manager anymore (there only is `yum.rpm` which actually
   provides `/bin/yum` symlink to `/bin/dnf`).  This situation is now
   properly detected in mock, and the symlink is ignored (we fallback to
   DNF).

 * Better re-using of DNF/YUM caches, in both normal and bootstrap chroot.
   This is mostly given by previous bullet (YUM vs. DNF detection).  To be
   100% sure, we also newly rather bind-mount both DNF and DNF cache
   directories into the chroot.

 * Mock expands the config templates (aka `include()`) completely before
   executing it by eval(), and the implementation is now much simpler and
   clear.

 * Mock doesn't ignore `cleanup_on_success` configuration option after
   `--postinstall` action.

 * `mock --chain` file descriptor leak was fixed, so the descriptor usage
   is constant with multiple builds.

 * The Jinja templating is now iteratively re-rendered (when Jinja template
   expands to another Jinja template), till there is something to expand.  Also
   we start the Jinja rendering mechanism a bit earlier in the codebase so the
   mock configuration isn't really order-dependant (no matter which
   configuration option is set first).

 * Fix lvm plugin volume removal feature on modern systems
   ([rhbz#1762728](https://bugzilla.redhat.com/1762728)).

 * We don't install `shadow-utils` (we don't need this one) and
   `distribution-gpg-keys` (we copy the keys from host instead), so this
   makes the initial `dnf_install_command` transaction shorter, and more
   reliable across all the variety distributions we support.

 * The `--sources` parameter is not mandatory in `--buildsrpm` mode.

 * Mock now copies `/etc/pkg/ca-trust/extracted` into chroot
   ([#397](../issues/397)).

 * The `success` and `fail` files are created under mockbuild user, not root.

 * The `compress_logs`, when turned on, have predefined default `gzip` method.

 * We turned `--forcearch` on long time ago, but mock exited with cryptic
   error when `qemu-user-static` wasn't installed.  Mock now detects that
   `qemu-user-static` is missing and throws instructions instead.


## Mock-core-configs 32.0

 * Added configs for **Fedora 32**, Fedora Rawhide configs moved to F33.  The new
   package depends on updated **distribution-gpg-keys 1.36** package (avaiable
   in Fedora updates at the time of release).

 * Fedora 29 configs EOLed (moved below `eol` subdirectory).

 * All the configuration files were modified to use templates, to de-duplicate
   a lot of stuff and many inconsistencies were fixed.

 * On el7, mock/mock-core-configs automatically enable `use_bootstrap_image`
   option for **Fedora 31+** chroots (ZSTD compression enabled for RPMs) because without
   this option it wouldn't make sense to do anything (neither bootstrap chroot
   is installable).

Both mock and mock-core-configs packages need to be updated together as pair.

Following contributors contributed to this release:

 * Dominik Tureček
 * Jakub Čajka
 * Jakub Kadlčík
 * Merlin Mathesius
 * Scott K Logan
 * Sérgio M. Basto
 * Silvie Chlupová
 * Tomas Hrnciar

Thank you.
