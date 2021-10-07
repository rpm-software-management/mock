---
layout: default
title: Plugin YumCache
---

This plugin pre-mounts `/var/cache/{yum,dnf}` directories inside chroot, so the package manager's metadata don't have to be re-downloaded between subsequent mock commands (the caches survive `mock --clean` for example).  This plugin is needed because dnf (or yum) `--installroot DIRECTORY` commands store caches below the `DIRECTORY`.

It mounts directories `/var/cache/mock/<chroot>/{dnf,yum}_cache` as `/var/cache/{dnf,yum}` in chroot.

You can explicitly clean the package manager caches by `--scrub=dnf-cache` option.

## Configuration

This plugin is **enabled by default** and has the following values built-in:

    config_opts['plugin_conf']['yum_cache_enable'] = True
    config_opts['plugin_conf']['yum_cache_opts'] = {}
    config_opts['plugin_conf']['yum_cache_opts']['max_age_days'] = 30
    config_opts['plugin_conf']['yum_cache_opts']['max_metadata_age_days'] = 30
    config_opts['plugin_conf']['yum_cache_opts']['online'] = True

* `max_age_days` - when files in cache directory is older than this number of days, then such files are removed
* `max_metadata_age_days` - when metadata (everything with suffix: ".sqlite", ".xml", ".bz2", ".gz") in cache directory is older than this number of days, then such files are removed.
* `online` - when `False`, mock doesn't apply policies for `max_*_age_days` options (complements `--offline` option)
