---
layout: default
title: Plugin Rpmautospec
---

This plugin pre-processes spec files using
[rpmautospec](https://fedora-infra.github.io/rpmautospec-docs/) to automatically fill in
`%autorelease` and `%autochangelog` from git history. The processing runs
inside the build chroot to minimize host dependencies and produce
deterministic, repeatable builds.

The plugin hooks into the `pre_srpm_build` phase, so it only applies when
building SRPMs with `mock --buildsrpm`. It is not invoked when rebuilding
existing SRPMs with `mock --rebuild`.

## Prerequisites

For the plugin to process a spec file, **all** of the following must be true:

* The `--sources` directory is specified and is a git repository (contains `.git`).
* The spec file exists both in `--sources` and in the buildroot, and their contents are identical.
* The spec file uses rpmautospec features (`%autorelease` or `%autochangelog`).

If any condition is not met, the plugin silently skips preprocessing and the build continues normally.

## Usage

```
$ cd <package_git_repository>
$ mock -r fedora-rawhide-x86_64 --enable-plugin rpmautospec --buildsrpm --spec ./package.spec --sources .
```

This will:

1. Install `rpmautospec` into the chroot.
2. Run `rpmautospec process-distgit` on the spec file inside the chroot,
   expanding `%autorelease` and `%autochangelog` from the git history
   in `--sources`.
3. Hand the processed spec file to `rpmbuild -bs` to build the SRPM.

## Configuration

The plugin supports the following configuration options (shown with default values):

```python
config_opts['plugin_conf']['rpmautospec_enable'] = False
config_opts['plugin_conf']['rpmautospec_opts']['requires'] = ['rpmautospec']
config_opts['plugin_conf']['rpmautospec_opts']['cmd_base'] = ['/usr/bin/rpmautospec', 'process-distgit']
```

* `rpmautospec_enable` — switches the plugin on and off.
* `requires` — list of packages to install in the chroot before running the command.
* `cmd_base` — the base command and arguments. The plugin appends the input
  and output spec file paths automatically.

To enable the plugin globally, add to `/etc/mock/site-defaults.cfg`:

```python
config_opts['plugin_conf']['rpmautospec_enable'] = True
```

You can also enable it per-invocation from the command line:

```
mock --enable-plugin rpmautospec --buildsrpm --spec ./package.spec --sources .
```

Available since mock-5.3.

This plugin is DISABLED by default.
