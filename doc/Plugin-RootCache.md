---
layout: default
title: Plugin RootCache
---

This plugin caches your buildroots. It creates archive of your buildroot and puts it in `config_opts['plugin_conf']['root_cache_opts']['dir']`, which is be default `/var/cache/mock/NAME_OF_CHROOT/root_cache/cache.tar.gz`. It is enabled by default.


## Configuration

This plugin is enabled by default and has the following values built-in:

    config_opts['plugin_conf']['root_cache_enable'] = True
    config_opts['plugin_conf']['root_cache_opts'] = {}
    config_opts['plugin_conf']['root_cache_opts']['age_check'] = True
    config_opts['plugin_conf']['root_cache_opts']['max_age_days'] = 15
    config_opts['plugin_conf']['root_cache_opts']['dir'] = "%(cache_topdir)s/%(root)s/root_cache/"
    config_opts['plugin_conf']['root_cache_opts']['compress_program'] = "pigz"
    config_opts['plugin_conf']['root_cache_opts']['extension'] = ".gz"
    config_opts['plugin_conf']['root_cache_opts']['exclude_dirs'] = ["./proc", \
       "./sys", "./dev", "./tmp/ccache", "./var/cache/yum" ]

* `age_check` - if set to `True` (which is default), then cache date is checked. See option `max_age_days` bellow. Additionally if some config is newer than cache file, then the cache is invalidated as well.
* `max_age_days` - if `age_check` is `True` and cache is older than this value, the cache is invalidated.
* `dir` - where to put cached files.
* `compress_program` - which compress program to use. By default `pigz` is used. If not present, then `gzip` is used.
* `extension` - the cache file is always named as `cache.tar$extension`. When you use different compress program e.g. `bzip2`, you should set different extension e.g. `".bz2"`.
* `exclude_dirs` - list of directories, which should not be archived.

**WARNING:** You should disable `root_cache` plugin when using `lvm_root` plugin - having two caches with the same contents would just slow you down.

**NOTE:** If you have enough disk storage you can speed-up it a bit by disabling archiving of cache:

    config_opts['plugin_conf']['root_cache_opts']['compress_program'] = ""
    config_opts['plugin_conf']['root_cache_opts']['extension'] = ""
